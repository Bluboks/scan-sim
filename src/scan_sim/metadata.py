"""JSON sidecar describing exactly how one output was produced."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import PIL

from scan_sim import __version__


def build_metadata(
    *,
    source: str,
    page: int | None,
    output: str,
    config_label: str,
    base_seed: int | None,
    seed: int,
    variant: int | None,
    dpi: int,
    input_dpi: tuple[float, float, str],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": source,
        "page": page,
        "output": output,
        "preset": config_label,
        "base_seed": base_seed,
        "seed": seed,
        "variant": variant,
        "dpi": dpi,
        "input_dpi": {"x": input_dpi[0], "y": input_dpi[1], "origin": input_dpi[2]},
        "parameters": parameters,
        "versions": {
            "scan_sim": __version__,
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": PIL.__version__,
        },
    }


def write_metadata(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
