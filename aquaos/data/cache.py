"""Offline-first download cache.

Each cached file sits next to a ``<name>.provenance.json`` sidecar that records its source URL, retrieval date,
license, units, and sha256. After the first fetch AquaOS works offline. Set ``AQUAOS_OFFLINE=1`` to forbid network
access entirely. A cache miss then raises instead of fetching.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from aquaos.data.provenance import Provenance, file_sha256

USER_AGENT = "Mozilla/5.0 (compatible; AquaOS/0.1; open water research)"


class OfflineCacheMiss(RuntimeError):
    """Raised when data is not cached and network access is disabled."""


def default_cache_dir() -> Path:
    return Path(os.environ.get("AQUAOS_CACHE", Path.cwd() / ".aquaos_cache"))


@dataclass
class CachedFile:
    path: Path
    provenance: Provenance


class DataCache:
    def __init__(self, root: str | Path | None = None, offline: bool | None = None) -> None:
        self.root = Path(root) if root is not None else default_cache_dir()
        self.offline = offline if offline is not None else os.environ.get("AQUAOS_OFFLINE") == "1"

    def _paths(self, name: str) -> tuple[Path, Path]:
        path = self.root / name
        return path, path.with_name(path.name + ".provenance.json")

    def get(self, name: str) -> CachedFile | None:
        path, meta = self._paths(name)
        if path.exists() and meta.exists():
            return CachedFile(path, Provenance.model_validate_json(meta.read_text()))
        return None

    def put(self, name: str, content: bytes, provenance: Provenance) -> CachedFile:
        """Store ``content`` with its provenance. The sha256 and (if missing) retrieval date are filled in."""
        path, meta = self._paths(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        update: dict[str, object] = {"sha256": file_sha256(path)}
        if provenance.retrieved is None:
            update["retrieved"] = dt.date.today()
        prov = provenance.model_copy(update=update)
        meta.write_text(json.dumps(prov.model_dump(mode="json"), indent=2))
        return CachedFile(path, prov)

    def fetch(self, name: str, url: str, provenance: Provenance, *, refresh: bool = False,
              timeout: float = 60.0) -> CachedFile:
        """Return the cached file, downloading it first if needed.

        ``provenance`` is a template. ``source_url`` is forced to ``url`` and ``retrieved`` is set to today.
        """
        if not refresh and (hit := self.get(name)) is not None:
            return hit
        if self.offline:
            raise OfflineCacheMiss(f"{name} is not cached and AQUAOS_OFFLINE=1 (source: {url})")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URLs come from the registry
            content = resp.read()
        prov = provenance.model_copy(update={"source_url": url, "retrieved": dt.date.today()})
        return self.put(name, content, prov)
