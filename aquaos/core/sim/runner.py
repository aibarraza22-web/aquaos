"""Scenario -> hydraulic simulation -> metrics.

Well pumping lowers aquifer heads, and lower heads reduce well output. That feedback is resolved by fixed-point
iteration: simulate, compute Theis drawdown from the simulated pumping, apply it as reservoir head patterns,
re-simulate. The report records how much pumped volume changed in the last iteration.
"""

from __future__ import annotations

import datetime as dt
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import wntr

from aquaos.core.demand.model import DemandSeries, allocate, apply_to_network, build_demand
from aquaos.core.demand.temperature import (
    TemperatureSeries,
    apply_heat_wave,
    load_climate_params,
    synthetic_temperature,
)
from aquaos.core.network.controls import remove_link_controls, set_valve_setting
from aquaos.core.network.loader import LoadedNetwork, link_kind, load_inp, validate_network, write_inp
from aquaos.core.network.valley_city import (
    RECLAIMED_USER_NODE,
    WTP_VALVE,
    build_valley_city,
)
from aquaos.core.params import resolve_params_path
from aquaos.core.rng import stream
from aquaos.core.scenario import LOCAL_TZ, Scenario
from aquaos.core.sim import metrics
from aquaos.core.supply.cap import CapAllocation, cap_allocation
from aquaos.core.supply.groundwater import GroundwaterBudget, drawdown, groundwater_budget, pumped_volume_m3
from aquaos.core.supply.recharge import RechargeLedger, recharge_ledger
from aquaos.core.units import m3_to_af, psi_to_m
from aquaos.data.connectors import noaa
from aquaos.data.provenance import Provenance

WARMUP_DAYS = 4


@dataclass
class RunResult:
    scenario: Scenario
    scenario_hash: str
    wn: wntr.network.WaterNetworkModel
    results: wntr.sim.SimulationResults
    index: pd.DatetimeIndex
    temperature: TemperatureSeries
    demand: DemandSeries
    cap: CapAllocation | None
    groundwater: GroundwaterBudget
    ledger: RechargeLedger
    mass_balance: metrics.MassBalance
    pressure: pd.DataFrame
    tanks: pd.DataFrame
    energy: pd.DataFrame
    power_kw: pd.DataFrame
    supply: dict[str, float | bool | str]
    drawdown_m: pd.DataFrame
    network_provenance: Provenance
    validation_warnings: list[str] = field(default_factory=list)
    drawdown_iteration_change: float = 0.0
    unmet: metrics.UnmetDemand | None = None

    @property
    def provenance(self) -> Provenance:
        parents = [self.network_provenance, self.demand.provenance, self.groundwater.provenance,
                   self.ledger.provenance]
        if self.cap is not None:
            parents.append(self.cap.provenance)
        return Provenance(title=f"AquaOS run {self.scenario.name} ({self.scenario_hash[:12]})", kind="derived",
                          derivation="aquaos.core.sim.runner.run_scenario (EPANET 2.2 via WNTR)",
                          parents=tuple(parents))

    @property
    def synthetic(self) -> bool:
        return self.provenance.synthetic

    def kpis(self) -> dict[str, float]:
        e = self.energy
        vol_delivered = self.mass_balance.total_demand_m3
        return {
            "energy_kwh": float(e["kwh"].sum()),
            "peak_kw": float(self.power_kw.sum(axis=1).max()),
            "kwh_per_m3_delivered": float(e["kwh"].sum() / vol_delivered) if vol_delivered else float("nan"),
            "demand_m3": vol_delivered,
            "min_pressure_psi": float(self.pressure["min_psi"].min()),
            "node_hours_below_service": float(self.pressure["node_hours_below_service"].sum()),
            "node_hours_below_min": float(self.pressure["node_hours_below_min"].sum()),
            "mass_balance_closure_rel": self.mass_balance.closure_error_rel,
            "unmet_demand_m3": self.unmet.volume_m3 if self.unmet else 0.0,
            "unmet_demand_node_hours": self.unmet.node_hours if self.unmet else 0.0,
            "groundwater_pumped_af": float(self.supply["groundwater_pumped_af"]),
            "cap_delivered_af": float(self.supply.get("cap_delivered_af", 0.0)),
            "recovered_af": float(self.supply["recovered_af"]),
        }


# ---------------------------------------------------------------- inputs
def time_index(scn: Scenario) -> pd.DatetimeIndex:
    start = pd.Timestamp(scn.time.start)
    start = start.tz_localize(LOCAL_TZ) if start.tzinfo is None else start.tz_convert(LOCAL_TZ)
    n = scn.time.duration_s // scn.time.report_step_s + 1
    return pd.date_range(start, periods=n, freq=f"{scn.time.report_step_s}s")


