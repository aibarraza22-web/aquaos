import datetime as dt
import math

import numpy as np
import pandas as pd
import pytest

from aquaos.core import params
from aquaos.core.scenario import AquiferConfig, CapConfig, GroundwaterConfig, RechargeConfig
from aquaos.core.supply.cap import cap_allocation
from aquaos.core.supply.groundwater import drawdown, groundwater_budget, pumped_volume_m3, theis_well_function
from aquaos.core.supply.recharge import InsufficientCredits, recharge_ledger
from aquaos.core.units import af_per_year_to_m3s


def cap(**kw) -> CapConfig:
    base = {"contract_af_per_year": 6000, "shortage_condition": "cy2026_tier1", "mi_reduction_fraction": 0.0}
    return CapConfig(**{**base, **kw})


def test_shortage_params_are_primary_sourced():
    t1 = params.shortage_condition("cy2026_tier1")
    og = params.shortage_condition("cy2027_2028_operating_guidelines")
    assert t1.value == 512000 and t1.provenance.kind == "primary" and "cap-az.com" in t1.provenance.source_url
    assert og.value == 760000 and og.provenance.kind == "primary" and "usbr.gov" in og.provenance.source_url
    hyp = params.shortage_condition("hypothetical_1maf_az_reduction")
    assert hyp.provenance.synthetic
    with pytest.raises(KeyError):
        params.shortage_condition("tier_99")


def test_cap_delivery_monotone_in_reduction():
    deliveries = [cap_allocation(cap(mi_reduction_fraction=f)).delivered_af for f in (0.0, 0.1, 0.25, 0.5, 1.0)]
    assert deliveries == sorted(deliveries, reverse=True)
    assert deliveries[0] == 6000 and deliveries[-1] == 0


def test_implied_cut_and_provenance():
    a = cap_allocation(cap())
    assert a.implied_cap_wide_cut_fraction == pytest.approx(0.30, abs=0.001)
    b = cap_allocation(cap(shortage_condition="cy2027_2028_operating_guidelines"))
    assert b.implied_cap_wide_cut_fraction > a.implied_cap_wide_cut_fraction
    assert a.provenance.synthetic  # contract and M&I share are assumptions


def test_daily_limits_average_to_annual_and_cap_wtp():
    a = cap_allocation(cap())
    days = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(365)]
    mean = np.mean([a.daily_limit_m3s(d) for d in days])
    assert mean == pytest.approx(af_per_year_to_m3s(6000), rel=0.01)
    july = [dt.date(2026, 7, d) for d in range(13, 20)]
    assert a.wtp_setting_m3s(july) == min(a.wtp_capacity_m3s, a.daily_limit_m3s(july[0]))
    tight = cap_allocation(cap(mi_reduction_fraction=0.5))
    assert tight.wtp_setting_m3s(july) < a.wtp_setting_m3s(july)


def test_groundwater_budget_assessment():
    g = groundwater_budget(GroundwaterConfig(ama="phoenix", annual_allowance_af=2500, pumped_to_date_af=1300))
    assert g.remaining_af == 1200 and g.provenance.synthetic
    pr = g.pro_rata_af(dt.date(2026, 7, 13), 7)
    assert pr == pytest.approx(1200 * 7 / 172)
    ok = g.assess(1233.48 * 10, dt.date(2026, 7, 13), 7)
    assert not ok["exceeds_pro_rata"] and not ok["exceeds_remaining_allowance"]
    bad = g.assess(1233.48 * 1300, dt.date(2026, 7, 13), 7)
    assert bad["exceeds_remaining_allowance"] and bad["exceeds_pro_rata"]
    over = groundwater_budget(GroundwaterConfig(ama="pinal", annual_allowance_af=100, pumped_to_date_af=150))
    assert over.remaining_af == 0


def test_theis_constant_pumping_matches_analytic():
    aq = AquiferConfig(transmissivity_m2_per_day=800, storativity=0.1, well_radius_m=0.2,
                       regional_decline_m_per_year=0.0)
    idx = pd.date_range("2026-07-13", periods=97, freq="15min")
    q = pd.DataFrame({"W": 0.04}, index=idx)
    dd = drawdown(q, {"W": (0.0, 0.0)}, aq)
    t_days = 1.0
    u = 0.2**2 * 0.1 / (4 * 800 * t_days)
    expected = 0.04 * 86400 / (4 * math.pi * 800) * float(theis_well_function(np.array([u]))[0])
    assert dd["W"].iloc[-1] == pytest.approx(expected, rel=1e-6)
    assert dd["W"].is_monotonic_increasing


def test_interference_and_recovery():
    aq = AquiferConfig(regional_decline_m_per_year=0.0)
    idx = pd.date_range("2026-07-13", periods=193, freq="15min")
    on = pd.Series(0.04, index=idx)
    on.iloc[96:] = 0.0  # pump for a day, then stop
    alone = drawdown(pd.DataFrame({"A": on}), {"A": (0, 0)}, aq)
    pair = drawdown(pd.DataFrame({"A": on, "B": on}), {"A": (0, 0), "B": (300, 0)}, aq)
    assert (pair["A"] >= alone["A"] - 1e-12).all() and pair["A"].max() > alone["A"].max()
    assert alone["A"].iloc[-1] < 0.2 * alone["A"].max()  # recovery after shut-off


def test_pumped_volume_left_riemann():
    idx = pd.date_range("2026-07-13", periods=5, freq="900s")
    f = pd.DataFrame({"A": [1.0, 1.0, -0.5, 1.0, 99.0]}, index=idx)
    assert pumped_volume_m3(f, 900) == 3 * 900


def test_recharge_ledger_statutory_fractions():
    led = recharge_ledger(RechargeConfig(credit_balance_af=100))
    assert led.credit_fraction.value == 0.95 and led.credit_fraction.provenance.kind == "primary"
    assert led.deposit(100) == pytest.approx(95)
    led.recover(50)
    assert led.balance_af == pytest.approx(145) and not led.overdrawn
    with pytest.raises(InsufficientCredits):
        led.recover(1000, strict=True)
    led.recover(1000)
    assert led.overdrawn
