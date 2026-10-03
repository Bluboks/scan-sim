"""PDF input: count pages and rasterize one page at working resolution.

Pages are rendered with PDFium (``pypdfium2``, Apache-2.0/BSD) straight to the working
DPI, so vector text gets real 600 dpi edges instead of an upscaled raster. Only the
rendered pixels go on; the text layer is gone, as it would be on paper.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

from scan_sim.errors import InputImageError
from scan_sim.noise import F32

PDF_SUFFIXES = {".pdf"}
POINTS_PER_INCH = 72.0
MM_PER_INCH = 25.4


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() in PDF_SUFFIXES


def _open(path: Path) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        raise InputImageError(f"{path}: cannot open PDF: {exc}") from exc


def page_count(path: Path) -> int:
    doc = _open(path)
    try:
        count = len(doc)
    finally:
        doc.close()
    if count == 0:
        raise InputImageError(f"{path}: PDF has no pages")
    return count


def render_page(path: Path, page: int, dpi: float, max_page_mm: float) -> F32:
    """Render 1-based ``page`` on white paper; returns display-encoded RGB in 0..1."""
    doc = _open(path)
    try:
        if not 1 <= page <= len(doc):
            raise InputImageError(f"{path}: page {page} out of range; the PDF has {len(doc)}")
        pdf_page = doc[page - 1]
        try:
            w_pt, h_pt = pdf_page.get_size()
            longest_mm = max(w_pt, h_pt) / POINTS_PER_INCH * MM_PER_INCH
            if longest_mm > max_page_mm:
                raise InputImageError(
                    f"{path}: page {page} is {w_pt / POINTS_PER_INCH * MM_PER_INCH:.0f}x"
                    f"{h_pt / POINTS_PER_INCH * MM_PER_INCH:.0f} mm, larger than "
                    f"input.max_page_mm ({max_page_mm:g} mm)"
                )
            bitmap = pdf_page.render(
                scale=dpi / POINTS_PER_INCH, fill_color=(255, 255, 255, 255), may_draw_forms=True
            )
            rgb: F32 = np.asarray(bitmap.to_pil().convert("RGB"), dtype=np.float32)
        finally:
            pdf_page.close()
    finally:
        doc.close()
    rgb /= np.float32(255.0)
    return rgb
