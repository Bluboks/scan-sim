from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from scan_sim import process_directory, simulate_scan
from scan_sim.config import SimulationConfig
from scan_sim.rng import derive_seed


def test_same_seed_gives_identical_output(
    document: NDArray[np.uint8], medium: SimulationConfig
) -> None:
    a, pa = simulate_scan(document, medium, seed=123)
    b, pb = simulate_scan(document, medium, seed=123)
    assert np.array_equal(a, b)
    assert pa == pb


def test_different_seed_gives_different_output(
    document: NDArray[np.uint8], medium: SimulationConfig
) -> None:
    a, pa = simulate_scan(document, medium, seed=123)
    b, pb = simulate_scan(document, medium, seed=124)
    assert not np.array_equal(a, b)
    assert pa["rotation_deg"] != pb["rotation_deg"]


def test_variant_seed_is_stable_and_separator_independent() -> None:
    # Golden value: if this changes, every previously generated dataset changes too.
    assert derive_seed("sub/b.png", 1000, 3) == 5029257726398529537
    assert derive_seed("sub\\b.png", 1000, 3) == derive_seed("sub/b.png", 1000, 3)
    assert derive_seed("sub/b.png", 1000, 4) != derive_seed("sub/b.png", 1000, 3)


def test_worker_count_does_not_change_files(
    input_dir: Path, tmp_path: Path, medium: SimulationConfig
) -> None:
    serial = process_directory(input_dir, tmp_path / "s", medium, 2, 7, 1, progress=False)
    parallel = process_directory(input_dir, tmp_path / "p", medium, 2, 7, 2, progress=False)
    assert not serial.failures and not parallel.failures
    names = sorted(p.relative_to(tmp_path / "s") for p in serial.written)
    assert names == sorted(p.relative_to(tmp_path / "p") for p in parallel.written)
    for name in names:
        assert (tmp_path / "s" / name).read_bytes() == (tmp_path / "p" / name).read_bytes()
