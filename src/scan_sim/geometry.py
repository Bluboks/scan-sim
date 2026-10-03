"""Placement error of the printed sheet on the scanner (step 7).

Rotation, per-axis scale, translation, and a small perspective term are combined into
one homography and applied with a single resampling, so the page is interpolated once.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from scan_sim.config import GeometryConfig
from scan_sim.noise import F32
from scan_sim.rng import sample


def place_on_scanner(
    page: F32,
    cfg: GeometryConfig,
    scanner_px_in_working: float,
    border_rgb: tuple[float, float, float],
    rng: np.random.Generator,
    rec: dict[str, Any],
) -> F32:
    """Warp the page into scanner coordinates (still at working resolution).

    ``translation_px`` is in scanner pixels; ``scanner_px_in_working`` converts it.
    Uncovered area shows the scanner lid, filled with ``border_rgb``.
    """
    h, w = page.shape[:2]
    angle = sample(cfg.rotation_deg, rng)
    sx = sample(cfg.scale_x, rng)
    sy = sample(cfg.scale_y, rng)
    tx = sample(cfg.translation_px.x, rng)
    ty = sample(cfg.translation_px.y, rng)
    rec.update(rotation_deg=angle, scale_x=sx, scale_y=sy, translation_x_px=tx, translation_y_px=ty)

    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    theta = math.radians(angle)
    cos, sin = math.cos(theta), math.sin(theta)
    corners = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float64)
    rel = corners - [cx, cy]
    scaled = rel * [sx, sy]
    rotated = np.stack(
        [scaled[:, 0] * cos - scaled[:, 1] * sin, scaled[:, 0] * sin + scaled[:, 1] * cos], 1
    )
    dst = rotated + [cx + tx * scanner_px_in_working, cy + ty * scanner_px_in_working]

    shift_max = 0.0
    if cfg.perspective.enabled and cfg.perspective.max_corner_shift_ratio > 0:
        ratio = cfg.perspective.max_corner_shift_ratio
        jitter = rng.uniform(-1.0, 1.0, size=(4, 2)) * [ratio * w, ratio * h]
        dst = dst + jitter
        shift_max = float(np.abs(jitter).max())
    rec["perspective_max_corner_shift_px"] = shift_max / scanner_px_in_working

    homography = cv2.getPerspectiveTransform(corners.astype(np.float32), dst.astype(np.float32))
    out = cv2.warpPerspective(
        page,
        homography,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=tuple(float(v) for v in border_rgb),
    )
    return np.asarray(out, dtype=np.float32)
