"""Seeded randomness. Every stochastic component draws from a named child stream of the scenario seed, so adding
a new random component never changes the draws of existing ones."""

from __future__ import annotations

import hashlib

import numpy as np


def stream(seed: int, name: str) -> np.random.Generator:
    """Independent generator for component ``name`` under scenario ``seed``."""
    key = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "little")
    return np.random.default_rng(np.random.SeedSequence([seed, key]))
