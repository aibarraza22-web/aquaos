"""AquaOS Arizona: an open water-infrastructure operating system for the desert Southwest."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

__version__ = "0.1.0"


@lru_cache(maxsize=1)
def code_fingerprint() -> str:
    """sha256 over the package's Python sources. Stored with every run so a result can be traced to the exact
    code that produced it, even when the version number has not changed."""
    root = Path(__file__).parent
    h = hashlib.sha256()
    for f in sorted(root.rglob("*.py")):
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()
