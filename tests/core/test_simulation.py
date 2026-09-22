"""Integration tests on full scenario runs: mass balance, pressure/tank bounds, reproducibility, supply limits."""

import os

import numpy as np
import pytest
import wntr

from aquaos.core.report import render_markdown
from aquaos.core.scenario import load_scenario
from aquaos.core.sim.metrics import tank_levels
from aquaos.core.sim.runner import run_scenario
from aquaos.core.store import ResultsStore
from aquaos.core.units import m_to_psi
from tests.conftest import SCENARIOS

NET3 = os.path.join(os.path.dirname(wntr.__file__), "library", "networks", "Net3.inp")


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    scn = load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml")
    return run_scenario(scn, workdir=tmp_path_factory.mktemp("baseline"))


@pytest.fixture(scope="module")
def heatwave(tmp_path_factory):
    scn = load_scenario(SCENARIOS / "valley_city_heatwave_7d.yaml")
    return run_scenario(scn, workdir=tmp_path_factory.mktemp("heatwave"))


@pytest.fixture(scope="module")
def shortage(tmp_path_factory):
    scn = load_scenario(SCENARIOS / "valley_city_2027_shortage_heatwave_7d.yaml")
    return run_scenario(scn, workdir=tmp_path_factory.mktemp("shortage"))


def short(seed: int | None = None, days: float = 1.0, **extra):
    over = {"time": {"duration_days": days}, **extra}
    if seed is not None:
        over["seed"] = seed
    return load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml", overrides=over)


# ------------------------------------------------------------------ mass balance
@pytest.mark.parametrize("run_name", ["baseline", "heatwave", "shortage"])
def test_mass_balance(run_name, request):
    run = request.getfixturevalue(run_name)
    mb = run.mass_balance
    assert mb.max_rel_residual < 1e-4, "instantaneous continuity violated"
    assert abs(mb.closure_error_rel) < 0.005, "sources != demand + storage change"
    # At 15-minute reporting, pump switching between report steps is not sampled, so the per-tank check is
    # resolution-limited here. test_tank_storage_consistency_fine_step checks it strictly at 5-minute steps.
    for tank, err in mb.tank_volume_error_rel.items():
        assert err < 0.05, f"tank {tank}: level-derived volume change disagrees with integrated inflow"


def test_tank_storage_consistency_fine_step(tmp_path):
    scn = load_scenario(SCENARIOS / "valley_city_2027_shortage_heatwave_7d.yaml",
                        overrides={"time": {"duration_days": 2, "hydraulic_step_s": 300, "report_step_s": 300}})
    run = run_scenario(scn, workdir=tmp_path, drawdown_iterations=0)
    for tank, err in run.mass_balance.tank_volume_error_rel.items():
        assert err < 0.005, f"tank {tank}: {err:.3%} storage inconsistency at 5-minute steps"
    assert abs(run.mass_balance.closure_error_rel) < 0.002


# ------------------------------------------------------------------ pressure and tank bounds
@pytest.mark.parametrize("run_name", ["baseline", "heatwave", "shortage"])
def test_pressure_bounds(run_name, request):
    run = request.getfixturevalue(run_name)
    rpt = run.scenario.report
    p = run.results.node["pressure"]
    demand_nodes = [n for n in run.demand.data.columns]
    psi = p[demand_nodes].apply(m_to_psi)
    assert psi.min().min() >= rpt.service_pressure_psi, f"pressure below {rpt.service_pressure_psi} psi"
    assert psi.max().max() <= rpt.max_pressure_psi
    assert run.kpis()["unmet_demand_m3"] == pytest.approx(0.0, abs=1.0)


@pytest.mark.parametrize("run_name", ["baseline", "heatwave", "shortage"])
def test_tank_levels_within_design_bounds(run_name, request):
    run = request.getfixturevalue(run_name)
    lv = tank_levels(run.wn, run.results)
    for t in run.wn.tank_name_list:
        tk = run.wn.get_node(t)
        assert lv[t].min() >= tk.min_level - 1e-6
        assert lv[t].max() <= tk.max_level + 1e-6
    assert (run.tanks["hours_at_min"] == 0).all(), "a tank drained to its minimum level"


# ------------------------------------------------------------------ energy and supply layer
def test_energy_consistency(baseline):
    step_h = baseline.scenario.time.report_step_s / 3600
    kwh = baseline.power_kw.iloc[:-1].sum() * step_h
    assert np.allclose(kwh.to_numpy(), baseline.energy["kwh"].to_numpy())
    wells = baseline.energy[baseline.energy["kind"] == "well"]
    boosters = baseline.energy[baseline.energy["kind"] == "booster"]
    assert wells["kwh_per_m3"].dropna().min() > boosters["kwh_per_m3"].dropna().max()  # deep lift costs more
    assert baseline.kpis()["peak_kw"] > 0


