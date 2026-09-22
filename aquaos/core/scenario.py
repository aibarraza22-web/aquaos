"""Scenario schema, loading (with ``extends`` inheritance), and canonical hashing.

Policy inputs (shortage condition, CAP contract, groundwater allowance, credit balance) have no defaults. A
scenario must state them. Technical generator parameters have defaults, and those defaults are SYNTHETIC.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import aquaos
from aquaos.core.params import load_yaml, resolve_params_path
from aquaos.data.provenance import file_sha256

LOCAL_TZ = "America/Phoenix"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- time
class TimeConfig(_Model):
    start: dt.datetime = Field(description="Local (America/Phoenix) start time; naive values are taken as local")
    duration_days: float = Field(7.0, gt=0, le=366)
    hydraulic_step_s: int = Field(900, ge=60)
    report_step_s: int = Field(900, ge=60)

    @model_validator(mode="after")
    def _steps(self) -> TimeConfig:
        if self.report_step_s % self.hydraulic_step_s:
            raise ValueError("report_step_s must be a multiple of hydraulic_step_s")
        return self

    @property
    def duration_s(self) -> int:
        return int(round(self.duration_days * 86400))


# ---------------------------------------------------------------- network
class ValleyCityConfig(_Model):
    """Generator parameters for the synthetic Valley City network. All defaults are SYNTHETIC."""

    zones: int = Field(4, ge=3, le=5)
    grid_rows: int = Field(6, ge=2)
    grid_cols: int = Field(12, ge=3)
    spacing_m: float = 250.0
    base_elevation_m: float = 330.0
    zone_rise_m: float = 25.0
    zone_band_m: float = 20.0
    elevation_noise_m: float = 1.5
    tank_height_above_zone_top_m: float = 30.0
    tank_min_level_m: float = 1.0
    tank_max_level_m: float = 10.0
    tank_init_level_m: float = 6.5
    zone_tank_storage_hours: float = 12.0
    trunk_diameter_m: float = 0.40
    distribution_diameter_m: float = 0.20
    hazen_williams_c: float = 130.0
    cap_turnout_head_m: float = 365.0
    clearwell_base_m: float = 336.0
    wells_per_zone: dict[int, int] = Field(default_factory=lambda: {2: 3, 3: 2})
    well_design_flow_m3s: float = 0.040
    recovery_wells: int = 2
    recovery_well_design_flow_m3s: float = 0.035
    reclaimed_pipeline_km: float = 4.0
    reclaimed_design_flow_m3s: float = 0.05


class NetworkConfig(_Model):
    source: Literal["valley_city", "inp"] = "valley_city"
    inp_path: str | None = None
    valley_city: ValleyCityConfig = Field(default_factory=ValleyCityConfig)

    @model_validator(mode="after")
    def _inp(self) -> NetworkConfig:
        if self.source == "inp" and not self.inp_path:
            raise ValueError("network.source == 'inp' requires network.inp_path")
        return self


# ---------------------------------------------------------------- demand
class HeatWaveConfig(_Model):
    start_day: float = Field(ge=0, description="Days after scenario start")
    duration_days: float = Field(gt=0)
    tmax_delta_c: float = Field(description="Added to daily maximum temperature at full intensity")
    tmin_delta_c: float = Field(description="Added to overnight minimum at full intensity (warm nights)")
    ramp_days: float = Field(1.0, ge=0)


class TemperatureConfig(_Model):
    source: Literal["synthetic", "noaa_hourly", "csv"] = "synthetic"
    climate_params: str = "phoenix_climate.yaml"
    noaa_station: str = "72278023183"
    csv_path: str | None = None


class DemandClass(_Model):
    """Demand behaviour of a customer class. All defaults are SYNTHETIC coefficients."""

    diurnal: list[float] = Field(min_length=24, max_length=24)
    temp_coef_per_c: float = Field(0.0, description="Fractional demand increase per degC above t_ref_c")
    t_ref_c: float = 30.0
    temp_driver: Literal["daily_max_ewma", "hourly"] = "daily_max_ewma"
    ewma_days: float = 2.0
    noise_sd: float = 0.05
    noise_ar1: float = 0.8

    @field_validator("diurnal")
    @classmethod
    def _normalize(cls, v: list[float]) -> list[float]:
        m = sum(v) / 24.0
        if m <= 0:
            raise ValueError("diurnal pattern must have positive mean")
        if abs(m - 1.0) < 1e-9:
            return v  # already normalized; keeps dump/load (and therefore the scenario hash) stable
        return [round(x / m, 12) for x in v]


def _default_classes() -> dict[str, DemandClass]:
    residential = [0.55, 0.45, 0.40, 0.40, 0.50, 0.85, 1.35, 1.55, 1.40, 1.20, 1.05, 1.00,
                   0.98, 0.95, 0.95, 1.00, 1.10, 1.30, 1.50, 1.45, 1.30, 1.10, 0.85, 0.65]
    commercial = [0.45, 0.40, 0.40, 0.40, 0.50, 0.70, 0.95, 1.20, 1.35, 1.40, 1.40, 1.40,
                  1.40, 1.40, 1.40, 1.35, 1.25, 1.10, 0.95, 0.85, 0.75, 0.65, 0.55, 0.50]
    flat = [1.0] * 24
    return {
        "residential": DemandClass(diurnal=residential, temp_coef_per_c=0.015, t_ref_c=30.0),
        "commercial": DemandClass(diurnal=commercial, temp_coef_per_c=0.008, t_ref_c=30.0),
        "fab": DemandClass(diurnal=flat, temp_coef_per_c=0.003, t_ref_c=30.0, noise_sd=0.02),
        "data_center": DemandClass(diurnal=flat, temp_coef_per_c=0.030, t_ref_c=25.0,
                                   temp_driver="hourly", noise_sd=0.03),
        "reclaimed_industrial": DemandClass(diurnal=flat, temp_coef_per_c=0.010, t_ref_c=30.0, noise_sd=0.03),
    }


class LargeUser(_Model):
    name: str
    demand_class: str
    avg_m3_per_day: float = Field(gt=0)
    zone: int | None = Field(None, description="Pressure zone (potable) or None for the reclaimed system")
    reclaimed: bool = False


def _default_large_users() -> list[LargeUser]:
    return [
        LargeUser(name="fab_1", demand_class="fab", avg_m3_per_day=3000.0, zone=1),
        LargeUser(name="dc_1", demand_class="data_center", avg_m3_per_day=800.0, zone=2),
        LargeUser(name="reclaimed_user_1", demand_class="reclaimed_industrial", avg_m3_per_day=2500.0,
                  reclaimed=True),
    ]


class DemandConfig(_Model):
    population: int = Field(40000, gt=0)
    residential_m3_per_capita_day: float = 0.45
    commercial_fraction_of_residential: float = 0.25
    commercial_node_fraction: float = 0.2
    classes: dict[str, DemandClass] = Field(default_factory=_default_classes)
    large_users: list[LargeUser] = Field(default_factory=_default_large_users)
    temperature: TemperatureConfig = Field(default_factory=TemperatureConfig)
    heat_wave: HeatWaveConfig | None = None
    growth_factor: float = Field(1.0, gt=0, description="Multiplier on residential and commercial demand")

    @model_validator(mode="after")
    def _classes_exist(self) -> DemandConfig:
        for u in self.large_users:
            if u.demand_class not in self.classes:
                raise ValueError(f"large user {u.name}: unknown demand class {u.demand_class}")
        return self


# ---------------------------------------------------------------- supply
class CapConfig(_Model):
    contract_af_per_year: float = Field(gt=0, description="City's CAP M&I subcontract (scenario input)")
    shortage_condition: str = Field(description="Key into params/colorado_river_shortage.yaml")
    mi_reduction_fraction: float = Field(ge=0, le=1, description="ASSUMPTION: share of the city's CAP "
                                         "subcontract cut under the chosen condition")
    shortage_params: str = "colorado_river_shortage.yaml"
    wtp_capacity_m3s: float = Field(0.30, gt=0)
    monthly_delivery_factor: list[float] = Field(
        default_factory=lambda: [0.75, 0.75, 0.85, 0.95, 1.10, 1.25, 1.30, 1.25, 1.15, 1.00, 0.85, 0.80],
        min_length=12, max_length=12)


class AquiferConfig(_Model):
    """Lumped aquifer + Cooper-Jacob well drawdown. Defaults are SYNTHETIC."""

    transmissivity_m2_per_day: float = Field(800.0, gt=0)
    storativity: float = Field(0.10, gt=0, lt=1)
    static_depth_m: float = Field(110.0, gt=0, description="Depth to water below ground at scenario start")
    well_radius_m: float = Field(0.2, gt=0)
    regional_decline_m_per_year: float = 0.5


class GroundwaterConfig(_Model):
    ama: str = Field(description="Active Management Area label, e.g. 'phoenix'")
    annual_allowance_af: float = Field(gt=0, description="AMA-style annual groundwater pumping budget")
    pumped_to_date_af: float = Field(ge=0, description="Volume already pumped this calendar year at start")
    aquifer: AquiferConfig = Field(default_factory=AquiferConfig)


class RechargeConfig(_Model):
    credit_balance_af: float = Field(ge=0, description="Long-term storage credits available at start")
    credit_fraction_param: str = "recharge_credits.yaml#long_term_storage_credit_fraction"
    recharge_af_per_year: float = Field(0.0, ge=0)
    mound_height_m: float = Field(15.0, description="Water-table rise under the recharge site (SYNTHETIC)")


class SupplyConfig(_Model):
    cap: CapConfig
    groundwater: GroundwaterConfig
    recharge: RechargeConfig


# ---------------------------------------------------------------- hydraulics
class HydraulicsConfig(_Model):
    """Pressure-dependent demand (EPANET 2.2) is the default. With adequate pressure it equals demand-driven, and
    under stress it delivers less water instead of reporting non-physical negative pressures."""

    demand_model: Literal["PDD", "DD"] = "PDD"
    required_pressure_psi: float = Field(30.0, gt=0, description="Pressure for full demand delivery")
    minimum_pressure_psi: float = Field(5.0, ge=0, description="Pressure below which no demand is delivered")

    @model_validator(mode="after")
    def _order(self) -> HydraulicsConfig:
        if self.minimum_pressure_psi >= self.required_pressure_psi:
            raise ValueError("minimum_pressure_psi must be below required_pressure_psi")
        return self


# ---------------------------------------------------------------- energy & report
class EnergyConfig(_Model):
    pump_efficiency: float = Field(0.75, gt=0, le=1, description="Wire-to-water efficiency (SYNTHETIC)")
    well_pump_efficiency: float = Field(0.65, gt=0, le=1)


class ReportConfig(_Model):
    """Thresholds are configurable engineering choices, not regulatory citations."""

    min_pressure_psi: float = 20.0
    service_pressure_psi: float = 40.0
    max_pressure_psi: float = 120.0


class Scenario(_Model):
    name: str
    description: str = ""
    seed: int
    time: TimeConfig
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    demand: DemandConfig = Field(default_factory=DemandConfig)
    supply: SupplyConfig
    hydraulics: HydraulicsConfig = Field(default_factory=HydraulicsConfig)
    energy: EnergyConfig = Field(default_factory=EnergyConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    base_dir: str = Field(".", exclude=True, description="Directory relative paths resolve against")

    def resolve_path(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else Path(self.base_dir) / path

    def input_files(self) -> dict[str, Path]:
        """External files whose *content* affects results; their hashes enter the scenario hash."""
        files: dict[str, Path] = {
            "shortage_params": resolve_params_path(self.supply.cap.shortage_params),
            "credit_params": resolve_params_path(self.supply.recharge.credit_fraction_param.split("#")[0]),
        }
        t = self.demand.temperature
        if t.source == "synthetic":
            files["climate_params"] = resolve_params_path(t.climate_params)
        elif t.source == "csv" and t.csv_path:
            files["temperature_csv"] = self.resolve_path(t.csv_path)
        if self.network.source == "inp" and self.network.inp_path:
            files["inp"] = self.resolve_path(self.network.inp_path)
        return files

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def scenario_hash(self) -> str:
        h = hashlib.sha256()
        h.update(f"aquaos={aquaos.__version__}\n".encode())
        h.update(self.canonical_json().encode())
        for key, path in sorted(self.input_files().items()):
            digest = file_sha256(path) if path.exists() else "missing"
            h.update(f"\n{key}={digest}".encode())
        return h.hexdigest()


# ---------------------------------------------------------------- loading
def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_raw(path: Path, seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    path = path.resolve()
    if path in seen:
        raise ValueError(f"circular 'extends' chain: {' -> '.join(map(str, seen + (path,)))}")
    raw = load_yaml(path)
    parent = raw.pop("extends", None)
    if parent:
        base = _load_raw((path.parent / parent), seen + (path,))
        raw = _deep_merge(base, raw)
    return raw


def load_scenario(path: str | Path, overrides: dict[str, Any] | None = None) -> Scenario:
    path = Path(path)
    raw = _load_raw(path)
    if overrides:
        raw = _deep_merge(raw, overrides)
    raw["base_dir"] = str(path.resolve().parent)
    return Scenario.model_validate(raw)


def dump_scenario(scn: Scenario) -> str:
    return yaml.safe_dump(scn.model_dump(mode="json"), sort_keys=False)
