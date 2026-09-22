"""Load and validate EPANET networks.

AquaOS metadata lives in EPANET ``[TAGS]`` so it survives any ``.inp`` round trip. A utility can add the same tags
to its own model:

* nodes: ``zone:<int>`` (pressure zone); multiple tags are comma-separated (``;`` starts an EPANET comment)
* links: ``kind:<well|recovery_well|high_service|booster|reclaimed>``, ``zone:<int>``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import wntr

from aquaos.data.provenance import Provenance, file_sha256


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class LoadedNetwork:
    wn: wntr.network.WaterNetworkModel
    provenance: Provenance
    path: Path | None = None


def parse_tags(tag: str | None) -> dict[str, str]:
    """``"zone:2,kind:well"`` -> ``{"zone": "2", "kind": "well"}``."""
    out: dict[str, str] = {}
    if not tag:
        return out
    for part in str(tag).split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def zone_map(wn: wntr.network.WaterNetworkModel) -> dict[str, int | None]:
    """Pressure zone of each junction, from ``zone:<n>`` tags (``None`` if untagged)."""
    out: dict[str, int | None] = {}
    for name, node in wn.junctions():
        z = parse_tags(node.tag).get("zone")
        out[name] = int(z) if z is not None and z.lstrip("-").isdigit() else None
    return out


def zone_labels(wn: wntr.network.WaterNetworkModel) -> dict[str, str | None]:
    """Raw zone tag of each junction (e.g. ``"2"`` or ``"reclaimed"``), for reporting."""
    return {name: parse_tags(node.tag).get("zone") for name, node in wn.junctions()}


def link_kind(wn: wntr.network.WaterNetworkModel, name: str) -> str | None:
    return parse_tags(wn.get_link(name).tag).get("kind")


def load_inp(path: str | Path, provenance: Provenance | None = None) -> LoadedNetwork:
    """Load any EPANET ``.inp`` file. Provenance defaults to 'user-supplied, unknown'."""
    path = Path(path)
    wn = wntr.network.WaterNetworkModel(str(path))
    prov = provenance or Provenance(
        title=f"EPANET network {path.name}", kind="assumption",
        notes="User-supplied network; origin, calibration and data vintage not recorded",
    )
    prov = prov.model_copy(update={"sha256": file_sha256(path)})
    return LoadedNetwork(wn, prov, path)


def validate_network(wn: wntr.network.WaterNetworkModel) -> ValidationReport:
    rep = ValidationReport()
    if wn.num_reservoirs + wn.num_tanks == 0:
        rep.errors.append("network has no reservoirs or tanks (no source of water)")
    for name, t in wn.tanks():
        if not (t.min_level <= t.init_level <= t.max_level):
            rep.errors.append(f"tank {name}: init level {t.init_level} outside [{t.min_level}, {t.max_level}]")
    for name, p in wn.pumps():
        if p.pump_type == "HEAD" and p.pump_curve_name is None:
            rep.errors.append(f"pump {name}: HEAD pump without curve")
    for name, j in wn.junctions():
        if j.elevation != j.elevation:  # NaN
            rep.errors.append(f"junction {name}: elevation is NaN")
    g = wn.to_graph().to_undirected()
    sources = set(wn.reservoir_name_list) | set(wn.tank_name_list)
    for comp in nx.connected_components(g):
        if not comp & sources:
            demand_nodes = [n for n in comp if n in wn.junction_name_list]
            rep.errors.append(f"{len(demand_nodes)} junction(s) not connected to any source, e.g. "
                              f"{sorted(demand_nodes)[:3]}")
    zones = zone_map(wn)
    untagged = sum(1 for z in zones.values() if z is None)
    if untagged:
        rep.warnings.append(f"{untagged} junction(s) have no zone tag; zone-level reporting will group them as "
                            f"'untagged'")
    return rep


def write_inp(wn: wntr.network.WaterNetworkModel, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wntr.network.write_inpfile(wn, str(path), units="LPS")
    return path
