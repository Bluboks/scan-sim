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

    # [7] placement on the scanner glass
    scanner_px = working_dpi / config.scanner.dpi
    sheet = geometry.place_on_scanner(
        sheet,
        config.geometry,
        scanner_px,
        config.paper.base_rgb,
        stage_rng(seed, "geometry"),
        rec,
    )

    # [8]-[14] scanner
    srng = stage_rng(seed, "scanner")
    scan = scanner.resample(sheet, config.scanner, working_dpi)
    del sheet
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
