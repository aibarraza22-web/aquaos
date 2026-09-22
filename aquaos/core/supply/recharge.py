"""Long-term storage credit ledger for aquifer recharge and recovery.

Deposits earn credits at the statutory fraction (A.R.S. 45-852.01(C): 95% base case, loaded from ``params/``).
Recovery debits 100% of the volume recovered (45-852.01(E)(1)).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aquaos.core.params import Param, scalar_param
from aquaos.core.scenario import RechargeConfig
from aquaos.data.provenance import Provenance, synthetic


class InsufficientCredits(ValueError):
    pass


@dataclass
class RechargeLedger:
    balance_af: float
    credit_fraction: Param
    provenance: Provenance
    entries: list[tuple[str, float]] = field(default_factory=list)

    def deposit(self, stored_af: float, label: str = "recharge") -> float:
        credit = stored_af * float(self.credit_fraction.value)
        self.balance_af += credit
        self.entries.append((label, credit))
        return credit

    def recover(self, recovered_af: float, label: str = "recovery", strict: bool = False) -> float:
        """Debit recovered water. Non-strict mode lets the balance go negative so the shortfall is reported."""
        if strict and recovered_af > self.balance_af + 1e-9:
            raise InsufficientCredits(f"recovering {recovered_af:.1f} af exceeds balance {self.balance_af:.1f} af")
        self.balance_af -= recovered_af
        self.entries.append((label, -recovered_af))
        return self.balance_af

    @property
    def overdrawn(self) -> bool:
        return self.balance_af < -1e-9


def recharge_ledger(cfg: RechargeConfig) -> RechargeLedger:
    path, key = cfg.credit_fraction_param.split("#")
    frac = scalar_param(key, path)
    prov = synthetic(
        "Recharge credit balance",
        f"Scenario input: starting balance {cfg.credit_balance_af} af (synthetic utility)",
        units={"balance_af": "acre-feet"}, parents=(frac.provenance,),
    )
    return RechargeLedger(cfg.credit_balance_af, frac, prov)
