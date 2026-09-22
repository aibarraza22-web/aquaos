"""Temperature-dependent nodal demand.

For each (node, customer class) allocation:

    q(t) = q_ref * diurnal_class(hour(t)) * (1 + beta_class * max(0, T_driver(t) - T_ref)) * noise(t)

``q_ref`` is the average demand at or below the reference temperature. ``T_driver`` is either the hourly air
temperature (evaporative-cooling loads such as data centers) or an EWMA of daily maxima (outdoor irrigation and
household use responding to recent heat). ``noise`` is a mean-one lognormal AR(1) per node. All coefficients are
SYNTHETIC unless a scenario supplies calibrated values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import wntr

from aquaos.core.demand.temperature import TemperatureSeries
from aquaos.core.network.loader import zone_map
from aquaos.core.rng import stream
from aquaos.core.scenario import DemandClass, DemandConfig
from aquaos.core.units import SECONDS_PER_DAY
from aquaos.data.provenance import Provenance, synthetic


@dataclass(frozen=True)
class Allocation:
    node: str
    demand_class: str
    q_ref_m3s: float


@dataclass
class DemandSeries:
    """Nodal demand (m3/s) on the simulation time grid, plus the allocations that produced it."""

    data: pd.DataFrame
    allocations: list[Allocation]
    provenance: Provenance


def _center_node(wn: wntr.network.WaterNetworkModel, nodes: list[str]) -> str:
    xy = np.array([wn.get_node(n).coordinates for n in nodes], dtype=float)
    c = xy.mean(axis=0)
    return nodes[int(np.argmin(((xy - c) ** 2).sum(axis=1)))]


def allocate(wn: wntr.network.WaterNetworkModel, cfg: DemandConfig, seed: int,
             reclaimed_node: str | None = None) -> list[Allocation]:
    """Spread residential and commercial demand over zoned junctions and place large users.

    Networks without zone tags (e.g. a utility ``.inp``) keep their own base demands as the residential class.
    """
    rng = stream(seed, "demand/allocation")
    zones = zone_map(wn)
    potable = sorted(n for n, z in zones.items() if z is not None)
    allocs: list[Allocation] = []
    if potable:
        res_total = cfg.population * cfg.residential_m3_per_capita_day * cfg.growth_factor / SECONDS_PER_DAY
        com_total = res_total * cfg.commercial_fraction_of_residential
        w = rng.lognormal(0.0, 0.35, size=len(potable))
        w /= w.sum()
        for n, wi in zip(potable, w, strict=True):
            allocs.append(Allocation(n, "residential", float(res_total * wi)))
        k = max(1, int(round(cfg.commercial_node_fraction * len(potable))))
        com_nodes = sorted(rng.choice(potable, size=k, replace=False).tolist())
        cw = rng.lognormal(0.0, 0.5, size=k)
        cw /= cw.sum()
        for n, wi in zip(com_nodes, cw, strict=True):
            allocs.append(Allocation(n, "commercial", float(com_total * wi)))
    else:
        for n, j in wn.junctions():
            base = sum(d.base_value for d in j.demand_timeseries_list)
            if base > 0:
                allocs.append(Allocation(n, "residential", float(base * cfg.growth_factor)))
    for u in cfg.large_users:
        q = u.avg_m3_per_day / SECONDS_PER_DAY
        if u.reclaimed:
            if reclaimed_node is None or reclaimed_node not in wn.node_name_list:
                raise ValueError(f"large user {u.name} is reclaimed but the network has no reclaimed user node")
            allocs.append(Allocation(reclaimed_node, u.demand_class, q))
            continue
        in_zone = [n for n in potable if zones[n] == u.zone]
        if not in_zone:
            raise ValueError(f"large user {u.name}: no junctions tagged zone:{u.zone}")
        allocs.append(Allocation(_center_node(wn, in_zone), u.demand_class, q))
    return allocs


def _diurnal(cls: DemandClass, index: pd.DatetimeIndex) -> np.ndarray:
    pat = np.asarray(cls.diurnal + [cls.diurnal[0]])
    frac_hour = index.hour + index.minute / 60.0 + index.second / 3600.0
    return np.interp(frac_hour, np.arange(25), pat)


def temperature_driver(cls: DemandClass, index: pd.DatetimeIndex, temp: TemperatureSeries) -> np.ndarray:
    if cls.temp_driver == "hourly":
        return temp.at(index).to_numpy()
    daily_max = temp.data.resample("D").max()
    ewma = daily_max.ewm(halflife=pd.Timedelta(days=cls.ewma_days),  # type: ignore[arg-type]
                         times=pd.Series(daily_max.index, index=daily_max.index)).mean()
    by_day = ewma.reindex(index.normalize(), method="ffill")
    return by_day.to_numpy()


def class_multiplier(cls: DemandClass, index: pd.DatetimeIndex, temp: TemperatureSeries) -> np.ndarray:
    t = temperature_driver(cls, index, temp)
    return _diurnal(cls, index) * (1.0 + cls.temp_coef_per_c * np.maximum(0.0, t - cls.t_ref_c))


def _ar1_lognormal(n: int, sd: float, phi: float, rng: np.random.Generator) -> np.ndarray:
    if sd <= 0:
        return np.ones(n)
    e = np.empty(n)
    e[0] = rng.normal(0, sd)
    innov = rng.normal(0, sd * np.sqrt(1 - phi**2), size=n)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + innov[i]
    return np.exp(e - 0.5 * sd**2)


def build_demand(allocs: list[Allocation], cfg: DemandConfig, temp: TemperatureSeries,
                 index: pd.DatetimeIndex, seed: int) -> DemandSeries:
    step_h = (index[1] - index[0]).total_seconds() / 3600.0 if len(index) > 1 else 1.0
    mult = {name: class_multiplier(c, index, temp) for name, c in cfg.classes.items()}
    cols: dict[str, np.ndarray] = {}
    for a in allocs:
        cls = cfg.classes[a.demand_class]
        rng = stream(seed, f"demand/noise/{a.node}/{a.demand_class}")
        phi = cls.noise_ar1 ** step_h  # AR(1) coefficient specified per hour
        q = a.q_ref_m3s * mult[a.demand_class] * _ar1_lognormal(len(index), cls.noise_sd, phi, rng)
        cols[a.node] = cols.get(a.node, np.zeros(len(index))) + q
    df = pd.DataFrame(cols, index=index)
    prov = synthetic(
        "Nodal demand time series",
        "aquaos.core.demand.model.build_demand: diurnal x temperature response x AR(1) noise; coefficients from "
        "scenario demand classes", units={"*": "m3/s"}, parents=(temp.provenance,),
    )
    return DemandSeries(df, allocs, prov)


def apply_to_network(wn: wntr.network.WaterNetworkModel, demand: DemandSeries, step_s: int) -> None:
    """Replace junction demands with one pattern per demand node (base = mean, pattern = q(t) / mean).

    Junctions without an allocation get zero demand. For a utility network, the new series *replaces* its
    original patterns, and the originals are recorded in the demand allocation instead.
    """
    wn.options.time.pattern_timestep = step_s
    wn.options.time.pattern_start = 0
    for name, j in wn.junctions():
        j.demand_timeseries_list.clear()
        if name not in demand.data.columns:
            j.add_demand(0.0, None)
    for name in demand.data.columns:
        q = demand.data[name].to_numpy()
        mean = float(q.mean())
        pat = f"D_{name}"
        if pat in wn.pattern_name_list:
            wn.remove_pattern(pat)
        wn.add_pattern(pat, list(q / mean) if mean > 0 else [0.0] * len(q))
        wn.get_node(name).add_demand(mean, pat)
