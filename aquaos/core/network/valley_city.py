"""Synthetic "Valley City" network generator (SYNTHETIC).

Layout, from the low end to the high end of a desert alluvial slope:

* A CAP turnout (reservoir) feeds a surface-water treatment plant. Plant throughput is a flow-control valve
  (``WTP``) set by the supply layer. It fills a clearwell that high-service pumps lift into Zone 1.
* ``zones`` stacked pressure zones on rising ground. Each is a looped grid with a floating storage tank ``T<k>``.
  Zone k>1 is fed from zone k-1 by a two-pump booster station ``B<k>_1/2``. Normally closed interties join
  adjacent zones (used in Phase 3).
* Groundwater wells pump from aquifer reservoirs (head = aquifer water level, with drawdown applied as a head
  pattern) into the upper zones.
* A recharge-and-recovery well field pumps stored CAP water back out of the aquifer into Zone 1.
* A separate non-potable reclaimed-water pipeline runs from the water reclamation facility (``WRF``) to an
  industrial user with its own tank.

The result goes through :func:`aquaos.core.network.loader.write_inp` and is loaded back through the same path
as any utility network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import wntr

from aquaos.core.network.controls import (
    TankLevelRule,
    ValveLevelRule,
    apply_tank_rules,
    apply_valve_rules,
    initialize_statuses,
)
from aquaos.core.scenario import DemandConfig, ValleyCityConfig
from aquaos.core.units import SECONDS_PER_DAY
from aquaos.data.provenance import Provenance, synthetic

WTP_VALVE = "WTP"
CLEARWELL = "CLEARWELL"
CAP_TURNOUT = "CAP_TURNOUT"
RECLAIMED_USER_NODE = "RCL_USER"
RECLAIMED_TANK = "RCL_TANK"


@dataclass
class ValleyCity:
    wn: wntr.network.WaterNetworkModel
    provenance: Provenance
    tank_rules: list[TankLevelRule] = field(default_factory=list)
    valve_rules: list[ValveLevelRule] = field(default_factory=list)
    zone_nodes: dict[int, list[str]] = field(default_factory=dict)
    wells: dict[str, str] = field(default_factory=dict)  # pump -> aquifer reservoir
    recovery_wells: dict[str, str] = field(default_factory=dict)


def expected_zone_demand_m3s(cfg: ValleyCityConfig, demand: DemandConfig) -> dict[int, float]:
    """Average potable demand per zone at reference temperature, used for sizing only."""
    res = demand.population * demand.residential_m3_per_capita_day * demand.growth_factor
    com = res * demand.commercial_fraction_of_residential
    per_zone = (res + com) / cfg.zones
    out = {k: per_zone for k in range(1, cfg.zones + 1)}
    for u in demand.large_users:
        if not u.reclaimed and u.zone is not None and u.zone in out:
            out[u.zone] += u.avg_m3_per_day
    return {k: v / SECONDS_PER_DAY for k, v in out.items()}


def _single_point_curve(wn: wntr.network.WaterNetworkModel, name: str, q: float, h: float) -> str:
    wn.add_curve(name, "HEAD", [(q, h)])
    return name


def _cooper_jacob_drawdown(q_m3s: float, t_m2d: float, s: float, r_m: float, days: float) -> float:
    q = q_m3s * SECONDS_PER_DAY
    u_arg = 2.25 * t_m2d * days / (r_m**2 * s)
    return max(0.0, q / (4 * math.pi * t_m2d) * math.log(u_arg))


def build_valley_city(cfg: ValleyCityConfig, demand: DemandConfig, aquifer_static_depth_m: float,
                      transmissivity_m2d: float, storativity: float, well_radius_m: float,
                      mound_height_m: float, wtp_capacity_m3s: float,
                      rng: np.random.Generator) -> ValleyCity:
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.inpfile_units = "LPS"
    wn.options.hydraulic.headloss = "H-W"
    zone_q = expected_zone_demand_m3s(cfg, demand)
    R, C, dx = cfg.grid_rows, cfg.grid_cols, cfg.spacing_m
    zone_height = (R + 1) * dx
    mid = C // 2
    vc = ValleyCity(wn=wn, provenance=synthetic(
        "Valley City synthetic network",
        "aquaos.core.network.valley_city.build_valley_city from scenario generator parameters and seed",
        units={"length": "m", "diameter": "m", "elevation": "m", "flow": "m3/s"}))

    def zone_low(k: int) -> float:
        return cfg.base_elevation_m + (k - 1) * cfg.zone_rise_m

    def zone_top(k: int) -> float:
        return zone_low(k) + cfg.zone_band_m

    def zone_hgl_mid(k: int) -> float:
        base = zone_top(k) + cfg.tank_height_above_zone_top_m
        return base + 0.5 * (cfg.tank_min_level_m + cfg.tank_max_level_m)

    def node(k: int, r: int, c: int) -> str:
        return f"Z{k}_J{r:02d}_{c:02d}"

    # ---- pressure-zone grids
    for k in range(1, cfg.zones + 1):
        names = []
        for r in range(R):
            for c in range(C):
                elev = zone_low(k) + cfg.zone_band_m * r / (R - 1) + rng.normal(0, cfg.elevation_noise_m)
                elev = float(np.clip(elev, zone_low(k) - 1.0, zone_top(k) + 1.0))
                n = node(k, r, c)
                wn.add_junction(n, base_demand=0.0, elevation=elev,
                                coordinates=(c * dx, (k - 1) * zone_height + r * dx))
                wn.get_node(n).tag = f"zone:{k}"
                names.append(n)
        vc.zone_nodes[k] = names
        for r in range(R):
            for c in range(C):
                trunk_h = r == 0 or r == R - 1
                trunk_v = c == mid
                if c + 1 < C:
                    d = cfg.trunk_diameter_m if trunk_h else cfg.distribution_diameter_m
                    wn.add_pipe(f"Z{k}_H{r:02d}_{c:02d}", node(k, r, c), node(k, r, c + 1), length=dx,
                                diameter=d, roughness=cfg.hazen_williams_c)
                if r + 1 < R:
                    d = cfg.trunk_diameter_m if trunk_v else cfg.distribution_diameter_m
                    wn.add_pipe(f"Z{k}_V{r:02d}_{c:02d}", node(k, r, c), node(k, r + 1, c), length=dx,
                                diameter=d, roughness=cfg.hazen_williams_c)

        # zone storage tank on the high side
        downstream = sum(zone_q[j] for j in range(k + 1, cfg.zones + 1))
        vol = cfg.zone_tank_storage_hours * 3600 * (zone_q[k] + 0.5 * downstream)
        op_range = cfg.tank_max_level_m - cfg.tank_min_level_m
        diam = math.sqrt(4 * vol / op_range / math.pi)
        tank = f"T{k}"
        wn.add_tank(tank, elevation=zone_top(k) + cfg.tank_height_above_zone_top_m,
                    init_level=cfg.tank_init_level_m, min_level=cfg.tank_min_level_m,
                    max_level=cfg.tank_max_level_m, diameter=round(diam, 2),
                    coordinates=(mid * dx, (k - 1) * zone_height + R * dx))
        wn.get_node(tank).tag = f"zone:{k}"
        wn.add_pipe(f"{tank}_INLET", node(k, R - 1, mid), tank, length=dx, diameter=cfg.trunk_diameter_m,
                    roughness=cfg.hazen_williams_c)

    # ---- CAP turnout, treatment plant, clearwell, high-service pumps
    wn.add_reservoir(CAP_TURNOUT, base_head=cfg.cap_turnout_head_m, coordinates=(-1200.0, -600.0))
    wn.add_junction("WTP_IN", elevation=cfg.clearwell_base_m + 2, coordinates=(-800.0, -600.0))
    wn.add_junction("WTP_OUT", elevation=cfg.clearwell_base_m + 2, coordinates=(-700.0, -600.0))
    wn.add_pipe("RAW_MAIN", CAP_TURNOUT, "WTP_IN", length=1000, diameter=0.6, roughness=120)
    wn.add_valve(WTP_VALVE, "WTP_IN", "WTP_OUT", diameter=0.6, valve_type="FCV",
                 initial_setting=wtp_capacity_m3s)
    wn.get_link(WTP_VALVE).tag = "kind:treatment_plant"
    cw_vol = wtp_capacity_m3s * 3 * 3600
    cw_min, cw_max = 0.5, 5.5
    wn.add_tank(CLEARWELL, elevation=cfg.clearwell_base_m, init_level=3.5, min_level=cw_min, max_level=cw_max,
                diameter=round(math.sqrt(4 * cw_vol / (cw_max - cw_min) / math.pi), 2),
                coordinates=(-600.0, -600.0))
    wn.add_pipe("CW_INLET", "WTP_OUT", CLEARWELL, length=50, diameter=0.6, roughness=130)
    wn.add_junction("HS_SUCTION", elevation=cfg.clearwell_base_m, coordinates=(-500.0, -600.0))
    wn.add_junction("HS_DISCHARGE", elevation=cfg.clearwell_base_m, coordinates=(-400.0, -600.0))
    wn.add_pipe("CW_OUTLET", CLEARWELL, "HS_SUCTION", length=50, diameter=0.6, roughness=130)
    wn.add_pipe("HS_MAIN", "HS_DISCHARGE", node(1, 0, mid), length=800, diameter=0.6, roughness=130)
    hs_q = wtp_capacity_m3s * 0.65
    hs_h = zone_hgl_mid(1) - (cfg.clearwell_base_m + 3.0) + 8.0
    _single_point_curve(wn, "HS_CURVE", hs_q, hs_h)
    for i in (1, 2):
        p = f"HS{i}"
        wn.add_pump(p, "HS_SUCTION", "HS_DISCHARGE", "HEAD", "HS_CURVE")
        wn.get_link(p).tag = "kind:high_service,zone:1"
    vc.tank_rules += [
        TankLevelRule("HS1", "T1", 5.5, 9.0, guard_tank=CLEARWELL, guard_below_m=cw_min + 0.5,
                      guard_resume_m=cw_min + 1.5),
        TankLevelRule("HS2", "T1", 4.0, 8.0, guard_tank=CLEARWELL, guard_below_m=cw_min + 1.5,
                      guard_resume_m=cw_min + 2.5),
    ]
    vc.valve_rules.append(ValveLevelRule(WTP_VALVE, CLEARWELL, wtp_capacity_m3s, close_above_m=cw_max - 0.3,
                                         reopen_below_m=cw_max - 1.5))

    # ---- booster stations and interties
    for k in range(2, cfg.zones + 1):
        cb = max(1, mid - 3)
        suction, discharge = f"B{k}_SUCTION", f"B{k}_DISCHARGE"
        y = (k - 1) * zone_height - 0.5 * dx
        wn.add_junction(suction, elevation=zone_top(k - 1), coordinates=(cb * dx - 30, y))
        wn.add_junction(discharge, elevation=zone_top(k - 1), coordinates=(cb * dx + 30, y))
        wn.add_pipe(f"B{k}_SUC_MAIN", node(k - 1, R - 1, cb), suction, length=dx / 2,
                    diameter=cfg.trunk_diameter_m, roughness=cfg.hazen_williams_c)
        wn.add_pipe(f"B{k}_DIS_MAIN", discharge, node(k, 0, cb), length=dx / 2,
                    diameter=cfg.trunk_diameter_m, roughness=cfg.hazen_williams_c)
        q = 0.9 * sum(zone_q[j] for j in range(k, cfg.zones + 1))
        h = zone_hgl_mid(k) - zone_hgl_mid(k - 1) + 10.0
        _single_point_curve(wn, f"B{k}_CURVE", q, h)
        for i in (1, 2):
            p = f"B{k}_{i}"
            wn.add_pump(p, suction, discharge, "HEAD", f"B{k}_CURVE")
            wn.get_link(p).tag = f"kind:booster,zone:{k}"
        # Suction guard: stop drawing from zone k-1 when its tank is low, so upper-zone wells pick up the load.
        suction_tank = f"T{k - 1}"
        vc.tank_rules += [
            TankLevelRule(f"B{k}_1", f"T{k}", 5.5, 9.0, guard_tank=suction_tank, guard_below_m=2.5,
                          guard_resume_m=4.0),
            TankLevelRule(f"B{k}_2", f"T{k}", 4.0, 8.0, guard_tank=suction_tank, guard_below_m=3.5,
                          guard_resume_m=5.0),
        ]
        ci = C - 2
        wn.add_pipe(f"IT_{k - 1}_{k}", node(k - 1, R - 1, ci), node(k, 0, ci), length=dx,
                    diameter=cfg.distribution_diameter_m, roughness=cfg.hazen_williams_c,
                    initial_status="Closed")
        wn.get_link(f"IT_{k - 1}_{k}").tag = "kind:intertie"

    # ---- wells (groundwater) and recovery wells
    def add_well(name: str, zone: int, col: int, aquifer_head: float, q_design: float, kind: str,
                 tank: str, on: float, off: float) -> None:
        target = node(zone, 0, col)
        ground = wn.get_node(target).elevation
        aq, head_node = f"{name}_AQ", f"{name}_HEAD"
        x, y = wn.get_node(target).coordinates
        wn.add_reservoir(aq, base_head=aquifer_head, coordinates=(x + 40, y - 120))
        wn.add_junction(head_node, elevation=ground, coordinates=(x + 40, y - 60))
        wn.get_node(head_node).tag = f"zone:{zone}"
        sdd = _cooper_jacob_drawdown(q_design, transmissivity_m2d, storativity, well_radius_m, 7.0)
        h_design = zone_hgl_mid(zone) - (aquifer_head - sdd) + 8.0
        _single_point_curve(wn, f"{name}_CURVE", q_design, h_design)
        wn.add_pump(name, aq, head_node, "HEAD", f"{name}_CURVE")
        wn.get_link(name).tag = f"kind:{kind},zone:{zone}"
        wn.add_pipe(f"{name}_MAIN", head_node, target, length=300, diameter=0.3, roughness=cfg.hazen_williams_c)
        vc.tank_rules.append(TankLevelRule(name, tank, on, off))

    # Flat regional water table: depth to water is static_depth at the bottom of the slope and grows upslope.
    water_table = cfg.base_elevation_m - aquifer_static_depth_m
    for zone, count in sorted(cfg.wells_per_zone.items()):
        if zone > cfg.zones:
            continue
        cols = np.linspace(1, C - 2, count + 2)[1:-1].round().astype(int)
        for i, col in enumerate(cols, start=1):
            name = f"GW{zone}_{i}"
            add_well(name, zone, int(col), water_table, cfg.well_design_flow_m3s, "well",
                     f"T{zone}", on=4.5 - 0.6 * (i - 1), off=7.5 - 0.3 * (i - 1))
            vc.wells[name] = f"{name}_AQ"
    for i in range(1, cfg.recovery_wells + 1):
        name = f"RW{i}"
        col = min(C - 1, 1 + 2 * (i - 1))
        head = water_table + mound_height_m
        add_well(name, 1, col, head, cfg.recovery_well_design_flow_m3s, "recovery_well", "T1",
                 on=4.5 - 0.6 * (i - 1), off=7.5 - 0.3 * (i - 1))
        vc.recovery_wells[name] = f"{name}_AQ"

    # ---- reclaimed-water system (separate, non-potable)
    wrf_head = cfg.base_elevation_m - 5.0
    wn.add_reservoir("WRF", base_head=wrf_head, coordinates=(-1200.0, 600.0))
    wn.add_junction("RCL_PS", elevation=wrf_head, coordinates=(-1100.0, 600.0))
    wn.add_junction("RCL_DIS", elevation=wrf_head, coordinates=(-1050.0, 600.0))
    wn.add_pipe("RCL_SUC", "WRF", "RCL_PS", length=30, diameter=0.35, roughness=130)
    segs = max(2, int(round(cfg.reclaimed_pipeline_km)))
    seg_len = cfg.reclaimed_pipeline_km * 1000 / segs
    user_elev = cfg.base_elevation_m + 8.0
    prev = "RCL_DIS"
    for s in range(1, segs + 1):
        n = RECLAIMED_USER_NODE if s == segs else f"RCL_J{s}"
        elev = wrf_head + (user_elev - wrf_head) * s / segs
        wn.add_junction(n, elevation=elev, coordinates=(-1050.0 - 150 * s, 600.0 + 250 * s))
        wn.get_node(n).tag = "zone:reclaimed"
        wn.add_pipe(f"RCL_PIPE{s}", prev, n, length=seg_len, diameter=0.30, roughness=130)
        prev = n
    rt_base = user_elev + 30.0
    rcl_avg = sum(u.avg_m3_per_day for u in demand.large_users if u.reclaimed) / SECONDS_PER_DAY
    rt_vol = max(500.0, 8 * 3600 * rcl_avg)
    wn.add_tank(RECLAIMED_TANK, elevation=rt_base, init_level=4.5, min_level=1.0, max_level=8.0,
                diameter=round(math.sqrt(4 * rt_vol / 7.0 / math.pi), 2),
                coordinates=(-1050.0 - 150 * segs, 700.0 + 250 * segs))
    wn.get_node(RECLAIMED_TANK).tag = "zone:reclaimed"
    wn.add_pipe("RCL_TANK_INLET", RECLAIMED_USER_NODE, RECLAIMED_TANK, length=50, diameter=0.3, roughness=130)
    rq = cfg.reclaimed_design_flow_m3s
    rh = (rt_base + 4.5) - wrf_head + 8.0
    _single_point_curve(wn, "RCL_CURVE", rq, rh)
    for i in (1, 2):
        p = f"RCL_P{i}"
        wn.add_pump(p, "RCL_PS", "RCL_DIS", "HEAD", "RCL_CURVE")
        wn.get_link(p).tag = "kind:reclaimed"
    vc.tank_rules += [TankLevelRule("RCL_P1", RECLAIMED_TANK, 4.0, 7.0),
                      TankLevelRule("RCL_P2", RECLAIMED_TANK, 2.5, 6.0)]

    apply_tank_rules(wn, vc.tank_rules)
    initialize_statuses(wn, vc.tank_rules)
    apply_valve_rules(wn, vc.valve_rules)
    return vc
