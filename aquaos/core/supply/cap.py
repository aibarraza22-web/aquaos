"""CAP allocation under a Colorado River shortage condition.

Chain of evidence:

1. The Arizona-wide reduction for the chosen condition comes from ``params/colorado_river_shortage.yaml``
   (primary sources).
2. How much of that reaches the city's M&I subcontract depends on CAP's priority system and on
   intrastate agreements. That is an explicit scenario ASSUMPTION (``mi_reduction_fraction``).
3. For context, the report shows the CAP-wide cut implied if CAP absorbed the whole Arizona reduction (derived).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from aquaos.core.params import Param, derived_param, shortage_condition
from aquaos.core.scenario import CapConfig
from aquaos.core.units import af_per_year_to_m3s
from aquaos.data.provenance import Provenance, assumption


@dataclass
class CapAllocation:
    condition: str
    az_reduction: Param
    cap_normal_supply: Param
    contract_af: float
    mi_reduction_fraction: float
    delivered_af: float
    monthly_factor: list[float]
    wtp_capacity_m3s: float
    provenance: Provenance

    @property
    def implied_cap_wide_cut_fraction(self) -> float:
        """Arizona reduction / CAP normal supply: the cut if CAP users absorbed all of it (context only)."""
        return float(self.az_reduction.value) / float(self.cap_normal_supply.value)

    def daily_limit_m3s(self, day: dt.date) -> float:
        mean = sum(self.monthly_factor) / 12.0
        return af_per_year_to_m3s(self.delivered_af) * self.monthly_factor[day.month - 1] / mean

    def wtp_setting_m3s(self, days: list[dt.date]) -> float:
        """Constant plant throughput for a run: the tightest of plant capacity and the daily CAP limits."""
        return min([self.wtp_capacity_m3s] + [self.daily_limit_m3s(d) for d in days])


def cap_allocation(cfg: CapConfig) -> CapAllocation:
    az = shortage_condition(cfg.shortage_condition, cfg.shortage_params)
    normal = derived_param("cap_normal_supply_af", cfg.shortage_params)
    mi = assumption(
        f"M&I subcontract reduction fraction = {cfg.mi_reduction_fraction}",
        "Share of the city's CAP subcontract cut under the chosen shortage condition. Depends on CAP priority "
        "pools and intrastate agreements; not published per subcontractor in the sources used.",
    )
    contract = assumption(
        f"CAP M&I subcontract = {cfg.contract_af_per_year} af/yr",
        "Valley City is synthetic; the subcontract volume is a scenario input.",
    )
    prov = Provenance(
        title=f"CAP delivery to city under '{cfg.shortage_condition}'", kind="derived",
        derivation="contract x (1 - mi_reduction_fraction), shaped by monthly delivery factors",
        parents=(az.provenance, normal.provenance, mi, contract),
        units={"delivered_af": "acre-feet per year"},
    )
    return CapAllocation(
        condition=cfg.shortage_condition, az_reduction=az, cap_normal_supply=normal,
        contract_af=cfg.contract_af_per_year, mi_reduction_fraction=cfg.mi_reduction_fraction,
        delivered_af=cfg.contract_af_per_year * (1.0 - cfg.mi_reduction_fraction),
        monthly_factor=list(cfg.monthly_delivery_factor), wtp_capacity_m3s=cfg.wtp_capacity_m3s,
        provenance=prov,
    )
