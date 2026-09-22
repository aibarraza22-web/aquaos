"""Temperature drivers for demand: observed series, a synthetic weather generator fitted to observations, and a
heat-wave perturbation generator.

The synthetic generator is SYNTHETIC even though its statistics come from NOAA observations. Its provenance
record says both.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from aquaos.core.params import load_yaml
from aquaos.data.provenance import Provenance, synthetic

LOCAL_TZ = "America/Phoenix"


@dataclass
class TemperatureSeries:
    """Hourly air temperature (degC), tz-aware index in America/Phoenix."""

    data: pd.Series
    provenance: Provenance

    def at(self, index: pd.DatetimeIndex) -> pd.Series:
        """Interpolate to arbitrary timestamps (e.g. a 15-minute hydraulic step)."""
        s = self.data.reindex(self.data.index.union(index)).interpolate("time").ffill().bfill()
        return s.reindex(index)


# ---------------------------------------------------------------- fitting
def fit_climate(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict[str, Any]:
    """Fit monthly generator statistics from daily TMAX/TMIN (degC) and, optionally, a diurnal shape from hourly
    observations."""
    df = daily.dropna().copy()
    df["month"] = pd.DatetimeIndex(df.index).month
    clim = df.groupby("month")[["tmax_c", "tmin_c"]].mean()
    df = df.join(clim, on="month", rsuffix="_clim")
    df["amax"] = df["tmax_c"] - df["tmax_c_clim"]
    df["amin"] = df["tmin_c"] - df["tmin_c_clim"]
    months: dict[int, dict[str, float]] = {}
    for m in sorted(int(x) for x in df["month"].unique()):
        g = df[df["month"] == m]
        amax, amin = g["amax"], g["amin"]
        ar1 = float(amax.autocorr(1)) if len(amax) > 3 else 0.0
        months[m] = {
            "tmax_mean_c": round(float(clim["tmax_c"][m]), 3),
            "tmin_mean_c": round(float(clim["tmin_c"][m]), 3),
            "tmax_anom_sd_c": round(float(amax.std()), 3),
            "tmin_anom_sd_c": round(float(amin.std()), 3),
            "tmax_anom_ar1": round(max(0.0, min(0.99, ar1)), 3),
            "tmin_tmax_anom_corr": round(float(amax.corr(amin)), 3),
        }
    shape = default_diurnal_shape()
    if hourly is not None and len(hourly):
        shape = fit_diurnal_shape(hourly["temp_c"])
    return {"months": months, "diurnal_shape": [round(x, 4) for x in shape]}


def default_diurnal_shape() -> list[float]:
    h = np.arange(24)
    raw = 0.5 - 0.5 * np.cos(2 * np.pi * (h - 5) / 24 * 0.9)
    return list(np.clip(raw, 0, 1))


def fit_diurnal_shape(hourly: pd.Series) -> list[float]:
    """Mean normalized diurnal cycle: (T(h) - daily min) / (daily max - daily min), min-max scaled to [0, 1]."""
    s = hourly.dropna()
    idx = pd.DatetimeIndex(s.index)
    day = idx.normalize()
    tmin = s.groupby(day).transform("min")
    tmax = s.groupby(day).transform("max")
    rng = (tmax - tmin).where(lambda x: x > 1.0)
    norm = ((s - tmin) / rng).dropna()
    shape = norm.groupby(pd.DatetimeIndex(norm.index).hour).mean().reindex(range(24)).interpolate().to_numpy()
    shape = (shape - shape.min()) / (shape.max() - shape.min())
    return [float(x) for x in shape]


def write_climate_params(path: str | Path, fit: dict[str, Any], provenance: Provenance) -> None:
    doc = {"provenance": provenance.model_dump(mode="json", exclude_none=True), **fit}
    Path(path).write_text(yaml.safe_dump(doc, sort_keys=False))


def load_climate_params(path: str | Path) -> tuple[dict[str, Any], Provenance]:
    data = load_yaml(path)
    prov = Provenance.model_validate(data.pop("provenance"))
    data["months"] = {int(k): v for k, v in data["months"].items()}
    return data, prov


# ---------------------------------------------------------------- generation
def _hourly_from_daily(tmax: np.ndarray, tmin: np.ndarray, shape: np.ndarray) -> np.ndarray:
    """Piecewise diurnal interpolation that is continuous across midnight.

    Before the morning minimum an hour belongs to the previous day's cooling limb. Between minimum and peak it
    warms toward today's max. After the peak it cools toward tomorrow's min.
    """
    h_min, h_peak = int(np.argmin(shape)), int(np.argmax(shape))
    n = len(tmax)
    out = np.empty(n * 24)
    for d in range(n):
        for h in range(24):
            if h < h_min:
                lo, hi = tmin[d], tmax[max(d - 1, 0)]
            elif h <= h_peak:
                lo, hi = tmin[d], tmax[d]
            else:
                lo, hi = tmin[min(d + 1, n - 1)], tmax[d]
            out[d * 24 + h] = lo + (hi - lo) * shape[h]
    return out


def synthetic_temperature(start: dt.datetime, days: int, climate: dict[str, Any], climate_prov: Provenance,
                          rng: np.random.Generator) -> TemperatureSeries:
    """Generate an hourly series. Daily max/min anomalies follow a monthly AR(1) process."""
    start_day = pd.Timestamp(start).normalize()
    dates = pd.date_range(start_day, periods=days, freq="D")
    tmax = np.empty(days)
    tmin = np.empty(days)
    a = 0.0
    for i, d in enumerate(dates):
        p = climate["months"][d.month]
        phi, sd = p["tmax_anom_ar1"], p["tmax_anom_sd_c"]
        a = phi * a + sd * np.sqrt(1 - phi**2) * rng.standard_normal()
        rho = p["tmin_tmax_anom_corr"]
        bmin = rho * a / sd * p["tmin_anom_sd_c"] if sd > 0 else 0.0
        bmin += p["tmin_anom_sd_c"] * np.sqrt(max(0.0, 1 - rho**2)) * rng.standard_normal()
        tmax[i] = p["tmax_mean_c"] + a
        tmin[i] = min(p["tmin_mean_c"] + bmin, tmax[i] - 1.0)
    shape = np.asarray(climate["diurnal_shape"], dtype=float)
    idx = pd.date_range(start_day, periods=days * 24, freq="h", tz=LOCAL_TZ)
    series = pd.Series(_hourly_from_daily(tmax, tmin, shape), index=idx, name="temp_c")
    prov = synthetic(
        "Synthetic hourly temperature (AR(1) weather generator)",
        "Monthly AR(1) daily max/min anomalies + fitted diurnal shape; statistics from parent record",
        units={"temp_c": "degC"}, parents=(climate_prov,),
    )
    return TemperatureSeries(series, prov)


def heat_wave_envelope(index: pd.DatetimeIndex, t0: pd.Timestamp, start_day: float, duration_days: float,
                       ramp_days: float) -> np.ndarray:
    """0..1 intensity: linear ramp up, plateau, linear ramp down, all inside [start, start+duration]."""
    days = (index - t0).total_seconds().to_numpy() / 86400.0 - start_day
    w = np.zeros(len(index))
    inside = (days >= 0) & (days <= duration_days)
    ramp = max(min(ramp_days, duration_days / 2), 1e-9)
    w[inside] = np.minimum(1.0, np.minimum(days[inside], duration_days - days[inside]) / ramp)
    return np.clip(w, 0, 1)


def apply_heat_wave(temp: TemperatureSeries, t0: dt.datetime, start_day: float, duration_days: float,
                    tmax_delta_c: float, tmin_delta_c: float, ramp_days: float,
                    diurnal_shape: list[float]) -> TemperatureSeries:
    """Raise daytime peaks by ``tmax_delta_c`` and overnight minima by ``tmin_delta_c`` (warm nights drive
    Arizona heat-wave demand and grid stress)."""
    s = temp.data
    idx = pd.DatetimeIndex(s.index)
    shape = np.asarray(diurnal_shape)[idx.hour]
    t0_ts = pd.Timestamp(t0).tz_localize(LOCAL_TZ) if pd.Timestamp(t0).tzinfo is None else pd.Timestamp(t0)
    w = heat_wave_envelope(idx, t0_ts, start_day, duration_days, ramp_days)
    delta = w * (tmin_delta_c + (tmax_delta_c - tmin_delta_c) * shape)
    prov = synthetic(
        "Heat-wave perturbation",
        f"+{tmax_delta_c} degC peak / +{tmin_delta_c} degC night, days {start_day}..{start_day + duration_days}, "
        f"ramp {ramp_days} d, applied to parent series",
        units={"temp_c": "degC"}, parents=(temp.provenance,),
    )
    return TemperatureSeries((s + delta).rename("temp_c"), prov)
