"""Optional scan artifacts (step 15), applied to encoded values.

Both artifacts are rare, faint, and span the whole sheet, as they do on real devices.
Dust specks and separate ADF skew are not part of v0.1 (ADF skew is covered by the
``office-adf`` preset's wider rotation range).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scan_sim.config import ArtifactsConfig
from scan_sim.noise import F32, smooth_profile
from scan_sim.rng import sample, sample_int


def apply_artifacts(
    img: F32, cfg: ArtifactsConfig, rng: np.random.Generator, rec: dict[str, Any]
) -> F32:
    h, w = img.shape[:2]
    streak = cfg.vertical_streak
    # Draw every random number up front so one artifact firing never shifts the other.
    streak_hit = bool(rng.random() < streak.probability)
    streak_x = float(rng.uniform(0, w))
    streak_strength = sample(streak.strength, rng)
    streak_width = sample_int(streak.width_px, rng)
    band = cfg.horizontal_banding
    band_hit = bool(rng.random() < band.probability)
    band_strength = sample(band.strength, rng)
    band_scale = sample(band.scale_px, rng)
    band_profile = smooth_profile(h, band_scale, rng)

    rec["vertical_streak"] = (
        {"x_px": streak_x, "strength": streak_strength, "width_px": streak_width}
        if streak_hit
        else None
    )
    rec["horizontal_banding"] = (
        {"strength": band_strength, "scale_px": band_scale} if band_hit else None
    )

    if streak_hit:
        # Dust on the glass under a contact image sensor darkens one column on every line.
        x = np.arange(w, dtype=np.float32)
        sigma = max(streak_width, 1) / 2.0
        profile = np.exp(-0.5 * ((x - streak_x) / sigma) ** 2)
        img *= (1.0 - np.float32(streak_strength) * profile)[None, :, None]
    if band_hit:
        # Uneven paper/carriage speed brightens and darkens whole scan lines.
        img *= (1.0 + np.float32(band_strength) * band_profile)[:, None, None]
    np.clip(img, 0.0, 1.0, out=img)
    return img
