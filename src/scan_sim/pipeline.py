"""The fixed-order print-scan chain (steps 1-15). Encoding (16) happens in ``batch``."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from scan_sim import artifacts, geometry, paper, printer, scanner
from scan_sim.config import SimulationConfig
from scan_sim.io import SourceImage, array_to_source, to_working
from scan_sim.rng import stage_rng


def simulate_scan(
    image: NDArray[np.generic], config: SimulationConfig, seed: int
) -> tuple[NDArray[np.uint8], dict[str, Any]]:
    """Simulate print + scan of an in-memory image taken to be at ``input.assumed_dpi``.

    Returns the scanner's 8-bit RGB output (before file encoding) and every sampled
    parameter. The same image, config and seed always give the same result.
    """
    return simulate_source(array_to_source(image, config.input.assumed_dpi), config, seed)


def simulate_source(
    source: SourceImage, config: SimulationConfig, seed: int
) -> tuple[NDArray[np.uint8], dict[str, Any]]:
    rec: dict[str, Any] = {}
    working_dpi = config.working.dpi

    # [1] input normalization to working DPI, linear light
    page = to_working(source, working_dpi)
    h, w = page.shape[:2]

    # [2]-[4] printer tone/colour, PSF, dot gain, edge roughness, toner density
    coverage = printer.print_coverage(page, config.printer, stage_rng(seed, "printer"), rec)
    del page

    # [5]-[6] paper reflectance and reflectance composite
    sheet = paper.generate_paper((h, w), config.paper, stage_rng(seed, "paper"), rec)
    sheet = paper.composite(sheet, coverage)
    del coverage

    # [7] placement on the scanner glass, backing and sheet-edge shadow
    sheet, placement = geometry.place_on_scanner(
        sheet, config.geometry, working_dpi, config.scanner.dpi, stage_rng(seed, "geometry"), rec
    )
    canvas_h, canvas_w = sheet.shape[:2]

    # [8]-[14] scanner
    srng = stage_rng(seed, "scanner")
    scan = scanner.resample(sheet, config.scanner, working_dpi)
    del sheet
    _record_mapping(rec, source, (w, h), (canvas_w, canvas_h), scan.shape[1::-1], placement)
    scan = scanner.optical_psf(scan, config.scanner, srng, rec)
    scan = scanner.illumination(scan, config.scanner, srng, rec)
    scan = scanner.sensor_noise(scan, config.scanner, srng, rec)
    scan = scanner.color_correct(scan, config.scanner, srng, rec)
    scan = scanner.tone(scan, config.scanner, srng, rec)
    scan = scanner.sharpen(scan, config.scanner, srng, rec)

    # [15] optional artifacts
    scan = artifacts.apply_artifacts(scan, config.artifacts, stage_rng(seed, "artifacts"), rec)

    out = np.rint(scan * np.float32(255.0)).astype(np.uint8)
    return out, rec


def _pixel_scale(sx: float, sy: float) -> NDArray[np.float64]:
    """Pixel-centre mapping of a resize by (sx, sy), as OpenCV resamples."""
    return np.array([[sx, 0, 0.5 * sx - 0.5], [0, sy, 0.5 * sy - 0.5], [0, 0, 1]], float)


def _record_mapping(
    rec: dict[str, Any],
    source: SourceImage,
    page_wh: tuple[int, int],
    canvas_wh: tuple[int, int],
    scan_wh: tuple[int, ...],
    placement: NDArray[np.float64],
) -> None:
    """Store where input pixels land in the scan, for mapping OCR ground truth.

    ``input_to_scan_homography`` maps input pixel coordinates (x, y, 1) to output
    pixel coordinates, including the placement error. ``page_box_scan_px`` is where the
    page would sit without placement error (the scan margin, if any).
    """
    src_h, src_w = source.rgb.shape[:2]
    to_working = _pixel_scale(page_wh[0] / src_w, page_wh[1] / src_h)
    fx, fy = scan_wh[0] / canvas_wh[0], scan_wh[1] / canvas_wh[1]
    to_scan = _pixel_scale(fx, fy)
    total = to_scan @ placement @ to_working
    rec["input_to_scan_homography"] = (total / total[2, 2]).tolist()
    margin_x = (canvas_wh[0] - page_wh[0]) / 2
    margin_y = (canvas_wh[1] - page_wh[1]) / 2
    rec["page_box_scan_px"] = [
        margin_x * fx,
        margin_y * fy,
        (margin_x + page_wh[0]) * fx,
        (margin_y + page_wh[1]) * fy,
    ]