def build_temperature(scn: Scenario, index: pd.DatetimeIndex) -> TemperatureSeries:
    t = scn.demand.temperature
    first = (index[0] - pd.Timedelta(days=WARMUP_DAYS)).normalize()
    days = int(np.ceil((index[-1] - first) / pd.Timedelta(days=1))) + 2
    climate, climate_prov = load_climate_params(resolve_params_path(t.climate_params))
    if t.source == "synthetic":
        temp = synthetic_temperature(first.tz_localize(None).to_pydatetime(), days, climate, climate_prov,
                                     stream(scn.seed, "temperature"))
    elif t.source == "noaa_hourly":
        rec = noaa.fetch_hourly(t.noaa_station, first.date(), (first + pd.Timedelta(days=days)).date())
        temp = TemperatureSeries(rec.data["temp_c"], rec.provenance)
    else:
        if not t.csv_path:
            raise ValueError("temperature.source == 'csv' requires csv_path")
        df = pd.read_csv(scn.resolve_path(t.csv_path), parse_dates=[0], index_col=0)
        s = df.iloc[:, 0]
        idx = pd.DatetimeIndex(s.index)
        s.index = idx.tz_localize(LOCAL_TZ) if idx.tz is None else idx.tz_convert(LOCAL_TZ)
        temp = TemperatureSeries(s.rename("temp_c"), Provenance(
            title=f"Temperature CSV {t.csv_path}", kind="assumption",
            notes="User-supplied temperature file; origin not recorded in scenario"))
    if scn.demand.heat_wave is not None:
        hw = scn.demand.heat_wave
        temp = apply_heat_wave(temp, index[0].to_pydatetime(), hw.start_day, hw.duration_days, hw.tmax_delta_c,
                               hw.tmin_delta_c, hw.ramp_days, climate["diurnal_shape"])
    return temp


def build_network(scn: Scenario, workdir: Path) -> tuple[LoadedNetwork, Provenance]:
    if scn.network.source == "valley_city":
        aq = scn.supply.groundwater.aquifer
        vc = build_valley_city(scn.network.valley_city, scn.demand, aq.static_depth_m, aq.transmissivity_m2_per_day,
                               aq.storativity, aq.well_radius_m, scn.supply.recharge.mound_height_m,
                               scn.supply.cap.wtp_capacity_m3s, stream(scn.seed, "network"))
        path = write_inp(vc.wn, workdir / "valley_city.inp")
        loaded = load_inp(path, vc.provenance)  # same path as any utility network
        return loaded, vc.provenance
    loaded = load_inp(scn.resolve_path(scn.network.inp_path or ""))
    return loaded, loaded.provenance


def _pumps_of_kind(wn: wntr.network.WaterNetworkModel, *kinds: str) -> list[str]:
    return [p for p in wn.pump_name_list if link_kind(wn, p) in kinds]


def _efficiencies(scn: Scenario, wn: wntr.network.WaterNetworkModel) -> dict[str, float]:
    return {p: (scn.energy.well_pump_efficiency if link_kind(wn, p) in ("well", "recovery_well")
                else scn.energy.pump_efficiency) for p in wn.pump_name_list}


def _disable_link(wn: wntr.network.WaterNetworkModel, name: str) -> None:
    remove_link_controls(wn, [name])
    wn.get_link(name).initial_status = wntr.network.LinkStatus.Closed


def _set_drawdown_patterns(wn: wntr.network.WaterNetworkModel, wells: list[str], dd: pd.DataFrame) -> None:
    for w in wells:
        res = wn.get_node(wn.get_link(w).start_node_name)
        name = f"H_{res.name}"
        base = res.base_head
        mult = list((base - dd[w].to_numpy()) / base)
        if name in wn.pattern_name_list:
            res.head_pattern_name = None
            wn.remove_pattern(name)
        wn.add_pattern(name, mult)
        res.head_pattern_name = name


