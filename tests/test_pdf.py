from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from scan_sim import process_directory
from scan_sim.batch import plan_jobs
from scan_sim.cli import main
from scan_sim.config import SimulationConfig
from scan_sim.errors import InputImageError


def write_pdf(path: Path, pages: list[NDArray[np.uint8]]) -> None:
    images = [Image.fromarray(p) for p in pages]
    images[0].save(path, save_all=True, append_images=images[1:], resolution=300)


def test_each_pdf_page_becomes_its_own_scans(
    tmp_path: Path, document: NDArray[np.uint8], medium: SimulationConfig
) -> None:
    src = tmp_path / "in"
    src.mkdir()
    blank = np.full_like(document, 255)
    write_pdf(src / "doc.pdf", [document, blank])
    report = process_directory(src, tmp_path / "out", medium, 2, 5, 1, progress=False)

    assert not report.failures
    names = sorted(p.name for p in report.written)
    assert names == [
        "doc_p001_scan_0001.jpg",
        "doc_p001_scan_0002.jpg",
        "doc_p002_scan_0001.jpg",
        "doc_p002_scan_0002.jpg",
    ]
    assert len({job.seed for job in report.jobs}) == 4
    page1 = np.asarray(Image.open(tmp_path / "out" / "doc_p001_scan_0001.jpg").convert("L"))
    page2 = np.asarray(Image.open(tmp_path / "out" / "doc_p002_scan_0001.jpg").convert("L"))
    assert page1.shape == (240, 360)  # 300 dpi page rendered at 600, scanned at 300
    assert page1.min() < 80 < page2.min(), "page 1 has toner, page 2 is blank paper"
    meta = json.loads((tmp_path / "out" / "doc_p002_scan_0001.json").read_text("utf-8"))
    assert meta["page"] == 2 and meta["input_dpi"]["origin"] == "pdf-render"


def test_multi_page_pdf_needs_an_output_directory(
    tmp_path: Path, document: NDArray[np.uint8], capsys: pytest.CaptureFixture[str]
) -> None:
    write_pdf(tmp_path / "two.pdf", [document, document])
    write_pdf(tmp_path / "one.pdf", [document])
    assert main([str(tmp_path / "two.pdf"), str(tmp_path / "x.jpg"), "--no-progress"]) == 2
    assert "has 2 pages" in capsys.readouterr().err
    assert main([str(tmp_path / "one.pdf"), str(tmp_path / "x.jpg"), "--no-progress"]) == 0
    assert (tmp_path / "x.jpg").is_file()


def test_unreadable_pdf_is_reported_before_any_work(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "bad.pdf").write_bytes(b"%PDF-1.7 truncated")
    with pytest.raises(InputImageError, match="cannot open PDF"):
        plan_jobs(tmp_path / "in", tmp_path / "out", 1, 0, "jpg")
