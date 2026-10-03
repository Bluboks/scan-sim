"""Paper reflectance model (step 5) and print-paper composite (step 6)."""

from __future__ import annotations

from typing import Any

import numpy as np

from scan_sim.config import PaperConfig
from scan_sim.noise import F32, smooth_field
from scan_sim.rng import sample

# Share of each texture layer that varies per channel. Paper texture is almost
# achromatic (the same fibres reflect all wavelengths alike), so channels stay
# highly correlated: about 0.95 correlation for these weights.
_CHROMA_SHARE = 0.25
_FINE_GRAIN_CORRELATION_PX = 0.7


def generate_paper(
    shape: tuple[int, int], cfg: PaperConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    """Linear reflectance of blank office paper, ``shape`` = (height, width)."""
    lf_strength = sample(cfg.low_frequency.strength, rng)
    lf_scale = sample(cfg.low_frequency.scale_px, rng)
    fiber_strength = sample(cfg.fiber.strength, rng)
    fiber_scale = sample(cfg.fiber.scale_px, rng)
    elongation = sample(cfg.fiber.elongation, rng)
    grain_strength = sample(cfg.fine_grain.strength, rng)
    # Fibres line up with the paper machine direction, which is either page axis.
    fiber_along_y = bool(rng.integers(0, 2))
    rec.update(
        paper_low_frequency_strength=lf_strength,
        paper_low_frequency_scale_px=lf_scale,
        paper_fiber_strength=fiber_strength,
        paper_fiber_scale_px=fiber_scale,
        paper_fiber_elongation=elongation,
        paper_fiber_direction="y" if fiber_along_y else "x",
        paper_fine_grain_strength=grain_strength,
    )

    fx, fy = fiber_scale, fiber_scale * elongation
    if not fiber_along_y:
        fx, fy = fy, fx

    lum = smooth_field(shape, lf_scale, lf_scale, rng) * np.float32(lf_strength)
    lum += smooth_field(shape, fx, fy, rng) * np.float32(fiber_strength)
    g = _FINE_GRAIN_CORRELATION_PX
    lum += smooth_field(shape, g, g, rng) * np.float32(grain_strength)
    lum += np.float32(1.0)

    base = np.asarray(cfg.base_rgb, dtype=np.float32)
    paper = np.empty((*shape, 3), dtype=np.float32)
    chroma_strength = np.float32(_CHROMA_SHARE * (lf_strength + fiber_strength))
    for ch in range(3):
        tint = smooth_field(shape, fx, fy, rng) * chroma_strength
        tint += lum
        paper[..., ch] = tint * base[ch]
    np.clip(paper, 0.0, 1.0, out=paper)
    return paper


def composite(paper: F32, coverage: F32) -> F32:
    """Reflectance product: light passes the toner layer, bounces off paper, passes back.

    ``paper * (1 - A)`` keeps the paper texture under light tints and leaves the toner
    mottle visible on solids, unlike an alpha blend that would paint over the paper.
    """
    out: F32 = paper
    out *= np.float32(1.0) - coverage
    return out
