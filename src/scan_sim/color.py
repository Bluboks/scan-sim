"""sRGB transfer functions. All light and reflectance math runs on linear values."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

F32 = NDArray[np.float32]


def srgb_to_linear(v: F32) -> F32:
    v = np.clip(v, 0.0, 1.0).astype(np.float32, copy=False)
    curve = np.asarray(cv2.pow((v + np.float32(0.055)) / np.float32(1.055), 2.4), np.float32)
    out: F32 = np.where(v <= 0.04045, v / np.float32(12.92), curve)
    return out


def linear_to_srgb(v: F32) -> F32:
    v = np.clip(v, 0.0, 1.0).astype(np.float32, copy=False)
    curve = np.asarray(cv2.pow(v, 1.0 / 2.4), np.float32) * np.float32(1.055) - np.float32(0.055)
    out: F32 = np.where(v <= 0.0031308, v * np.float32(12.92), curve)
    return out
