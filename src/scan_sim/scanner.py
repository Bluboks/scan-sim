"""Scanner model (steps 8-14).

Steps 8-12 operate on linear light, as the sensor sees it. Step 13 encodes to the
scanner's sRGB output, and the tone curve and sharpening (steps 13-14) act on encoded
values, the way a scanner's image processor does.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from scan_sim.color import linear_to_srgb
from scan_sim.config import ScannerConfig
from scan_sim.noise import F32, gaussian_blur, smooth_field
from scan_sim.rng import sample

_INTERPOLATION = {
    "area": cv2.INTER_AREA,
    "lanczos": cv2.INTER_LANCZOS4,
    "cubic": cv2.INTER_CUBIC,
}


def resample(page: F32, cfg: ScannerConfig, working_dpi: float) -> F32:
    """Sample the working-resolution page on the scanner's pixel grid (step 8)."""
    h, w = page.shape[:2]
    factor = cfg.dpi / working_dpi
    size = (max(1, round(w * factor)), max(1, round(h * factor)))
    out = np.asarray(cv2.resize(page, size, interpolation=_INTERPOLATION[cfg.resample]), np.float32)
    np.clip(out, 0.0, 1.0, out=out)
    return out


def optical_psf(img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]) -> F32:
    """Lens/CIS blur in scanner pixels (step 9); y is the sub-scan (paper travel) axis."""
    sx = sample(cfg.psf.sigma_x, rng)
    sy = sample(cfg.psf.sigma_y, rng)
    rec["scanner_psf_sigma_x"] = sx
    rec["scanner_psf_sigma_y"] = sy
    return gaussian_blur(img, sx, sy)


def illumination(
    img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Uneven lamp field (step 10): low-order polynomial + low-frequency field + end falloff."""
    strength = sample(cfg.illumination.strength, rng)
    falloff = sample(cfg.illumination.edge_falloff, rng)
    rec["illumination_strength"] = strength
    rec["illumination_edge_falloff"] = falloff
    h, w = img.shape[:2]
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    y = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    a = rng.uniform(-1.0, 1.0, size=5).astype(np.float32) * np.float32(strength)
    field = a[0] * x + a[1] * y + a[2] * (x * x - 1 / 3) + a[3] * (y * y - 1 / 3) + a[4] * x * y
    scale = 0.3 * min(h, w)
    field = field + smooth_field((h, w), scale, scale, rng) * np.float32(0.5 * strength)
    # The lamp and light guide of a contact image sensor dim toward both ends.
    field = field - np.float32(falloff) * x**4
    field += np.float32(1.0)
    out: F32 = img * field[..., None]
    return out


def sensor_noise(
    img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Read and shot noise plus line-to-line and element-to-element gain error (step 11).

    Rows are scan lines: lamp flicker changes the gain of a whole line, per colour LED.
    Columns are sensor elements: residual error after shading calibration is a fixed
    gain per element, shared by the three colours that element measures.
    """
    n = cfg.noise
    read = sample(n.gaussian_sigma, rng)
    shot = sample(n.shot_strength, rng)
    row = sample(n.row_sigma, rng)
    col = sample(n.column_sigma, rng)
    rec.update(
        noise_gaussian_sigma=read,
        noise_shot_strength=shot,
        noise_row_sigma=row,
        noise_column_sigma=col,
    )
    h, w = img.shape[:2]
    gain = np.ones((h, w, 3), dtype=np.float32)
    if row > 0:
        gain += rng.standard_normal((h, 1, 3), dtype=np.float32) * np.float32(row)
    if col > 0:
        gain += rng.standard_normal((1, w, 1), dtype=np.float32) * np.float32(col)
    out: F32 = img * gain
    del gain
    if read > 0 or shot > 0:
        var = np.maximum(out, 0.0) * np.float32(shot * shot) + np.float32(read * read)
        out += rng.standard_normal(out.shape, dtype=np.float32) * np.sqrt(var)
    return out


def color_correct(
    img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Scanner RGB matrix and white balance (step 12)."""
    wb = [sample(v, rng) for v in cfg.white_balance]
    rec["white_balance"] = wb
    matrix = np.asarray(cfg.color_matrix, dtype=np.float32) * np.asarray(wb, np.float32)[:, None]
    return np.asarray(cv2.transform(img, matrix), dtype=np.float32)


def tone(img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]) -> F32:
    """Encode to sRGB, push paper toward white, then apply output levels (step 13).

    Background suppression closes part of the gap to white above a threshold. The
    weight ramps in smoothly below the threshold, so mid-tones and toner are kept.
    """
    gamma = sample(cfg.tone.gamma, rng)
    black = sample(cfg.tone.black_level, rng)
    white = sample(cfg.tone.white_level, rng)
    rec.update(tone_gamma=gamma, tone_black_level=black, tone_white_level=white)

    v = linear_to_srgb(img)
    if cfg.background_suppression.enabled:
        threshold = sample(cfg.background_suppression.threshold, rng)
        strength = sample(cfg.background_suppression.strength, rng)
        rec["background_threshold"] = threshold
        rec["background_strength"] = strength
        ramp = np.clip((v - np.float32(threshold - 0.12)) / np.float32(0.12), 0.0, 1.0)
        weight = ramp * ramp * (3.0 - 2.0 * ramp)
        v += np.float32(strength) * weight * (1.0 - v)
    if gamma != 1.0:
        v = np.asarray(cv2.pow(v, gamma), np.float32)
    v *= np.float32(white - black)
    v += np.float32(black)
    np.clip(v, 0.0, 1.0, out=v)
    return v


def sharpen(img: F32, cfg: ScannerConfig, rng: np.random.Generator, rec: dict[str, Any]) -> F32:
    """Unsharp mask on encoded values (step 14)."""
    if not cfg.sharpening.enabled:
        return img
    sigma = sample(cfg.sharpening.sigma, rng)
    amount = sample(cfg.sharpening.amount, rng)
    rec["sharpen_sigma"] = sigma
    rec["sharpen_amount"] = amount
    blur = gaussian_blur(img, sigma, sigma)
    out: F32 = img + np.float32(amount) * (img - blur)
    np.clip(out, 0.0, 1.0, out=out)
    return out
