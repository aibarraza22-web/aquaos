import os

import pytest
import wntr

from aquaos.core.network.controls import (
    TankLevelRule,
    controls_targeting,
    remove_link_controls,
    set_valve_setting,
)
from aquaos.core.network.loader import (
    link_kind,
    load_inp,
    parse_tags,
    validate_network,
    write_inp,
    zone_labels,
    zone_map,
)
from aquaos.core.network.valley_city import WTP_VALVE, build_valley_city, expected_zone_demand_m3s
from aquaos.core.rng import stream
from aquaos.core.scenario import DemandConfig, ValleyCityConfig

NET3 = os.path.join(os.path.dirname(wntr.__file__), "library", "networks", "Net3.inp")


def build(seed: int = 1, **cfg):
    return build_valley_city(ValleyCityConfig(**cfg), DemandConfig(), 110, 800, 0.1, 0.2, 15, 0.3,
                             stream(seed, "net"))


def test_valley_city_structure():
    vc = build()
    wn = vc.wn
    rep = validate_network(wn)
    assert rep.ok, rep.errors
    assert set(vc.zone_nodes) == {1, 2, 3, 4}
    assert 250 <= wn.num_junctions <= 400
    kinds = {link_kind(wn, p) for p in wn.pump_name_list}
    assert kinds == {"high_service", "booster", "well", "recovery_well", "reclaimed"}
    assert len(vc.wells) == 5 and len(vc.recovery_wells) == 2
    assert wn.get_link(WTP_VALVE).valve_type == "FCV"
    assert {"T1", "T2", "T3", "T4", "CLEARWELL", "RCL_TANK"} <= set(wn.tank_name_list)
    closed = [n for n, p in wn.pipes() if p.initial_status == wntr.network.LinkStatus.Closed]
    assert closed == ["IT_1_2", "IT_2_3", "IT_3_4"]


def test_zones_rise_upslope_and_generator_is_seeded():
    wn = build().wn
    zones = zone_map(wn)
    mean_elev = {z: sum(wn.get_node(n).elevation for n in zones if zones[n] == z) /
                 sum(1 for n in zones if zones[n] == z) for z in (1, 2, 3, 4)}
    assert mean_elev[1] < mean_elev[2] < mean_elev[3] < mean_elev[4]
    e1 = [j.elevation for _, j in build(1).wn.junctions()]
    e2 = [j.elevation for _, j in build(1).wn.junctions()]
    e3 = [j.elevation for _, j in build(2).wn.junctions()]
    assert e1 == e2 and e1 != e3


def test_inp_roundtrip_preserves_tags_and_controls(tmp_path):
    vc = build()
    path = write_inp(vc.wn, tmp_path / "vc.inp")
    ln = load_inp(path, vc.provenance)
    wn2 = ln.wn
    assert wn2.describe() == vc.wn.describe()
    assert zone_map(wn2) == zone_map(vc.wn)
    assert zone_labels(wn2)["RCL_USER"] == "reclaimed"
    assert link_kind(wn2, "GW2_1") == "well" and parse_tags(wn2.get_link("B3_1").tag)["zone"] == "3"
    assert len(ln.provenance.sha256 or "") == 64 and ln.provenance.synthetic


def test_controls_found_by_target_after_inp_load(tmp_path):
    vc = build()
    wn2 = load_inp(write_inp(vc.wn, tmp_path / "vc.inp")).wn
    assert len(controls_targeting(wn2, "B2_1")) == 3  # on, off, suction guard
    assert len(controls_targeting(wn2, "GW2_1")) == 2
    set_valve_setting(wn2, WTP_VALVE, 0.123)
    values = sorted(float(wn2.get_control(c).actions()[0]._value) for c in controls_targeting(wn2, WTP_VALVE))
    assert values == [0.0, 0.123]
    assert wn2.get_link(WTP_VALVE).initial_setting == 0.123
    remove_link_controls(wn2, ["GW2_1"])
    assert controls_targeting(wn2, "GW2_1") == []


def test_initial_pump_status_follows_rules():
    wn = build().wn  # tanks start at 6.5 m, above every lead/lag start level
    assert all(p.initial_status == wntr.network.LinkStatus.Closed for _, p in wn.pumps())
    wn2 = build(tank_init_level_m=3.0).wn  # every tank below its start levels
    open_, closed = wntr.network.LinkStatus.Open, wntr.network.LinkStatus.Closed
    assert wn2.get_link("GW2_1").initial_status == open_
    assert wn2.get_link("HS1").initial_status == open_  # clearwell (3.5 m) above its guard-resume level
    assert wn2.get_link("B2_1").initial_status == closed  # suction guard: T1 (3.0 m) below resume level 4.0 m


def test_tank_rule_validation():
    with pytest.raises(ValueError):
        TankLevelRule("P", "T", on_below_m=5, off_above_m=4)


def test_expected_zone_demand_includes_large_users():
    q = expected_zone_demand_m3s(ValleyCityConfig(), DemandConfig())
    assert q[1] > q[3] and q[2] > q[3]  # fab in zone 1, data center in zone 2


def test_load_external_net3_and_validation_errors():
    ln = load_inp(NET3)
    rep = validate_network(ln.wn)
    assert rep.ok and any("zone tag" in w for w in rep.warnings)
    assert ln.provenance.synthetic  # unknown origin -> flagged, never presented as real
    wn = wntr.network.WaterNetworkModel()
    wn.add_junction("A", elevation=0)
    wn.add_junction("B", elevation=0)
    wn.add_pipe("P", "A", "B")
    rep = validate_network(wn)
    assert not rep.ok and any("no reservoirs" in e for e in rep.errors)
    assert any("not connected" in e for e in rep.errors)
