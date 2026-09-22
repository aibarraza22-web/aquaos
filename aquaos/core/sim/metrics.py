"""Post-simulation metrics: continuity (mass balance), pressure service levels, tank behaviour, pump energy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import wntr

from aquaos.core.network.loader import link_kind, zone_labels
from aquaos.core.units import RHO_WATER, G, m_to_psi


@dataclass
class MassBalance:
    max_abs_residual_m3s: float
    max_rel_residual: float
    tank_volume_error_m3: dict[str, float]
    tank_volume_error_rel: dict[str, float]
    total_source_m3: float
    total_demand_m3: float
    storage_change_m3: float

    @property
    def closure_error_rel(self) -> float:
        """(sources - demand - storage change) / sources over the whole run."""
        if self.total_source_m3 <= 0:
            return 0.0
        return (self.total_source_m3 - self.total_demand_m3 - self.storage_change_m3) / self.total_source_m3


def tank_volume(wn: wntr.network.WaterNetworkModel, tank: str, level: np.ndarray | pd.Series) -> np.ndarray:
    t = wn.get_node(tank)
    if t.vol_curve is not None:
        curve = np.asarray(t.vol_curve.points, dtype=float)
        return np.interp(np.asarray(level, dtype=float), curve[:, 0], curve[:, 1])
    return np.pi * (t.diameter / 2) ** 2 * np.asarray(level, dtype=float)


def tank_levels(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults) -> pd.DataFrame:
    heads = results.node["head"][wn.tank_name_list]
    elev = pd.Series({t: wn.get_node(t).elevation for t in wn.tank_name_list})
    return heads - elev


def mass_balance(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults,
                 step_s: float) -> MassBalance:
    """Two independent checks.

    1. Instantaneous continuity: the sum of all nodal demands (junction consumption, reservoir supply as negative,
       tank net inflow) is zero at every reported time.
    2. Storage consistency: each tank's volume change from its level trajectory equals its integrated net inflow.
    """
    d = results.node["demand"]
    total = d.sum(axis=1)
    junction = d[wn.junction_name_list]
    scale = max(float(junction.sum(axis=1).abs().max()), 1e-12)
    levels = tank_levels(wn, results)
    vol_err, vol_rel = {}, {}
    storage_change = 0.0
    for t in wn.tank_name_list:
        v = tank_volume(wn, t, levels[t])
        dv_levels = float(v[-1] - v[0])
        dv_flow = float(d[t].iloc[:-1].sum() * step_s)
        storage_change += dv_levels
        vol_err[t] = dv_levels - dv_flow
        throughput = float(d[t].iloc[:-1].abs().sum() * step_s)
        vol_rel[t] = abs(vol_err[t]) / throughput if throughput > 0 else 0.0
    sources = -d[wn.reservoir_name_list].iloc[:-1].sum().sum() * step_s
    demand = junction.iloc[:-1].sum().sum() * step_s
    return MassBalance(
        max_abs_residual_m3s=float(total.abs().max()),
        max_rel_residual=float(total.abs().max() / scale),
        tank_volume_error_m3=vol_err, tank_volume_error_rel=vol_rel,
        total_source_m3=float(sources), total_demand_m3=float(demand), storage_change_m3=storage_change,
    )


@dataclass
class UnmetDemand:
    volume_m3: float
    fraction: float
    node_hours: float  # node-hours with delivered < 95% of requested
    worst_nodes: dict[str, float]


def unmet_demand(requested_m3s: pd.DataFrame, delivered_m3s: pd.DataFrame, step_s: float,
                 threshold: float = 0.95) -> UnmetDemand:
    """Requested (demand model) vs delivered (hydraulics) at demand nodes. Non-zero only under PDD stress."""
    req = requested_m3s.to_numpy()[:-1]
    dlv = delivered_m3s[requested_m3s.columns].to_numpy()[: len(req)]
    short = np.clip(req - dlv, 0, None)
    vol = float(short.sum() * step_s)
    total = float(req.sum() * step_s)
    per_node = pd.Series(short.sum(axis=0) * step_s, index=requested_m3s.columns)
    low = (dlv < threshold * req) & (req > 1e-9)
    return UnmetDemand(vol, vol / total if total else 0.0, float(low.sum() * step_s / 3600.0),
                       {str(k): float(v) for k, v in per_node[per_node > 0].nlargest(5).round(1).items()})


def demand_junctions(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults) -> list[str]:
    d = results.node["demand"][wn.junction_name_list]
    return [n for n in wn.junction_name_list if float(d[n].max()) > 1e-9]


def pressure_summary(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults,
                     min_psi: float, service_psi: float, max_psi: float) -> pd.DataFrame:
    """Per-zone pressure statistics (psi) at demand junctions."""
    nodes = demand_junctions(wn, results)
    p = results.node["pressure"][nodes].apply(m_to_psi)
    zones = zone_labels(wn)
    rows = []
    step_h = _step_hours(p.index)
    for z in sorted({zones.get(n) for n in nodes}, key=lambda x: (x is None, not str(x).isdigit(), str(x))):
        cols = [n for n in nodes if zones.get(n) == z]
        v = p[cols].to_numpy()
        rows.append({
            "zone": "untagged" if z is None else str(z),
            "nodes": len(cols),
            "min_psi": float(v.min()), "p05_psi": float(np.percentile(v, 5)),
            "median_psi": float(np.median(v)), "max_psi": float(v.max()),
            "node_hours_below_min": float((v < min_psi).sum() * step_h),
            "node_hours_below_service": float((v < service_psi).sum() * step_h),
            "node_hours_above_max": float((v > max_psi).sum() * step_h),
        })
    return pd.DataFrame(rows).set_index("zone")


def _step_hours(index: pd.Index) -> float:
    if len(index) < 2:
        return 0.0
    dt = index[1] - index[0]
    seconds = dt.total_seconds() if hasattr(dt, "total_seconds") else float(dt)
    return seconds / 3600.0


def tank_summary(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults) -> pd.DataFrame:
    lv = tank_levels(wn, results)
    rows = []
    for t in wn.tank_name_list:
        tk = wn.get_node(t)
        s = lv[t]
        span = tk.max_level - tk.min_level
        rows.append({
            "tank": t, "min_level_m": float(s.min()), "max_level_m": float(s.max()),
            "start_level_m": float(s.iloc[0]), "end_level_m": float(s.iloc[-1]),
            "design_min_m": tk.min_level, "design_max_m": tk.max_level,
            "hours_at_min": float((s <= tk.min_level + 0.01 * span).sum() * _step_hours(lv.index)),
            "hours_at_max": float((s >= tk.max_level - 0.01 * span).sum() * _step_hours(lv.index)),
        })
    return pd.DataFrame(rows).set_index("tank")


def pump_power_kw(wn: wntr.network.WaterNetworkModel, results: wntr.sim.SimulationResults,
                  efficiency: dict[str, float]) -> pd.DataFrame:
    """Electrical power per pump: rho * g * Q * head gain / wire-to-water efficiency."""
    flows = results.link["flowrate"]
    heads = results.node["head"]
    out = {}
    for name, pump in wn.pumps():
        q = flows[name].clip(lower=0)
        dh = (heads[pump.end_node_name] - heads[pump.start_node_name]).clip(lower=0)
        out[name] = RHO_WATER * G * q * dh / efficiency.get(name, 0.75) / 1000.0
    return pd.DataFrame(out)


def energy_summary(wn: wntr.network.WaterNetworkModel, power_kw: pd.DataFrame,
                   flows: pd.DataFrame, step_s: float) -> pd.DataFrame:
    h = step_s / 3600.0
    rows = []
    for name in power_kw.columns:
        kwh = float(power_kw[name].iloc[:-1].sum() * h)
        vol = float(flows[name].iloc[:-1].clip(lower=0).sum() * step_s)
        rows.append({
            "pump": name, "kind": link_kind(wn, name) or "pump", "kwh": kwh, "volume_m3": vol,
            "kwh_per_m3": kwh / vol if vol > 0 else float("nan"),
            "peak_kw": float(power_kw[name].max()),
            "run_hours": float((flows[name].iloc[:-1] > 1e-6).sum() * h),
        })
    return pd.DataFrame(rows).set_index("pump")
