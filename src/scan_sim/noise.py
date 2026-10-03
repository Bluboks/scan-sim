"""Band-limited random fields shared by the printer, paper, and scanner models.

Large-scale fields are generated on a coarse grid and upsampled, so a field with a
1000 px correlation length costs about as much as one with a 4 px length.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

F32 = NDArray[np.float32]


def gaussian_blur(img: F32, sigma_x: float, sigma_y: float) -> F32:
    """Anisotropic Gaussian blur in pixels; a sigma of 0 leaves that axis untouched."""
    if sigma_x <= 0 and sigma_y <= 0:
        return img
    kx = _kernel(sigma_x)
    ky = _kernel(sigma_y)
    out = cv2.sepFilter2D(img, cv2.CV_32F, kx, ky, borderType=cv2.BORDER_REFLECT)
    return np.asarray(out, dtype=np.float32)


def _kernel(sigma: float) -> F32:
    if sigma <= 0:
        return np.ones(1, dtype=np.float32)
    radius = max(1, int(np.ceil(3.5 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    out: F32 = (k / k.sum()).astype(np.float32)
    return out


def smooth_field(
    shape: tuple[int, int],
    scale_x: float,
    scale_y: float,
    rng: np.random.Generator,
) -> F32:
    """Zero-mean, unit-variance Gaussian random field with the given correlation lengths."""
    h, w = shape
    step = max(1, int(min(scale_x, scale_y) // 3))
    if step == 1:
        field = rng.standard_normal((h, w), dtype=np.float32)
        return _normalize(gaussian_blur(field, scale_x, scale_y))
    gh, gw = -(-h // step) + 1, -(-w // step) + 1
    field = rng.standard_normal((gh, gw), dtype=np.float32)
    field = _normalize(gaussian_blur(field, scale_x / step, scale_y / step))
    full = cv2.resize(field, (gw * step, gh * step), interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(full[:h, :w])


def _normalize(field: F32) -> F32:
    std = float(field.std())
    if std > 0:
        field = (field - np.float32(field.mean())) / np.float32(std)
    return field.astype(np.float32, copy=False)


def smooth_profile(length: int, scale: float, rng: np.random.Generator) -> F32:
    """One-dimensional version of :func:`smooth_field` (unit variance)."""
    return smooth_field((length, 1), 0.0, scale, rng)[:, 0].copy()
