from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from scan_sim.rng import derive_seed  # noqa: E402
from scan_sim.web.app import create_app  # noqa: E402


def _png(document: NDArray[np.uint8]) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(document).save(buf, format="PNG", dpi=(300, 300))
    return buf.getvalue()


def test_upload_returns_downloadable_scans_with_cli_seeds(
    tmp_path: Path, document: NDArray[np.uint8]
) -> None:
    client = TestClient(create_app(tmp_path, samples_dir=None))
    res = client.post(
        "/api/jobs",
        files={"file": ("doc.png", _png(document), "image/png")},
        data={"preset": "office-clean", "seed": "9", "variants": "2"},
    )
    assert res.status_code == 200, res.text
    job = res.json()
    assert [v["seed"] for v in job["variants"]] == [
        str(derive_seed("doc.png", 9, v)) for v in (1, 2)
    ]
    scan = client.get(job["variants"][1]["image"])
    assert scan.status_code == 200
    assert Image.open(io.BytesIO(scan.content)).size == tuple(job["size"])
    meta = json.loads(client.get(job["variants"][1]["metadata"]).content)
    assert str(meta["seed"]) == job["variants"][1]["seed"]
    assert client.get(job["original"]).status_code == 200


def test_bad_override_reports_the_real_validation_message(
    tmp_path: Path, document: NDArray[np.uint8]
) -> None:
    client = TestClient(create_app(tmp_path, samples_dir=None))
    res = client.post(
        "/api/jobs",
        files={"file": ("doc.png", _png(document), "image/png")},
        data={"preset": "office-medium", "overrides": "geometry.rotation=1"},
    )
    assert res.status_code == 400
    assert "unknown key 'geometry.rotation'" in res.json()["detail"]


def test_pdf_upload_scans_the_chosen_page(tmp_path: Path, document: NDArray[np.uint8]) -> None:
    buf = io.BytesIO()
    pages = [Image.fromarray(document), Image.fromarray(np.full_like(document, 255))]
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:], resolution=300)
    client = TestClient(create_app(tmp_path, samples_dir=None))
    files = {"file": ("form.pdf", buf.getvalue(), "application/pdf")}

    res = client.post("/api/jobs", files=files, data={"page": "2"})
    assert res.status_code == 200, res.text
    job = res.json()
    assert (job["page"], job["page_count"]) == (2, 2)
    assert job["variants"][0]["seed"] == str(derive_seed("form.pdf#p2", 0, 1))
    assert job["variants"][0]["download_name"] == "form_p002_scan_0001.jpg"

    res = client.post("/api/jobs", files=files, data={"page": "3"})
    assert res.status_code == 400
    assert res.json()["detail"] == "form.pdf: page 3 out of range; the PDF has 2"
