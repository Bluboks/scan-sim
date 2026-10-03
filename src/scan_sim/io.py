"""Image input: decoding, alpha removal, DPI resolution, working-resolution resampling.

Images are decoded with Pillow, not ``cv2.imread``, because OpenCV cannot open
non-ASCII paths on Windows (Korean file names are the normal case here).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

from scan_sim.color import srgb_to_linear
from scan_sim.config import InputConfig
from scan_sim.errors import InputImageError
from scan_sim.noise import F32
from scan_sim.pdf import PDF_SUFFIXES, is_pdf, render_page

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
INPUT_SUFFIXES = IMAGE_SUFFIXES | PDF_SUFFIXES
MM_PER_INCH = 25.4


@dataclass(frozen=True)
class SourceImage:
    """Display-encoded RGB in 0..1 plus the DPI of each axis."""

    rgb: F32
    dpi_x: float
    dpi_y: float
    dpi_origin: str  # "metadata", "assumed", or "pdf-render"


def read_source(path: Path, cfg: InputConfig, working_dpi: float, page: int | None) -> SourceImage:
    """Read an image file, or render one page (1-based) of a PDF at working DPI."""
    if is_pdf(path):
        if page is None:
            raise InputImageError(f"{path}: a PDF input needs a page number")
        rgb = render_page(path, page, working_dpi, cfg.max_page_mm)
        return SourceImage(rgb, working_dpi, working_dpi, "pdf-render")
    if page is not None:
        raise InputImageError(f"{path}: page {page} given for an image file")
    return read_image(path, cfg)


def read_image(path: Path, cfg: InputConfig) -> SourceImage:
    try:
        with Image.open(path) as opened:
            img = ImageOps.exif_transpose(opened)
            img.load()
    except (OSError, UnidentifiedImageError) as exc:
        raise InputImageError(f"{path}: cannot read image: {exc}") from exc
    rgb = to_rgb_float(img)
    dpi_x, dpi_y, origin = _resolve_dpi(img.info.get("dpi"), cfg)
    check_page_size(path.name, rgb.shape[1], rgb.shape[0], dpi_x, dpi_y, origin, cfg)
    return SourceImage(rgb, dpi_x, dpi_y, origin)


def to_rgb_float(img: Image.Image) -> F32:
    """Any Pillow mode to RGB 0..1; transparency is composited onto white paper."""
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        gray = np.asarray(img, dtype=np.float32)
        gray /= np.float32(65535.0 if img.mode.startswith("I;16") else max(float(gray.max()), 1.0))
        return np.repeat(gray[..., None], 3, axis=2)
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if has_alpha:
        rgba = np.asarray(img.convert("RGBA"), dtype=np.float32) / np.float32(255.0)
        alpha = rgba[..., 3:4]
        out: F32 = rgba[..., :3] * alpha + (1.0 - alpha)
        return out
    rgb: F32 = np.asarray(img.convert("RGB"), dtype=np.float32) / np.float32(255.0)
    return rgb


def _resolve_dpi(meta: object, cfg: InputConfig) -> tuple[float, float, str]:
    if cfg.dpi_from_metadata and isinstance(meta, tuple) and len(meta) == 2:
        dx, dy = (round(float(v), 2) for v in meta)
        if dx > 0 and dy > 0:
            return dx, dy, "metadata"
    return cfg.assumed_dpi, cfg.assumed_dpi, "assumed"


def check_page_size(
    name: str, w: int, h: int, dpi_x: float, dpi_y: float, origin: str, cfg: InputConfig
) -> None:
    """Reject DPI values that would make an implausibly large physical page.

    Many tools write 72 or 96 dpi into files meant for 300 dpi print. Trusting that
    would turn an A4 page into a poster and the working image into gigabytes.
    """
    width_mm = w / dpi_x * MM_PER_INCH
    height_mm = h / dpi_y * MM_PER_INCH
    if max(width_mm, height_mm) <= cfg.max_page_mm:
        return
    hint = (
        "the file's DPI metadata looks wrong; pass --set input.dpi_from_metadata=false "
        f"to use input.assumed_dpi ({cfg.assumed_dpi:g})"
        if origin == "metadata"
        else "set input.assumed_dpi to the resolution the image was made for"
    )
    raise InputImageError(
        f"{name}: {w}x{h} px at {dpi_x:g}x{dpi_y:g} dpi ({origin}) is a "
        f"{width_mm:.0f}x{height_mm:.0f} mm page, larger than input.max_page_mm "
        f"({cfg.max_page_mm:g} mm); {hint}"
    )


def to_working(source: SourceImage, working_dpi: float) -> F32:
    """Convert to linear light and resample to working DPI.

    Resampling happens in linear light, as light from neighbouring dots mixes on paper.
    Upsampling interpolates only; it adds no detail the original raster does not have.
    """
    h, w = source.rgb.shape[:2]
    fx, fy = working_dpi / source.dpi_x, working_dpi / source.dpi_y
    size = (max(1, round(w * fx)), max(1, round(h * fy)))
    linear = srgb_to_linear(source.rgb)
    if size == (w, h):
        return linear
    interp = cv2.INTER_AREA if fx < 1 and fy < 1 else cv2.INTER_CUBIC
    out = np.asarray(cv2.resize(linear, size, interpolation=interp), np.float32)
    np.clip(out, 0.0, 1.0, out=out)
    return out


def array_to_source(image: NDArray[np.generic], dpi: float) -> SourceImage:
    """Wrap an in-memory array (uint8/uint16/float, gray/RGB/RGBA) as a source image."""
    arr = np.asarray(image)
    if arr.dtype == np.uint8:
        f = arr.astype(np.float32) / np.float32(255.0)
    elif arr.dtype == np.uint16:
        f = arr.astype(np.float32) / np.float32(65535.0)
    elif np.issubdtype(arr.dtype, np.floating):
        f = arr.astype(np.float32)
    else:
        raise InputImageError(f"unsupported image dtype {arr.dtype}")
    if f.ndim == 2:
        f = np.repeat(f[..., None], 3, axis=2)
    if f.ndim != 3 or f.shape[2] not in (3, 4):
        raise InputImageError(f"expected HxW, HxWx3 or HxWx4 image, got shape {arr.shape}")
    if f.shape[2] == 4:
        alpha = f[..., 3:4]
        f = f[..., :3] * alpha + (1.0 - alpha)
    return SourceImage(np.clip(f, 0.0, 1.0), dpi, dpi, "assumed")
