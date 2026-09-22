import datetime as dt

import pytest

from aquaos.data.connectors import noaa, usbr
from aquaos.data.provenance import synthetic

PROV = synthetic("fixture", "trimmed test fixture")


def test_parse_daily_fixture(fixtures):
    rec = noaa.load_daily_csv(fixtures / "noaa_ghcnd_USW00023183_2023.csv", PROV)
    df = rec.data
    assert list(df.columns) == ["tmax_c", "tmin_c"]
    assert df.index.min().year == 2023 and len(df) >= 360
    july = df.loc["2023-07"]
    assert (july["tmax_c"] > july["tmin_c"]).all()
    assert july["tmax_c"].mean() > 40  # July 2023 in Phoenix


def test_parse_hourly_fixture_local_time(fixtures):
    rec = noaa.load_hourly_csv(fixtures / "noaa_isd_72278023183_2023-07-08_21.csv", PROV)
    s = rec.data["temp_c"]
    assert str(s.index.tz) == "America/Phoenix"
    assert s.index.freq is not None or len(s) > 300
    by_hour = s.groupby(s.index.hour).mean()
    assert by_hour.idxmax() in range(13, 18)  # afternoon peak in local time
    assert by_hour.idxmin() in range(4, 8)


def test_url_builders():
    u = noaa.daily_url("USW00023183", dt.date(2020, 1, 1), dt.date(2020, 1, 31))
    assert "daily-summaries" in u and "USW00023183" in u and "units=metric" in u
    assert noaa.hourly_url("72278023183", dt.date(2023, 7, 1), dt.date(2023, 7, 2)).count("global-hourly") == 1
    assert usbr.archive_url(2026, 7).endswith("/2026/JUL26.pdf")


def test_parse_lake_mead_excerpt(fixtures):
    text = (fixtures / "usbr_24mo_jul2026_lake_mead_excerpt.txt").read_text()
    study, df = usbr.parse_lake_mead(text)
    assert study == "July 2026 Most Probable 24-Month Study"
    assert df.loc["2026-12-01", "elevation_ft"] == pytest.approx(1037.31)
    assert df.loc["2026-12-01", "storage_kaf"] == pytest.approx(6794)
    assert len(df) == 36


def test_parse_lake_mead_missing_table():
    with pytest.raises(ValueError):
        usbr.parse_lake_mead("no table here")
