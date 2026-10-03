"""Placement of the printed sheet on the scanner (step 7).

Rotation, per-axis scale, translation, and a small perspective term are combined into
one homography and applied with a single resampling, so the page is interpolated once.
Wherever the skewed or shifted sheet does not cover the scan area, the scanner's
backing shows (flatbed lid or ADF backing plate), and the sheet's edge casts a thin
shadow onto it. Without that, a skewed page would have no visible border at all.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from scan_sim.config import GeometryConfig
from scan_sim.noise import F32, gaussian_blur, smooth_field
from scan_sim.rng import sample

MM_PER_INCH = 25.4
# Directions in which a sheet edge can throw its shadow: down, up, right, left.
_SHADOW_DIRECTIONS = ((0, 1), (0, -1), (1, 0), (-1, 0))


def place_on_scanner(
    page: F32,
    cfg: GeometryConfig,
    working_dpi: float,
    scanner_dpi: float,
    rng: np.random.Generator,
    rec: dict[str, Any],
) -> tuple[F32, NDArray[np.float64]]:
    """Warp the page onto the scan area (still at working resolution).

    The scan area is the page plus ``scan_margin_mm`` on every side. Returns the scan
    area image and the homography from working-page pixels to scan-area pixels.
    ``translation_px`` is in scanner pixels.
    """
    h, w = page.shape[:2]
    scanner_px = working_dpi / scanner_dpi
    # Draw order is fixed (ADR-003): placement first, then the newer border terms.
    angle = sample(cfg.rotation_deg, rng)
    sx = sample(cfg.scale_x, rng)
    sy = sample(cfg.scale_y, rng)
    tx = sample(cfg.translation_px.x, rng)
    ty = sample(cfg.translation_px.y, rng)
    rec.update(rotation_deg=angle, scale_x=sx, scale_y=sy, translation_x_px=tx, translation_y_px=ty)
    jitter = np.zeros((4, 2))
    if cfg.perspective.enabled and cfg.perspective.max_corner_shift_ratio > 0:
        ratio = cfg.perspective.max_corner_shift_ratio
        jitter = rng.uniform(-1.0, 1.0, size=(4, 2)) * [ratio * w, ratio * h]
    rec["perspective_max_corner_shift_px"] = float(np.abs(jitter).max()) / scanner_px

    margin_mm = sample(cfg.scan_margin_mm, rng)
    margin = round(margin_mm / MM_PER_INCH * working_dpi)
    rec["scan_margin_mm"] = margin_mm

    homography = _homography(w, h, angle, sx, sy, tx * scanner_px, ty * scanner_px, jitter)
    homography = np.array([[1, 0, margin], [0, 1, margin], [0, 0, 1]], float) @ homography
    size = (w + 2 * margin, h + 2 * margin)

    sheet = np.asarray(
        cv2.warpPerspective(
            page, homography, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        ),
        dtype=np.float32,
    )
    coverage = np.asarray(
        cv2.warpPerspective(
            np.ones((h, w), np.float32),
            homography,
            size,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        ),
        dtype=np.float32,
    )
    backing = _backing(size[1], size[0], cfg, rng, rec)
    shade = _edge_shadow(coverage, cfg, rng, rec)

    # Anti-aliased sheet edge: blend sheet over backing by fractional coverage.
    sheet *= coverage[..., None]
    sheet += backing * (np.float32(1.0) - coverage)[..., None]
    if shade is not None:
        sheet *= shade[..., None]
    return sheet, homography


def _homography(
    w: int,
    h: int,
    angle: float,
    sx: float,
    sy: float,
    tx: float,
    ty: float,
    jitter: NDArray[np.float64],
) -> NDArray[np.float64]:
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    theta = math.radians(angle)
    cos, sin = math.cos(theta), math.sin(theta)
    corners = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float64)
    scaled = (corners - [cx, cy]) * [sx, sy]
    rotated = np.stack(
        [scaled[:, 0] * cos - scaled[:, 1] * sin, scaled[:, 0] * sin + scaled[:, 1] * cos], 1
    )
    dst = rotated + [cx + tx, cy + ty] + jitter
    out: NDArray[np.float64] = cv2.getPerspectiveTransform(
        corners.astype(np.float32), dst.astype(np.float32)
    ).astype(np.float64)
    return out


def _backing(
    h: int, w: int, cfg: GeometryConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Lid or ADF backing: a flat colour with faint large-scale unevenness."""
    brightness = sample(cfg.backing.brightness, rng)
    texture = sample(cfg.backing.texture_strength, rng)
    rec["backing_brightness"] = brightness
    rec["backing_texture_strength"] = texture
    rgb = np.clip(np.asarray(cfg.backing.rgb, dtype=np.float32) * np.float32(brightness), 0, 1)
    if texture <= 0:
        return np.broadcast_to(rgb, (h, w, 3)).astype(np.float32)
    scale = 0.05 * max(h, w)
    lum = smooth_field((h, w), scale, scale, rng) * np.float32(texture) + np.float32(1.0)
    out: F32 = np.clip(lum[..., None] * rgb, 0.0, 1.0).astype(np.float32)
    return out


def _shift(img: F32, dx: int, dy: int) -> F32:
    """Translate by whole pixels, filling the uncovered strip with zeros."""
    out = np.zeros_like(img)
    h, w = img.shape
    src_y, dst_y = slice(max(0, -dy), h - max(0, dy)), slice(max(0, dy), h - max(0, -dy))
    src_x, dst_x = slice(max(0, -dx), w - max(0, dx)), slice(max(0, dx), w - max(0, -dx))
    out[dst_y, dst_x] = img[src_y, src_x]
    return out


def _edge_shadow(
    coverage: F32, cfg: GeometryConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32 | None:
    """Multiplier (<= 1) darkening a thin band just outside the sheet edge.

    The sheet edge is lifted a little and lit at an angle, so it shades the backing
    next to it. Each of the four shadow directions gets its own weight, as the light
    comes from one side and paper never lies perfectly flat.
    """
    strength = sample(cfg.edge_shadow.strength, rng)
    width = sample(cfg.edge_shadow.width_px, rng)
    weights = rng.uniform(0.3, 1.0, size=4)
    rec["edge_shadow_strength"] = strength
    rec["edge_shadow_width_px"] = width
    rec["edge_shadow_side_weights"] = [float(x) for x in weights]
    if strength <= 0 or width <= 0:
        return None
    step = max(1, round(width))
    band = np.zeros_like(coverage)
    for (dx, dy), weight in zip(_SHADOW_DIRECTIONS, weights, strict=True):
        shifted = _shift(coverage, dx * step, dy * step)
        band += np.float32(weight) * np.clip(shifted - coverage, 0.0, 1.0)
    band = gaussian_blur(band, width / 2.0, width / 2.0)
    shade: F32 = np.float32(1.0) - np.float32(strength) * np.clip(band, 0.0, 1.0)
    return shade
