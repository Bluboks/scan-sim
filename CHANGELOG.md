# Changelog

## Unreleased

## 0.1.0 - 2026-10-03

First public release. Implements the v0.1 scope of the
[initial brief](docs/archive/2026-10-02-initial-brief.md), plus PDF input and a browser UI.

- Added the `scan-sim` CLI and the Python API `simulate_scan`, `process_file`,
  `process_directory`, `load_config`.
- Added the fixed 16-step print-scan chain: printer colour/tone, anisotropic printer PSF,
  sub-pixel dot gain and edge roughness, toner density mottle, three-layer paper
  reflectance, reflectance composite, single-homography placement error, scanner
  resampling, scanner PSF, illumination field, read/shot/row/column noise, scanner colour
  matrix and white balance, sRGB tone with smooth background suppression, unsharp
  masking, rare vertical streak and horizontal banding, final JPEG/PNG encoding.
- Added five complete presets: `office-clean`, `office-medium` (default), `office-adf`,
  `office-aged`, `ocr-stress`. Custom YAML files may `extends:` a preset.
- Added config keys not named in the brief: `input.dpi_from_metadata`,
  `input.max_page_mm`, `paper.fiber.elongation`, `scanner.resample`, `scanner.tone`,
  `artifacts.horizontal_banding` (see [ADR-004](docs/decisions/ADR-004-config-schema.md)).
- Seeds are a SHA-256 derivation of (relative input path, base seed, variant); each stage
  has its own random stream. Output is byte-identical across runs and worker counts.
- JSON sidecars record source, preset, base seed, variant seed, DPI, every sampled
  parameter, and library versions.
- Inputs: PNG, JPG, TIFF, BMP. Outputs: JPG, PNG. PDF is v0.2.
- Added PDF input ([ADR-005](docs/decisions/ADR-005-pdf-input.md)). Each page is rendered with
  PDFium (`pypdfium2`) directly at working DPI and processed as its own input. Outputs are
  named `<stem>_p001_scan_0001.jpg`; the page seed key is `<relative>#p<page>`. Sidecars
  record `page`; `input_dpi.origin` can be `pdf-render`.
- Added the optional `web` extra and the `scan-sim-web` browser UI: upload, paste from the
  clipboard, or pick a sample (PDF: one chosen page); choose preset, seed, variants and `--set`
  overrides; compare original and scan with a wipe divider; download the image and JSON
  sidecar. Variant seeds match the CLI. The viewer supports mouse, trackpad pinch, and touch
  (pinch zoom, pan, tap to move the divider, double tap to zoom, split slider on phones).
  See [WEB](docs/ops/WEB.md).
- Samples: five synthetic A4 documents and a 2-page PDF. All names, numbers and addresses in
  them are fictional.
- Licensed under MIT.
