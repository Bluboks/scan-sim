from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from scan_sim import process_file, simulate_scan
from scan_sim.config import SimulationConfig, load_config
from scan_sim.errors import InputImageError


def test_output_size_follows_scanner_dpi(document: NDArray[np.uint8]) -> None:
    at_300, _ = simulate_scan(document, load_config("office-medium")[0], 1)
    at_200, _ = simulate_scan(
        document, load_config("office-medium", overrides=["scanner.dpi=200"])[0], 1
    )
    assert at_300.shape == (240, 360, 3)
    assert at_200.shape == (160, 240, 3)


def test_file_dpi_metadata_sets_physical_size(tmp_path: Path, medium: SimulationConfig) -> None:
    src = tmp_path / "hi.png"
    Image.fromarray(np.full((480, 720, 3), 255, np.uint8)).save(src, dpi=(600, 600))
    out = tmp_path / "hi.jpg"
    meta = process_file(src, out, medium, 1)
    with Image.open(out) as img:
        assert img.size == (360, 240)  # 600 dpi page scanned at 300 dpi
        assert round(img.info["dpi"][0]) == 300
    assert meta["input_dpi"] == {"x": 600.0, "y": 600.0, "origin": "metadata"}


def test_transparent_background_becomes_paper(medium: SimulationConfig) -> None:
    rgba = np.zeros((200, 200, 4), dtype=np.uint8)  # fully transparent black
    out, _ = simulate_scan(rgba, medium, 1)
    assert out[20:-20, 20:-20].mean() > 235


def test_implausible_metadata_dpi_is_rejected_with_a_fix(
    tmp_path: Path, medium: SimulationConfig
) -> None:
    src = tmp_path / "a4_at_96.png"
    Image.fromarray(np.full((3508, 2480, 3), 255, np.uint8)).save(src, dpi=(96, 96))
    with pytest.raises(InputImageError, match="dpi_from_metadata=false"):
        process_file(src, tmp_path / "x.jpg", medium, 1)
    assert not (tmp_path / "x.jpg").exists()
