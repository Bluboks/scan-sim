"""Seed derivation and per-stage random streams.

A variant seed comes from a stable hash of (relative input path, base seed, variant
index), so results do not depend on processing order, worker count, or Python's
per-process ``hash()`` salt. Each pipeline stage draws from its own stream derived
from that one seed, so changing one stage's parameters does not reshuffle the
random draws of every other stage.
"""

from __future__ import annotations

import hashlib

import numpy as np

# Fixed stage identifiers. Never renumber: that would change every existing output.
_STAGE_IDS = {
    "printer": 1,
    "paper": 2,
    "geometry": 3,
    "scanner": 4,
    "artifacts": 5,
    "encoding": 6,
}


def derive_seed(relative_path: str, base_seed: int, variant: int) -> int:
    """Return a 63-bit seed that is stable across machines and Python processes."""
    key = f"{relative_path.replace(chr(92), '/')}\x00{base_seed}\x00{variant}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") >> 1


def stage_rng(seed: int, stage: str) -> np.random.Generator:
    return np.random.default_rng([seed, _STAGE_IDS[stage]])


def sample(value: float | tuple[float, float], rng: np.random.Generator) -> float:
    """A fixed number is returned as is; a ``(min, max)`` pair is sampled uniformly."""
    if isinstance(value, tuple):
        low, high = value
        return float(rng.uniform(low, high)) if high > low else float(low)
    return float(value)


def sample_int(value: int | tuple[int, int], rng: np.random.Generator) -> int:
    """Like :func:`sample` for integers; both ends of a range are inclusive."""
    if isinstance(value, tuple):
        low, high = value
        return int(rng.integers(low, high + 1))
    return int(value)
