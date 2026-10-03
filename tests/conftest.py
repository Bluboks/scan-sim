from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from scan_sim.config import SimulationConfig, load_config


def make_document(width: int = 360, height: int = 240) -> NDArray[np.uint8]:
    """Small 300 dpi test page: a solid black block, a 2 px rule, a grey patch."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    img[40:100, 40:120] = 0  # solid toner
    img[150:152, 20:340] = 0  # thin table rule
    img[40:100, 200:300] = 200  # light grey fill
    return img


@pytest.fixture
def document() -> NDArray[np.uint8]:
    return make_document()


@pytest.fixture
def medium() -> SimulationConfig:
    return load_config("office-medium")[0]


@pytest.fixture
def input_dir(tmp_path: Path) -> Path:
    root = tmp_path / "input"
    (root / "sub").mkdir(parents=True)
    Image.fromarray(make_document()).save(root / "a.png", dpi=(300, 300))
    Image.fromarray(make_document()).save(root / "sub" / "b.png", dpi=(300, 300))
    return root
