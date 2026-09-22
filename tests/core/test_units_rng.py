import pytest

from aquaos.core import units as u
from aquaos.core.rng import stream


def test_roundtrips():
    assert u.psi_to_m(u.m_to_psi(12.3)) == pytest.approx(12.3)
    assert u.m3_to_af(u.af_to_m3(7.0)) == pytest.approx(7.0)
    assert u.f_to_c(u.c_to_f(43.3)) == pytest.approx(43.3)
    assert u.mgd_to_m3s(1.0) == pytest.approx(0.043812636, rel=1e-6)
    assert u.m3s_to_mgd(u.mgd_to_m3s(2.5)) == pytest.approx(2.5)


def test_known_values():
    assert u.m_to_psi(1.0) == pytest.approx(1.4223, rel=1e-3)
    assert pytest.approx(1233.48, rel=1e-5) == u.M3_PER_AF
    assert u.af_per_year_to_m3s(1.0) == pytest.approx(1233.48 / (365 * 86400), rel=1e-5)
    assert u.j_to_kwh(3.6e6) == 1.0
    assert u.m3s_to_gpm(u.M3_PER_GAL / 60) == pytest.approx(1.0)


def test_streams_are_independent_and_reproducible():
    a1 = stream(1, "a").random(5)
    a2 = stream(1, "a").random(5)
    b = stream(1, "b").random(5)
    c = stream(2, "a").random(5)
    assert (a1 == a2).all()
    assert not (a1 == b).all() and not (a1 == c).all()
