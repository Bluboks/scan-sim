"""Small web UI: upload or pick a document, choose a preset, compare original and scan.

Run with ``scan-sim-web`` (needs the ``web`` extra). Jobs run one at a time because one
A4 page needs about 2.4 GB of memory. Results live under ``--data-dir``; only the most
recent jobs are kept.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from scan_sim.batch import output_name, process_file, seed_key
from scan_sim.config import SimulationConfig, list_presets, load_config, preset_summary
from scan_sim.errors import ScanSimError
from scan_sim.io import INPUT_SUFFIXES, read_source
from scan_sim.pdf import is_pdf, page_count
from scan_sim.rng import derive_seed

log = logging.getLogger("scan_sim.web")

STATIC = Path(__file__).parent / "static"
REPO_SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "input"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_VARIANTS = 6
KEEP_JOBS = 40
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")
_FILE_NAME = re.compile(r"^(original_\d{4}\.png|scan_\d{4}\.(jpg|png|json))$")


def create_app(data_dir: Path, samples_dir: Path | None) -> FastAPI:
    app = FastAPI(title="scan-sim", docs_url=None, redoc_url=None)
    jobs_dir = data_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    run_lock = threading.Lock()

    def sample_files() -> dict[str, Path]:
        return _sample_files(samples_dir)

    @app.exception_handler(Exception)
    async def unexpected(_request: Any, exc: Exception) -> JSONResponse:
        log.exception("unexpected error")
        detail = f"{type(exc).__name__}: {exc}"
        tb = "".join(traceback.format_exception(exc))
        return JSONResponse({"detail": detail, "traceback": tb}, status_code=500)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/options")
    def options() -> dict[str, Any]:
        return {
            "presets": [{"name": n, "summary": preset_summary(n)} for n in list_presets()],
            "default_preset": "office-medium",
            "samples": list(sample_files()),
            "max_variants": MAX_VARIANTS,
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        }

    @app.get("/samples/{name}")
    def sample(name: str) -> FileResponse:
        path = sample_files().get(name)
        if path is None:
            raise HTTPException(404, f"no sample named {name!r}")
        return FileResponse(path)

    @app.post("/api/jobs")
    def create_job(
        file: Annotated[UploadFile | None, File()] = None,
        sample: Annotated[str, Form()] = "",
        preset: Annotated[str, Form()] = "office-medium",
        seed: Annotated[int, Form()] = 0,
        variants: Annotated[int, Form()] = 1,
        overrides: Annotated[str, Form()] = "",
        page: Annotated[int, Form()] = 1,
    ) -> dict[str, Any]:
        set_lines = [line.strip() for line in overrides.splitlines() if line.strip()]
        config, label = _job_config(preset, variants, set_lines)

        job_id = uuid.uuid4().hex
        job_dir = jobs_dir / job_id
        job_dir.mkdir()
        source_name, source_path = _store_input(job_dir, file, sample, sample_files())
        started = time.perf_counter()
        # PDFium is not thread-safe, so page counting and preview stay under the lock too.
        with run_lock:
            pages, page_or_none = _resolve_page(source_name, source_path, page)
            results = _run_variants(
                job_id,
                job_dir,
                source_name,
                source_path,
                page_or_none,
                config,
                label,
                seed,
                variants,
                _original_image(source_path, page_or_none, config),
            )
        elapsed = time.perf_counter() - started
        _prune(jobs_dir, keep=KEEP_JOBS)
        return {
            "id": job_id,
            "source": source_name,
            "page": page_or_none,
            "page_count": pages,
            "preset": label,
            "base_seed": seed,
            "overrides": set_lines,
            "size": results[0]["size"],
            "dpi": config.scanner.dpi,
            "elapsed_s": round(elapsed, 1),
            "variants": results,
            "cli": _cli_equivalent(source_name, preset, seed, variants, set_lines),
        }

    @app.get("/files/{job_id}/{name}")
    def job_file(job_id: str, name: str) -> FileResponse:
        if not _JOB_ID.match(job_id) or not _FILE_NAME.match(name):
            raise HTTPException(404, "not found")
        path = jobs_dir / job_id / name
        if not path.is_file():
            raise HTTPException(404, "result no longer exists (old jobs are deleted)")
        return FileResponse(path)

    return app


def _sample_files(samples_dir: Path | None) -> dict[str, Path]:
    if samples_dir is None or not samples_dir.is_dir():
        return {}
    return {
        p.name: p
        for p in sorted(samples_dir.iterdir())
        if p.is_file() and p.suffix.lower() in INPUT_SUFFIXES
    }


def _job_config(preset: str, variants: int, set_lines: list[str]) -> tuple[SimulationConfig, str]:
    if not 1 <= variants <= MAX_VARIANTS:
        raise HTTPException(400, f"variants must be 1..{MAX_VARIANTS}, got {variants}")
    if preset not in list_presets():
        raise HTTPException(400, f"unknown preset {preset!r}")
    try:
        return load_config(preset, overrides=set_lines)
    except ScanSimError as exc:
        raise HTTPException(400, str(exc)) from exc


def _resolve_page(source_name: str, source_path: Path, page: int) -> tuple[int | None, int | None]:
    """(page count, page to render) for a PDF; (None, None) for an image."""
    if not is_pdf(source_path):
        return None, None
    try:
        pages = page_count(source_path)
    except ScanSimError as exc:
        raise HTTPException(400, str(exc).replace(str(source_path), source_name)) from exc
    if not 1 <= page <= pages:
        raise HTTPException(400, f"{source_name}: page {page} out of range; the PDF has {pages}")
    return pages, page


def _run_variants(
    job_id: str,
    job_dir: Path,
    source_name: str,
    source_path: Path,
    page: int | None,
    config: SimulationConfig,
    label: str,
    seed: int,
    variants: int,
    original: Image.Image,
) -> list[dict[str, Any]]:
    """Same seeds as ``scan-sim <file> <dir> --seed S --variants N`` (relative = file name).

    Each variant gets its own original preview, because the scan margin (and so the
    output size) can differ per variant.
    """
    results = []
    for v in range(1, variants + 1):
        vseed = derive_seed(seed_key(source_name, page), seed, v)
        out = job_dir / f"scan_{v:04d}.{config.encoding.format}"
        try:
            meta = process_file(
                source_path,
                out,
                config,
                vseed,
                config_label=label,
                base_seed=seed,
                variant=v,
                relative=source_name,
                save_metadata=True,
                page=page,
            )
        except ScanSimError as exc:
            raise HTTPException(400, str(exc).replace(str(source_path), source_name)) from exc
        with Image.open(out) as scanned:
            size = scanned.size
        preview = job_dir / f"original_{v:04d}.png"
        _write_original_preview(original, meta["parameters"]["page_box_scan_px"], size, preview)
        results.append(
            {
                "variant": v,
                "size": list(size),
                "original": f"/files/{job_id}/{preview.name}",
                # 63-bit seeds exceed JavaScript's exact integer range; send as text.
                "seed": str(vseed),
                "download_name": output_name(Path(source_name).stem, page, v, out.suffix),
                "image": f"/files/{job_id}/{out.name}",
                "metadata": f"/files/{job_id}/{out.with_suffix('.json').name}",
                "parameters": meta["parameters"],
            }
        )
    return results


def _store_input(
    job_dir: Path, upload: UploadFile | None, sample: str, samples: dict[str, Path]
) -> tuple[str, Path]:
    if upload is not None and upload.filename:
        name = Path(upload.filename).name
        suffix = Path(name).suffix.lower()
        if suffix not in INPUT_SUFFIXES:
            allowed = ", ".join(sorted(INPUT_SUFFIXES))
            raise HTTPException(400, f"{name}: unsupported file type; use one of {allowed}")
        data = upload.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{name}: larger than {MAX_UPLOAD_BYTES // 2**20} MB")
        path = job_dir / f"input{suffix}"
        path.write_bytes(data)
        return name, path
    if sample:
        src = samples.get(sample)
        if src is None:
            raise HTTPException(400, f"no sample named {sample!r}")
        path = job_dir / f"input{src.suffix.lower()}"
        shutil.copyfile(src, path)
        return sample, path
    raise HTTPException(400, "upload a file or choose a sample")


def _original_image(source: Path, page: int | None, config: SimulationConfig) -> Image.Image:
    """The input as the viewer shows it: PDF pages rendered at scanner DPI, alpha on white."""
    original = read_source(source, config.input, float(config.scanner.dpi), page)
    rgb = np.rint(np.clip(original.rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def _write_original_preview(
    original: Image.Image, page_box: list[float], size: tuple[int, int], target: Path
) -> None:
    """Original placed where the page sits in the scan (no placement error), for overlaying.

    Outside the page (scan margin) stays neutral grey.
    """
    x0, y0, x1, y1 = (round(v) for v in page_box)
    page = original.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (128, 128, 128))
    canvas.paste(page, (x0, y0))
    canvas.save(target, compress_level=3)


def _prune(jobs_dir: Path, keep: int) -> None:
    dirs = sorted((d for d in jobs_dir.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
    for old in dirs[:-keep]:
        shutil.rmtree(old)


def _cli_equivalent(name: str, preset: str, seed: int, variants: int, sets: list[str]) -> str:
    parts = ["scan-sim", name, "./out", "--preset", preset, "--seed", str(seed)]
    if variants > 1:
        parts += ["--variants", str(variants)]
    for s in sets:
        parts += ["--set", s]
    return " ".join(parts)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="scan-sim-web", description="scan-sim browser UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8789)
    p.add_argument("--data-dir", type=Path, default=Path(".web-data"))
    p.add_argument("--samples-dir", type=Path, default=REPO_SAMPLES)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = create_app(args.data_dir.resolve(), args.samples_dir)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