# ---------------------------------------------------------------- run
def run_scenario(scn: Scenario, workdir: str | Path | None = None, drawdown_iterations: int = 2) -> RunResult:
    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="aquaos_"))
    workdir.mkdir(parents=True, exist_ok=True)
    index = time_index(scn)
    step = scn.time.report_step_s

    loaded, net_prov = build_network(scn, workdir)
    wn = loaded.wn
    val = validate_network(wn)
    if not val.ok:
        raise ValueError("network validation failed: " + "; ".join(val.errors))

    temp = build_temperature(scn, index)
    reclaimed = RECLAIMED_USER_NODE if RECLAIMED_USER_NODE in wn.node_name_list else None
    allocs = allocate(wn, scn.demand, scn.seed, reclaimed_node=reclaimed)
    demand = build_demand(allocs, scn.demand, temp, index, scn.seed)
    apply_to_network(wn, demand, step)

    # supply layer
    cap = cap_allocation(scn.supply.cap) if WTP_VALVE in wn.link_name_list else None
    days = sorted({ts.date() for ts in index[:-1]})
    if cap is not None:
        set_valve_setting(wn, WTP_VALVE, cap.wtp_setting_m3s(days))
    gw = groundwater_budget(scn.supply.groundwater)
    ledger = recharge_ledger(scn.supply.recharge)
    wells = _pumps_of_kind(wn, "well")
    recovery = _pumps_of_kind(wn, "recovery_well")
    if ledger.balance_af <= 0:
        for r in recovery:
            _disable_link(wn, r)
    if gw.remaining_af <= 0:
        for w in wells:
            _disable_link(wn, w)

    opts = wn.options.time
    opts.duration = scn.time.duration_s
    opts.hydraulic_timestep = scn.time.hydraulic_step_s
    opts.report_timestep = step
    opts.pattern_timestep = step
    opts.quality_timestep = step
    opts.start_clocktime = int(index[0].hour * 3600 + index[0].minute * 60)
    hyd = scn.hydraulics
    wn.options.hydraulic.demand_model = hyd.demand_model
    wn.options.hydraulic.required_pressure = psi_to_m(hyd.required_pressure_psi)
    wn.options.hydraulic.minimum_pressure = psi_to_m(hyd.minimum_pressure_psi)

    all_wells = wells + recovery
    coords = {w: wn.get_node(wn.get_link(w).end_node_name).coordinates for w in all_wells}
    dd = pd.DataFrame(0.0, index=index, columns=all_wells)
    prev_vol = None
    change = 0.0
    results: wntr.sim.SimulationResults | None = None
    for it in range(max(1, drawdown_iterations + 1)):
        if it > 0 and all_wells:
            _set_drawdown_patterns(wn, all_wells, dd)
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim(file_prefix=str(workdir / f"run{it}"), version=2.2)
        if not all_wells:
            break
        flows = results.link["flowrate"][all_wells].clip(lower=0)
        flows.index = index[: len(flows)]
        dd = drawdown(flows, coords, scn.supply.groundwater.aquifer).reindex(index).ffill()
        vol = pumped_volume_m3(flows, step)
        if prev_vol is not None:
            change = abs(vol - prev_vol) / prev_vol if prev_vol > 0 else 0.0
        prev_vol = vol
    assert results is not None

    for frame in (results.node, results.link):
        for key in frame:
            frame[key].index = index[: len(frame[key])]

    flows = results.link["flowrate"]
    power = metrics.pump_power_kw(wn, results, _efficiencies(scn, wn))
    energy = metrics.energy_summary(wn, power, flows, step)
    mb = metrics.mass_balance(wn, results, step)
    unmet = metrics.unmet_demand(demand.data, results.node["demand"], step)
    rpt = scn.report
    pressure = metrics.pressure_summary(wn, results, rpt.min_pressure_psi, rpt.service_pressure_psi,
                                        rpt.max_pressure_psi)
    tanks = metrics.tank_summary(wn, results)

    gw_m3 = pumped_volume_m3(flows[wells], step) if wells else 0.0
    rec_m3 = pumped_volume_m3(flows[recovery], step) if recovery else 0.0
    start_date: dt.date = index[0].date()
    supply: dict[str, float | bool | str] = {}
    for k, v in gw.assess(gw_m3, start_date, scn.time.duration_days).items():
        supply[f"groundwater_{k}"] = v
    recharge_af = scn.supply.recharge.recharge_af_per_year * scn.time.duration_days / 365.0
    if recharge_af > 0:
        ledger.deposit(recharge_af, "recharge during run")
    ledger.recover(m3_to_af(rec_m3), "recovery wells during run")
    supply["recovered_af"] = m3_to_af(rec_m3)
    supply["credit_balance_end_af"] = ledger.balance_af
    supply["credits_overdrawn"] = ledger.overdrawn
    if cap is not None:
        cap_m3 = pumped_volume_m3(flows[[WTP_VALVE]], step)
        supply["cap_condition"] = cap.condition
        supply["cap_delivered_af"] = m3_to_af(cap_m3)
        supply["cap_wtp_setting_m3s"] = cap.wtp_setting_m3s(days)
        run_days = scn.time.duration_days
        supply["cap_pro_rata_af"] = m3_to_af(
            sum(cap.daily_limit_m3s(d) for d in days) / len(days) * run_days * 86400.0)
        supply["cap_exceeds_pro_rata"] = m3_to_af(cap_m3) > float(supply["cap_pro_rata_af"]) * 1.001
    rcl = _pumps_of_kind(wn, "reclaimed")
    if rcl:
        supply["reclaimed_delivered_af"] = m3_to_af(pumped_volume_m3(flows[rcl], step))

    return RunResult(
        scenario=scn, scenario_hash=scn.scenario_hash(), wn=wn, results=results, index=index, temperature=temp,
        demand=demand, cap=cap, groundwater=gw, ledger=ledger, mass_balance=mb, pressure=pressure, tanks=tanks,
        energy=energy, power_kw=power, supply=supply, drawdown_m=dd, network_provenance=net_prov,
        validation_warnings=val.warnings, drawdown_iteration_change=change, unmet=unmet,
    )
