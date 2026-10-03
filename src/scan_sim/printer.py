"""Laser printer model (pipeline steps 2-4), at working resolution.

The printer is modelled as toner *coverage* ``A`` per channel: the fraction of light
the toner layer absorbs (0 = bare paper, ``black_density`` = solid black). Working in
coverage keeps the later paper composite a plain reflectance product.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from scan_sim.config import PrinterConfig
from scan_sim.noise import F32, gaussian_blur, smooth_field
from scan_sim.rng import sample

# Correlation length of toner edge roughness at working resolution. Toner particles
# are 5-8 um; the ragged edge they leave correlates over roughly 30-40 um (~0.8 px at
# 600 dpi). Fixed, because the brief only exposes the roughness amplitude.
_EDGE_ROUGHNESS_CORRELATION_PX = 0.8


def print_coverage(
    rgb_linear: F32, cfg: PrinterConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Turn a linear-light digital page into the toner coverage the printer lays down."""
    gamma = sample(cfg.gamma, rng)
    black_density = sample(cfg.black_density, rng)
    rec["printer_gamma"] = gamma
    rec["printer_black_density"] = black_density

    matrix = np.asarray(cfg.color_matrix, dtype=np.float32)
    reflect = cv2.transform(rgb_linear, matrix)
    np.clip(reflect, 0.0, 1.0, out=reflect)
    if gamma != 1.0:
        reflect = cv2.pow(reflect, gamma)
    coverage: F32 = (1.0 - reflect) * np.float32(black_density)
    del reflect

    sigma_x = sample(cfg.psf.sigma_x, rng)
    sigma_y = sample(cfg.psf.sigma_y, rng)
    rec["printer_psf_sigma_x"] = sigma_x
    rec["printer_psf_sigma_y"] = sigma_y
    coverage = gaussian_blur(coverage, sigma_x, sigma_y)

    coverage = _shift_edges(coverage, cfg, black_density, rng, rec)
    coverage = _toner_density(coverage, cfg, rng, rec)
    # Edge growth must not print darker than a solid area: cap at the solid density.
    np.clip(coverage, 0.0, black_density, out=coverage)
    return coverage


def _shift_edges(
    coverage: F32,
    cfg: PrinterConfig,
    black_density: float,
    rng: np.random.Generator,
    rec: dict[str, Any],
) -> F32:
    """Dot gain and edge roughness as a sub-pixel move of every toner edge.

    Moving an edge outward by ``d`` pixels changes the value under it by about
    ``d * |grad A|`` (first-order Taylor), which is exact enough for the sub-pixel
    distances involved and touches only pixels on an edge: flat paper and flat toner
    have no gradient. ``d`` is the dot-gain radius plus a band-limited random field
    (the ragged toner edge). A hard morphological dilation would move edges by whole
    pixels instead.
    """
    radius = sample(cfg.dot_gain.radius_px, rng) if cfg.dot_gain.enabled else 0.0
    tonal = sample(cfg.dot_gain.strength, rng) if cfg.dot_gain.enabled else 0.0
    rough = sample(cfg.edge_roughness_px, rng)
    rec["dot_gain_radius_px"] = radius
    rec["dot_gain_strength"] = tonal
    rec["edge_roughness_px"] = rough

    h, w = coverage.shape[:2]
    if radius > 0 or rough > 0:
        shift = np.full((h, w), radius, dtype=np.float32)
        if rough > 0:
            c = _EDGE_ROUGHNESS_CORRELATION_PX
            shift += smooth_field((h, w), c, c, rng) * np.float32(rough)
        gx = cv2.Sobel(coverage, cv2.CV_32F, 1, 0, ksize=3, scale=0.125)
        gy = cv2.Sobel(coverage, cv2.CV_32F, 0, 1, ksize=3, scale=0.125)
        grad = cv2.magnitude(gx.reshape(-1), gy.reshape(-1)).reshape(coverage.shape)
        del gx, gy
        coverage += grad * shift[..., None]
        del grad, shift

    if tonal > 0:
        # Tonal dot gain: light tints and anti-aliased edge pixels print darker,
        # most strongly at mid coverage, while paper and solid black stay put.
        c = np.clip(coverage / np.float32(black_density), 0.0, 1.0)
        coverage += np.float32(tonal * black_density) * c * (1.0 - c)
    return coverage


def _toner_density(
    coverage: F32, cfg: PrinterConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Low-frequency mottle in toner density. Multiplicative, so bare paper is unaffected."""
    strength = sample(cfg.toner_density_noise.strength, rng)
    scale = sample(cfg.toner_density_noise.scale_px, rng)
    rec["toner_density_strength"] = strength
    rec["toner_density_scale_px"] = scale
    if strength <= 0:
        return coverage
    field = smooth_field(coverage.shape[:2], scale, scale, rng)
    field *= np.float32(strength)
    field += np.float32(1.0)
    coverage *= field[..., None]
    return coverage
