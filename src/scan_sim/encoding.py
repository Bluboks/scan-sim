"""Final file encoding (step 16). The only lossy compression in the whole pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from scan_sim.config import EncodingConfig
from scan_sim.rng import sample_int

# Office MFPs almost always write 4:2:0 JPEGs, so "auto" means 4:2:0.
_SUBSAMPLING = {"auto": 2, "420": 2, "422": 1, "444": 0}
FORMAT_SUFFIX = {"jpg": ".jpg", "png": ".png"}
SUFFIX_FORMAT = {".jpg": "jpg", ".jpeg": "jpg", ".png": "png"}


def sample_encoding(cfg: EncodingConfig, rng: np.random.Generator) -> dict[str, Any]:
    params: dict[str, Any] = {"format": cfg.format}
    quality = sample_int(cfg.jpeg_quality, rng)
    if cfg.format == "jpg":
        params["jpeg_quality"] = quality
        params["jpeg_subsampling"] = "420" if cfg.subsampling == "auto" else cfg.subsampling
    return params


def write_image(
    path: Path, img: NDArray[np.uint8], dpi: int, cfg: EncodingConfig, params: dict[str, Any]
) -> None:
    pil = Image.fromarray(img, mode="RGB")
    if cfg.format == "jpg":
        pil.save(
            path,
            format="JPEG",
            quality=params["jpeg_quality"],
            subsampling=_SUBSAMPLING[cfg.subsampling],
            dpi=(dpi, dpi),
        )
    else:
        pil.save(path, format="PNG", dpi=(dpi, dpi), compress_level=6)
