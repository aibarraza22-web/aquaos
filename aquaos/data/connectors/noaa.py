"""NOAA NCEI Access Data Service connector (GHCN-Daily and Global Hourly / ISD).

API docs: https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation
"""

from __future__ import annotations

import datetime as dt
import io
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from aquaos.data.cache import DataCache
from aquaos.data.provenance import Provenance

BASE_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
LICENSE = "U.S. Government work (NOAA NCEI); no copyright restrictions in the U.S."
LOCAL_TZ = "America/Phoenix"

# Phoenix Sky Harbor International Airport
PHX_GHCND = "USW00023183"
PHX_ISD = "72278023183"

# ISD quality codes meaning "suspect" or "erroneous"; everything else is kept.
_ISD_BAD_QC = {"2", "3", "6", "7"}


@dataclass
class TemperatureRecord:
    data: pd.DataFrame
    provenance: Provenance


def daily_url(station: str, start: dt.date, end: dt.date) -> str:
    q = {"dataset": "daily-summaries", "stations": station, "startDate": start.isoformat(),
         "endDate": end.isoformat(), "dataTypes": "TMAX,TMIN", "format": "csv", "units": "metric",
         "includeStationName": "true"}
    return f"{BASE_URL}?{urlencode(q)}"


def hourly_url(station: str, start: dt.date, end: dt.date) -> str:
    q = {"dataset": "global-hourly", "stations": station, "startDate": start.isoformat(),
         "endDate": end.isoformat(), "dataTypes": "TMP", "format": "csv"}
    return f"{BASE_URL}?{urlencode(q)}"


def parse_daily(csv_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv_bytes))
    df["DATE"] = pd.to_datetime(df["DATE"])
    out = df.set_index("DATE")[["TMAX", "TMIN"]].rename(columns={"TMAX": "tmax_c", "TMIN": "tmin_c"})
    out.index.name = "date"
    return out.astype(float)


def parse_hourly(csv_bytes: bytes) -> pd.DataFrame:
    """Parse ISD ``TMP`` values ("+0320,1" means 32.0 °C with QC code 1) into an hourly local-time series.

    Stations file several reports per hour (METAR, synoptic). Valid values are averaged within each hour.
    """
    df = pd.read_csv(io.BytesIO(csv_bytes), dtype={"TMP": str})
    parts = df["TMP"].str.split(",", expand=True)
    raw = pd.to_numeric(parts[0], errors="coerce")
    qc = parts[1].astype(str)
    ok = (raw.abs() < 9999) & ~qc.isin(_ISD_BAD_QC)
    ts = pd.to_datetime(df["DATE"], utc=True)
    s = pd.Series((raw / 10.0).where(ok).to_numpy(), index=ts).dropna()
    hourly = s.tz_convert(LOCAL_TZ).resample("1h").mean().interpolate(limit=3)
    return hourly.to_frame("temp_c")


def fetch_daily(station: str, start: dt.date, end: dt.date, cache: DataCache | None = None) -> TemperatureRecord:
    cache = cache or DataCache()
    url = daily_url(station, start, end)
    template = Provenance(
        title=f"NOAA GHCN-Daily TMAX/TMIN, station {station}, {start}..{end}", kind="primary",
        source_url=url, retrieved=dt.date.today(), license=LICENSE,
        units={"tmax_c": "degC", "tmin_c": "degC"},
    )
    hit = cache.fetch(f"noaa/ghcnd_{station}_{start}_{end}.csv", url, template)
    return TemperatureRecord(parse_daily(hit.path.read_bytes()), hit.provenance)


def fetch_hourly(station: str, start: dt.date, end: dt.date, cache: DataCache | None = None) -> TemperatureRecord:
    cache = cache or DataCache()
    url = hourly_url(station, start, end)
    template = Provenance(
        title=f"NOAA Global Hourly (ISD) air temperature, station {station}, {start}..{end}", kind="primary",
        source_url=url, retrieved=dt.date.today(), license=LICENSE, units={"temp_c": "degC"},
        notes="Hourly mean of valid reports, converted from UTC to America/Phoenix; QC codes 2,3,6,7 dropped.",
    )
    hit = cache.fetch(f"noaa/isd_{station}_{start}_{end}.csv", url, template)
    return TemperatureRecord(parse_hourly(hit.path.read_bytes()), hit.provenance)


def load_hourly_csv(path: str | Path, provenance: Provenance) -> TemperatureRecord:
    """Load a previously saved hourly ISD CSV (for example a committed test fixture)."""
    return TemperatureRecord(parse_hourly(Path(path).read_bytes()), provenance)


def load_daily_csv(path: str | Path, provenance: Provenance) -> TemperatureRecord:
    return TemperatureRecord(parse_daily(Path(path).read_bytes()), provenance)