def test_no_startup_power_spike(baseline):
    total = baseline.power_kw.sum(axis=1)
    assert total.iloc[0] < 0.8 * total.max(), "all pumps running at t=0 (initial status not set from rules)"


def test_supply_limits_respected_in_baseline(baseline):
    s = baseline.supply
    assert not s["groundwater_exceeds_remaining_allowance"]
    assert not s["credits_overdrawn"]
    assert s["cap_delivered_af"] <= s["cap_pro_rata_af"] * 1.001
    assert baseline.drawdown_m.to_numpy().max() > 0
    assert baseline.drawdown_iteration_change < 0.10


def test_shortage_shifts_load_to_groundwater(baseline, shortage):
    assert shortage.supply["cap_wtp_setting_m3s"] < baseline.supply["cap_wtp_setting_m3s"]
    assert shortage.supply["cap_delivered_af"] < baseline.supply["cap_delivered_af"]
    gw = lambda r: r.supply["groundwater_pumped_af"] + r.supply["recovered_af"]  # noqa: E731
    assert gw(shortage) > gw(baseline)
    assert shortage.kpis()["kwh_per_m3_delivered"] > baseline.kpis()["kwh_per_m3_delivered"]


def test_heat_wave_raises_temperature_and_demand(baseline, heatwave):
    tb = baseline.temperature.at(baseline.index)
    th = heatwave.temperature.at(heatwave.index)
    assert th.max() > tb.max() and (th >= tb - 1e-9).all()
    assert heatwave.mass_balance.total_demand_m3 > baseline.mass_balance.total_demand_m3
    assert heatwave.temperature.provenance.synthetic


# ------------------------------------------------------------------ reproducibility
def test_same_scenario_same_results(tmp_path):
    a = run_scenario(short(), workdir=tmp_path / "a")
    b = run_scenario(short(), workdir=tmp_path / "b")
    assert a.scenario_hash == b.scenario_hash
    assert a.results.node["pressure"].equals(b.results.node["pressure"])
    assert a.results.link["flowrate"].equals(b.results.link["flowrate"])
    c = run_scenario(short(seed=99), workdir=tmp_path / "c")
    assert c.scenario_hash != a.scenario_hash
    assert not c.demand.data.equals(a.demand.data)


def test_pdd_equals_dd_when_pressure_is_adequate(tmp_path):
    pdd = run_scenario(short(), workdir=tmp_path / "pdd")
    dd = run_scenario(short(hydraulics={"demand_model": "DD"}), workdir=tmp_path / "dd")
    assert pdd.mass_balance.total_demand_m3 == pytest.approx(dd.mass_balance.total_demand_m3, rel=1e-4)


# ------------------------------------------------------------------ plug-in path: a utility .inp
def test_external_inp_network_runs(tmp_path):
    over = {"network": {"source": "inp", "inp_path": NET3}, "demand": {"large_users": []},
            "time": {"duration_days": 2}}
    scn = load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml", overrides=over)
    run = run_scenario(scn, workdir=tmp_path)
    assert run.cap is None  # no treatment-plant valve in Net3
    assert abs(run.mass_balance.closure_error_rel) < 0.01
    assert run.synthetic and "inp" in scn.input_files()
    assert "untagged" in run.pressure.index


# ------------------------------------------------------------------ outputs
def test_report_carries_assumptions(baseline):
    md = render_markdown(baseline)
    assert "SYNTHETIC" in md.splitlines()[2]
    assert baseline.scenario_hash in md
    assert "cy2026_tier1" in md and "[PRIMARY]" in md and "[ASSUMPTION]" in md
    assert "https://www.cap-az.com/" in md and "azleg.gov" in md and "ncei.noaa.gov" in md
    assert "Mass balance" in md and "Pressure by zone" in md and "Pump energy" in md


def test_results_store_roundtrip(baseline, tmp_path):
    store = ResultsStore(tmp_path)
    store.save(baseline)
    assert store.has(baseline.scenario_hash)
    k = store.kpis(baseline.scenario_hash).set_index("kpi")["value"]
    assert k["energy_kwh"] == pytest.approx(baseline.kpis()["energy_kwh"])
    p = store.timeseries(baseline.scenario_hash, "pressure_m")
    assert p.shape == baseline.results.node["pressure"].shape
    assert not store.has("0" * 64)
    store.save(baseline)  # idempotent re-save
    assert len(store.kpis()) == len(baseline.kpis())
