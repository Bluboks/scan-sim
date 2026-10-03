from __future__ import annotations

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from scan_sim import simulate_scan
from scan_sim.config import list_presets, load_config

OFFICE = ["office-clean", "office-medium", "office-adf", "office-aged"]


def test_five_required_presets_exist() -> None:
    assert set(list_presets()) >= {*OFFICE, "ocr-stress"}


def test_office_clean_rotation_stays_within_a_tenth_of_a_degree() -> None:
    rotation = load_config("office-clean")[0].geometry.rotation_deg
    assert isinstance(rotation, tuple)
    assert max(abs(rotation[0]), abs(rotation[1])) <= 0.1


@pytest.mark.parametrize("preset", OFFICE)
def test_office_presets_keep_the_document_readable(
    preset: str, document: NDArray[np.uint8]
) -> None:
    cfg = load_config(preset)[0]
    for seed in range(3):
        out, _ = simulate_scan(document, cfg, seed)
        gray = out.mean(axis=2)
        assert gray[50:90, 50:110].mean() < 100, "solid toner must stay dark"
        assert gray[180:230, 40:320].mean() > 215, "blank paper must stay light"
        rule = gray[138:164, 30:330].mean(axis=1).min()  # the 2 px rule, wherever it moved
        assert rule < gray[180:230, 40:320].mean() - 60, "thin rule must stay visible"
        grey_patch = gray[50:90, 210:290].mean()
        assert 140 < grey_patch < 225, "light grey fill stays a distinct mid tone"


@pytest.mark.parametrize("preset", [*OFFICE, "ocr-stress"])
def test_preset_preserves_layout(preset: str, document: NDArray[np.uint8]) -> None:
    """Degradation only: mapped back through the recorded homography, the scan matches."""
    out, params = simulate_scan(document, load_config(preset)[0], 5)
    to_scan = np.array(params["input_to_scan_homography"])
    h, w = document.shape[:2]
    back = cv2.warpPerspective(
        out.mean(axis=2).astype(np.float32),
        to_scan,
        (w, h),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
    )
    m = 12  # skip the border: placement shifts up to ~10 px uncover backing there
    a = document.mean(axis=2)[m:-m, m:-m].ravel()
    assert np.corrcoef(a, back[m:-m, m:-m].ravel())[0, 1] > 0.95
