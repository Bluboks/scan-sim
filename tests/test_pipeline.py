from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from scan_sim import process_file, simulate_scan
from scan_sim.cli import main
from scan_sim.config import SimulationConfig, load_config
from scan_sim.errors import ConfigError


def test_blank_paper_has_texture_not_flat_white(medium: SimulationConfig) -> None:
    blank = np.full((300, 300, 3), 255, dtype=np.uint8)
    out, _ = simulate_scan(blank, medium, 3)
    core = out[20:-20, 20:-20].astype(float)
    assert core.mean() < 254.5
    assert core.std() > 0.2


def test_printer_and_scanner_blur_are_separate_stages(document: NDArray[np.uint8]) -> None:
    sharp = [
        "printer.psf.sigma_x=0",
        "printer.psf.sigma_y=0",
        "scanner.psf.sigma_x=0",
        "scanner.psf.sigma_y=0",
    ]
    only_printer = [*sharp[2:], "printer.psf.sigma_x=3", "printer.psf.sigma_y=3"]
    only_scanner = [*sharp[:2], "scanner.psf.sigma_x=1.5", "scanner.psf.sigma_y=1.5"]

    def edge_width(overrides: list[str]) -> int:
        # Same seed: geometry and noise draws are identical, only the PSF differs.
        out, _ = simulate_scan(document, load_config(overrides=overrides)[0], 1)
        row = out[60:80, 100:140].mean(axis=(0, 2))  # right edge of the black block
        return int(((row > 40) & (row < 230)).sum())

    base = edge_width(sharp)
    assert edge_width(only_printer) > base
    assert edge_width(only_scanner) > base


def test_jpeg_is_encoded_once_with_recorded_quality(
    tmp_path: Path, document: NDArray[np.uint8], medium: SimulationConfig
) -> None:
    src = tmp_path / "doc.png"
    Image.fromarray(document).save(src, dpi=(300, 300))
    out = tmp_path / "doc_scan.jpg"
    meta = process_file(src, out, medium, 42, config_label="office-medium")
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar == json.loads(json.dumps(meta))
    assert sidecar["preset"] == "office-medium" and sidecar["seed"] == 42
    assert 90 <= sidecar["parameters"]["jpeg_quality"] <= 96
    pixels, _ = simulate_scan(document, medium, 42)
    with Image.open(out) as img:
        assert img.format == "JPEG"
        decoded = np.asarray(img.convert("RGB")).astype(int)
    # One JPEG pass at q>=90 stays within a few levels of the pre-encoding pixels.
    assert np.abs(decoded - pixels.astype(int)).mean() < 2.0


def test_set_override_and_validation_errors() -> None:
    cfg, _ = load_config(overrides=["geometry.rotation_deg=-0.5,0.5", "encoding.jpeg_quality=85"])
    assert cfg.geometry.rotation_deg == (-0.5, 0.5)
    assert cfg.encoding.jpeg_quality == 85
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(overrides=["geometry.rotation=1"])
    with pytest.raises(ConfigError, match="greater than max"):
        load_config(overrides=["geometry.rotation_deg=0.5,-0.5"])


def test_custom_config_extends_a_preset(tmp_path: Path) -> None:
    path = tmp_path / "custom.yaml"
    path.write_text("extends: office-clean\nscanner:\n  dpi: 200\n", encoding="utf-8")
    cfg, label = load_config(config_path=path)
    assert cfg.scanner.dpi == 200
    assert cfg.encoding.jpeg_quality == load_config("office-clean")[0].encoding.jpeg_quality
    assert label == str(path)


def test_cli_variants_naming_and_dry_run(input_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main([str(input_dir), str(out), "--variants", "2", "--dry-run"]) == 0
    assert not out.exists()
    assert main([str(input_dir), str(out), "--variants", "2", "--no-progress"]) == 0
    written = sorted(p.relative_to(out).as_posix() for p in out.rglob("*"))
    assert written == [
        "a_scan_0001.jpg",
        "a_scan_0001.json",
        "a_scan_0002.jpg",
        "a_scan_0002.json",
        "sub",
        "sub/b_scan_0001.jpg",
        "sub/b_scan_0001.json",
        "sub/b_scan_0002.jpg",
        "sub/b_scan_0002.json",
    ]


def test_cli_refuses_to_overwrite_or_collide(
    input_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert main([str(input_dir), str(out), "--no-progress"]) == 0
    assert main([str(input_dir), str(out), "--no-progress"]) == 2
    assert "--overwrite" in capsys.readouterr().err
    assert main([str(input_dir), str(out), "--no-progress", "--overwrite"]) == 0

    Image.fromarray(np.zeros((10, 10, 3), np.uint8)).save(input_dir / "a.jpg")
    assert main([str(input_dir), str(tmp_path / "o2"), "--dry-run"]) == 2
    assert "same name" in capsys.readouterr().err
    assert main([str(input_dir), str(input_dir / "out"), "--dry-run"]) == 2
    assert "inside input" in capsys.readouterr().err


def test_cli_reports_unreadable_input_and_exits_nonzero(
    input_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (input_dir / "broken.png").write_bytes(b"not an image")
    assert main([str(input_dir), str(tmp_path / "out"), "--no-progress"]) == 1
    err = capsys.readouterr().err
    assert "broken.png" in err and "cannot read image" in err
    assert "2 written, 1 failed" in err
