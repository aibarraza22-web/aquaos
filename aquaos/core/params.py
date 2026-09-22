"""Loading of provenance-tagged parameter files from ``params/``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aquaos.data.provenance import Provenance

PARAMS_DIR = Path(__file__).resolve().parents[2] / "params"


@dataclass(frozen=True)
class Param:
    value: Any
    provenance: Provenance


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return data


def resolve_params_path(name: str | Path) -> Path:
    p = Path(name)
    if p.is_absolute() or p.exists():
        return p
    return PARAMS_DIR / p


def shortage_condition(key: str, path: str | Path = "colorado_river_shortage.yaml") -> Param:
    """Arizona Colorado River reduction (af/yr) for a named shortage condition."""
    data = load_yaml(resolve_params_path(path))
    conds = data["conditions"]
    if key not in conds:
        raise KeyError(f"unknown shortage condition '{key}'; known: {sorted(conds)}")
    c = conds[key]
    return Param(float(c["az_reduction_af"]), Provenance.model_validate(c["provenance"]))


def derived_param(key: str, path: str | Path) -> Param:
    d = load_yaml(resolve_params_path(path))["derived"][key]
    return Param(d["value"], Provenance.model_validate(d["provenance"]))


def scalar_param(key: str, path: str | Path) -> Param:
    d = load_yaml(resolve_params_path(path))[key]
    return Param(d["value"], Provenance.model_validate(d["provenance"]))
