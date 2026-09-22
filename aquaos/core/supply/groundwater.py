"""Groundwater: an AMA-style annual pumping budget and well drawdown.

Budget: a scenario sets the annual allowance (standing in for the groundwater allowance in an Assured Water Supply
determination) and the volume already pumped this year. Pumping in a run is checked against both the remaining
annual allowance (hard limit) and the pro-rata share for the run period (soft limit).

Drawdown: Theis solution with superposition in time (variable pumping) and in space (interference between wells)
on top of a regional water-table trend. Assumes a confined, homogeneous, infinite aquifer at static level at the
start of the run. These simplifications are recorded in ``docs/limitations.md``.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.special import exp1

from aquaos.core.scenario import AquiferConfig, GroundwaterConfig
from aquaos.core.units import SECONDS_PER_DAY, m3_to_af
from aquaos.data.provenance import Provenance, synthetic


@dataclass
class GroundwaterBudget:
    ama: str
    annual_allowance_af: float
    pumped_to_date_af: float
    provenance: Provenance

    @property
    def remaining_af(self) -> float:
        return max(0.0, self.annual_allowance_af - self.pumped_to_date_af)

    def pro_rata_af(self, start: dt.date, days: float) -> float:
        """Share of the remaining allowance that belongs to a run of ``days`` starting on ``start``."""
        year_end = dt.date(start.year, 12, 31)
        days_left = (year_end - start).days + 1
        return self.remaining_af * min(1.0, days / days_left)

    def assess(self, pumped_m3: float, start: dt.date, days: float) -> dict[str, float | bool]:
        pumped_af = m3_to_af(pumped_m3)
        pro_rata = self.pro_rata_af(start, days)
        return {
            "pumped_af": pumped_af,
            "remaining_before_af": self.remaining_af,
            "pro_rata_af": pro_rata,
            "exceeds_remaining_allowance": pumped_af > self.remaining_af + 1e-9,
            "exceeds_pro_rata": pumped_af > pro_rata + 1e-9,
        }


def groundwater_budget(cfg: GroundwaterConfig) -> GroundwaterBudget:
    prov = synthetic(
        f"AMA-style groundwater budget ({cfg.ama} AMA label)",
        f"Scenario input: allowance {cfg.annual_allowance_af} af/yr, pumped to date {cfg.pumped_to_date_af} af. "
        "Not an ADWR determination.",
        units={"annual_allowance_af": "acre-feet per year"},
    )
    return GroundwaterBudget(cfg.ama, cfg.annual_allowance_af, cfg.pumped_to_date_af, prov)


def theis_well_function(u: np.ndarray) -> np.ndarray:
    return exp1(np.maximum(u, 1e-12))


def drawdown(pumping_m3s: pd.DataFrame, coords: dict[str, tuple[float, float]], aq: AquiferConfig) -> pd.DataFrame:
    """Drawdown (m) at each pumping well from all wells' variable pumping.

    ``pumping_m3s``: index = time, columns = well names, values = pumping rate (m3/s, >= 0).
    """
    t_s = (pumping_m3s.index - pumping_m3s.index[0]).total_seconds().to_numpy()
    t_d = t_s / SECONDS_PER_DAY
    T, S = aq.transmissivity_m2_per_day, aq.storativity
    wells = list(pumping_m3s.columns)
    q = pumping_m3s.to_numpy() * SECONDS_PER_DAY  # m3/day
    dq = np.diff(np.vstack([np.zeros((1, q.shape[1])), q]), axis=0)  # rate changes at each step
    n = len(t_d)
    lag = t_d[:, None] - t_d[None, :]  # (n, n), t_i - t_k
    mask = lag > 0
    out = np.zeros((n, len(wells)))
    for i_obs, w_obs in enumerate(wells):
        x0, y0 = coords[w_obs]
        for j_src, w_src in enumerate(wells):
            if not np.any(dq[:, j_src]):
                continue
            if w_src == w_obs:
                r = aq.well_radius_m
            else:
                x1, y1 = coords[w_src]
                r = max(math.hypot(x1 - x0, y1 - y0), aq.well_radius_m)
            u = np.where(mask, r**2 * S / (4 * T * np.where(mask, lag, 1.0)), np.inf)
            W = np.where(mask, theis_well_function(u), 0.0)
            out[:, i_obs] += W @ dq[:, j_src] / (4 * math.pi * T)
    regional = aq.regional_decline_m_per_year * t_d / 365.0
    return pd.DataFrame(out + regional[:, None], index=pumping_m3s.index, columns=wells)


def pumped_volume_m3(flows_m3s: pd.DataFrame, step_s: float) -> float:
    """Left-Riemann volume, matching EPANET's explicit integration between reporting steps."""
    return float(flows_m3s.iloc[:-1].clip(lower=0).to_numpy().sum() * step_s)

