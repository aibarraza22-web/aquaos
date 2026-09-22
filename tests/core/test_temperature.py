import datetime as dt

import numpy as np
import pandas as pd
import pytest

from aquaos.core.demand import temperature as T
from aquaos.core.params import PARAMS_DIR
from aquaos.core.rng import stream
from aquaos.data.connectors import noaa
from aquaos.data.provenance import synthetic


@pytest.fixture(scope="module")
def climate():
    return T.load_climate_params(PARAMS_DIR / "phoenix_climate.yaml")


def test_committed_climate_params_are_derived_from_noaa(climate):
    data, prov = climate
    assert prov.kind == "derived" and not prov.synthetic
    assert all("ncei.noaa.gov" in (p.source_url or "") for p in prov.parents)
    assert set(data["months"]) == set(range(1, 13))
    assert data["months"][7]["tmax_mean_c"] > data["months"][1]["tmax_mean_c"] + 15
    assert len(data["diurnal_shape"]) == 24 and min(data["diurnal_shape"]) == 0.0


def test_fit_climate_from_fixture(fixtures):
    prov = synthetic("f", "fixture")
    d = noaa.load_daily_csv(fixtures / "noaa_ghcnd_USW00023183_2023.csv", prov).data
    h = noaa.load_hourly_csv(fixtures / "noaa_isd_72278023183_2023-07-08_21.csv", prov).data
    fit = T.fit_climate(d, h)
    jul = fit["months"][7]
    assert 40 < jul["tmax_mean_c"] < 50 and 0 <= jul["tmax_anom_ar1"] < 1
    assert int(np.argmax(fit["diurnal_shape"])) in range(13, 18)
    assert T.fit_climate(d)["diurnal_shape"] == pytest.approx(T.default_diurnal_shape(), abs=1e-4)


def test_synthetic_temperature_reproducible_and_plausible(climate):
    data, prov = climate
    a = T.synthetic_temperature(dt.datetime(2026, 7, 13), 10, data, prov, stream(1, "t"))
    b = T.synthetic_temperature(dt.datetime(2026, 7, 13), 10, data, prov, stream(1, "t"))
    c = T.synthetic_temperature(dt.datetime(2026, 7, 13), 10, data, prov, stream(2, "t"))
    assert a.data.equals(b.data) and not a.data.equals(c.data)
    assert a.provenance.synthetic
    assert len(a.data) == 240 and str(a.data.index.tz) == "America/Phoenix"
    assert a.data.min() > 20 and a.data.max() < 55
    assert a.data.diff().abs().max() < 6  # continuous across midnight


def test_heat_wave_only_inside_window_and_raises_nights(climate):
    data, prov = climate
    t0 = dt.datetime(2026, 7, 13)
    base = T.synthetic_temperature(t0, 10, data, prov, stream(1, "t"))
    hw = T.apply_heat_wave(base, t0, start_day=2, duration_days=4, tmax_delta_c=4, tmin_delta_c=5,
                           ramp_days=1, diurnal_shape=data["diurnal_shape"])
    delta = hw.data - base.data
    idx = base.data.index
    days = (idx - idx[0]).total_seconds() / 86400
    assert np.allclose(delta[(days < 2) | (days > 6)], 0)
    plateau = delta[(days >= 3) & (days <= 5)]
    assert plateau.max() == pytest.approx(5.0, abs=0.01)  # night delta at shape minimum
    assert plateau.min() >= 4.0 - 1e-9
    assert hw.provenance.synthetic and hw.provenance.parents[0] == base.provenance


def test_envelope_ramps():
    idx = pd.date_range("2026-07-01", periods=24 * 8, freq="h", tz="America/Phoenix")
    w = T.heat_wave_envelope(idx, idx[0], 1.0, 4.0, 1.0)
    assert w.max() == 1.0 and w[:24].max() == 0.0
    assert 0 < w[36] < 1  # halfway up the ramp


def test_at_interpolates(climate):
    data, prov = climate
    s = T.synthetic_temperature(dt.datetime(2026, 7, 13), 3, data, prov, stream(1, "t"))
    q = pd.date_range(s.data.index[0], periods=9, freq="15min")
    v = s.at(q)
    assert v.iloc[0] == s.data.iloc[0] and v.iloc[4] == pytest.approx(s.data.iloc[1])
    assert min(s.data.iloc[0], s.data.iloc[1]) <= v.iloc[2] <= max(s.data.iloc[0], s.data.iloc[1])
