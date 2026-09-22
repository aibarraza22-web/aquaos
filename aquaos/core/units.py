"""Unit conversions. AquaOS computes in SI and converts only at report, API, and UI boundaries."""

from __future__ import annotations

G = 9.80665  # m/s^2
RHO_WATER = 997.0  # kg/m^3 at ~25 C

M_PER_FT = 0.3048
M3_PER_GAL = 3.785411784e-3
M3_PER_AF = 1233.48183754752
PSI_PER_M_HEAD = 9806.65 / 6894.757293168  # psi per metre of water head (rho = 1000 kg/m^3, standard g)
SECONDS_PER_DAY = 86400.0


def m_to_psi(head_m: float) -> float:
    return head_m * PSI_PER_M_HEAD


def psi_to_m(psi: float) -> float:
    return psi / PSI_PER_M_HEAD


def m3s_to_gpm(q: float) -> float:
    return q / M3_PER_GAL * 60.0


def m3s_to_mgd(q: float) -> float:
    return q * SECONDS_PER_DAY / M3_PER_GAL / 1e6


def mgd_to_m3s(mgd: float) -> float:
    return mgd * 1e6 * M3_PER_GAL / SECONDS_PER_DAY


def m3_to_af(v: float) -> float:
    return v / M3_PER_AF


def af_to_m3(af: float) -> float:
    return af * M3_PER_AF


def af_per_year_to_m3s(af: float) -> float:
    return af_to_m3(af) / (365.0 * SECONDS_PER_DAY)


def j_to_kwh(j: float) -> float:
    return j / 3.6e6


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0
