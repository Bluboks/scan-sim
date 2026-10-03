"""File and directory processing: job planning, naming, seeds, workers, sidecars."""

from __future__ import annotations

import functools
import multiprocessing
import os
import sys
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
from tqdm import tqdm

from scan_sim.config import SimulationConfig
from scan_sim.encoding import FORMAT_SUFFIX, SUFFIX_FORMAT, sample_encoding, write_image
from scan_sim.errors import ScanSimError
from scan_sim.io import INPUT_SUFFIXES, read_source
from scan_sim.metadata import build_metadata, write_metadata
from scan_sim.pdf import is_pdf, page_count
from scan_sim.pipeline import simulate_source
from scan_sim.rng import derive_seed, stage_rng


@dataclass(frozen=True)
class Job:
    input_path: Path
    output_path: Path
    relative: str  # input path relative to the input root; part of the seed
    variant: int  # 1-based
    seed: int
    page: int | None = None  # 1-based PDF page; None for image files


@dataclass
class BatchReport:
    jobs: list[Job]
    written: list[Path] = field(default_factory=list)
    failures: list[tuple[Job, str]] = field(default_factory=list)


def process_file(
    input_path: Path,
    output_path: Path,
    config: SimulationConfig,
    seed: int,
    *,
    config_label: str = "custom",
    base_seed: int | None = None,
    variant: int | None = None,
    relative: str | None = None,
    save_metadata: bool | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Simulate one scan of ``input_path`` and write it (plus optional JSON sidecar).

    ``page`` (1-based) is required for a PDF and must be None for an image. The output
    format follows the output suffix. Returns the metadata record.
    """
    fmt = SUFFIX_FORMAT.get(output_path.suffix.lower())
    if fmt is None:
        raise ScanSimError(f"{output_path}: output suffix must be one of {sorted(SUFFIX_FORMAT)}")
    if fmt != config.encoding.format:
        config = config.model_copy(
            update={"encoding": config.encoding.model_copy(update={"format": fmt})}
        )

    source = read_source(input_path, config.input, config.working.dpi, page)
    img, params = simulate_source(source, config, seed)
    encoding = sample_encoding(config.encoding, stage_rng(seed, "encoding"))
    params.update(encoding)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_name(f".{output_path.name}.part")
    write_image(tmp, img, config.scanner.dpi, config.encoding, encoding)
    os.replace(tmp, output_path)

    meta = build_metadata(
        source=relative or input_path.name,
        page=page,
        output=output_path.name,
        config_label=config_label,
        base_seed=base_seed,
        seed=seed,
        variant=variant,
        dpi=config.scanner.dpi,
        input_dpi=(source.dpi_x, source.dpi_y, source.dpi_origin),
        parameters=params,
    )
    if config.metadata.save if save_metadata is None else save_metadata:
        write_metadata(output_path.with_suffix(".json"), meta)
    return meta


def seed_key(relative: str, page: int | None) -> str:
    """The input identity hashed into a variant seed (ADR-003); PDF pages get a suffix."""
    return relative if page is None else f"{relative}#p{page}"


def output_name(stem: str, page: int | None, variant: int, suffix: str) -> str:
    page_part = "" if page is None else f"_p{page:03d}"
    return f"{stem}{page_part}_scan_{variant:04d}{suffix}"


def plan_jobs(
    input_path: Path, output_path: Path, variants: int, base_seed: int, fmt: str
) -> list[Job]:
    """Decide every output path and seed up front; fail before any work is done.

    A PDF contributes one job per page and variant.
    """
    if variants < 1:
        raise ScanSimError(f"--variants must be at least 1, got {variants}")
    if not input_path.exists():
        raise ScanSimError(f"input {input_path} does not exist")

    if input_path.is_file():
        sources = [(input_path, input_path.name)]
        if output_path.suffix and not output_path.is_dir():
            return [_single_output_job(input_path, output_path, variants, base_seed)]
    else:
        sources = _discover(input_path, output_path)

    suffix = FORMAT_SUFFIX[fmt]
    jobs = []
    for path, relative in sources:
        rel_dir = Path(relative).parent
        pages: list[int | None] = list(range(1, page_count(path) + 1)) if is_pdf(path) else [None]
        for page in pages:
            for v in range(1, variants + 1):
                out = output_path / rel_dir / output_name(path.stem, page, v, suffix)
                seed = derive_seed(seed_key(relative, page), base_seed, v)
                jobs.append(Job(path, out, relative, v, seed, page))
    _check_collisions(jobs)
    return jobs


def _single_output_job(input_path: Path, output_path: Path, variants: int, base_seed: int) -> Job:
    """One input file written to exactly the given output file."""
    if variants != 1:
        raise ScanSimError(
            f"output {output_path} is a single file but --variants is {variants}; "
            "give an output directory instead"
        )
    page = None
    if is_pdf(input_path):
        pages = page_count(input_path)
        if pages != 1:
            raise ScanSimError(
                f"{input_path} has {pages} pages but output {output_path} is a single file; "
                "give an output directory instead"
            )
        page = 1
    relative = input_path.name
    seed = derive_seed(seed_key(relative, page), base_seed, 1)
    return Job(input_path, output_path, relative, 1, seed, page)


def _discover(input_dir: Path, output_dir: Path) -> list[tuple[Path, str]]:
    root = input_dir.resolve()
    out = output_dir.resolve()
    if out == root or root in out.parents:
        raise ScanSimError(
            f"output directory {output_dir} is inside input directory {input_dir}; "
            "outputs would be picked up as inputs on the next run"
        )
    found = sorted(
        p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in INPUT_SUFFIXES
    )
    if not found:
        suffixes = ", ".join(sorted(INPUT_SUFFIXES))
        raise ScanSimError(f"no inputs ({suffixes}) under {input_dir}")
    return [(p, p.relative_to(input_dir).as_posix()) for p in found]


def _check_collisions(jobs: list[Job]) -> None:
    owners: dict[Path, str] = {}
    clashes = []
    for job in jobs:
        prior = owners.setdefault(job.output_path, job.relative)
        if prior != job.relative:
            clashes.append(f"{prior} and {job.relative} -> {job.output_path.name}")
    if clashes:
        raise ScanSimError(
            "inputs with the same name but different extensions would overwrite each other: "
            + "; ".join(clashes[:5])
        )


def check_existing(jobs: list[Job]) -> None:
    existing = [j.output_path for j in jobs if j.output_path.exists()]
    if existing:
        listed = ", ".join(str(p) for p in existing[:3])
        more = f" and {len(existing) - 3} more" if len(existing) > 3 else ""
        raise ScanSimError(f"output already exists: {listed}{more}; pass --overwrite to replace")


def process_directory(
    input_dir: Path,
    output_dir: Path,
    config: SimulationConfig,
    variants: int,
    seed: int,
    workers: int,
    *,
    config_label: str = "custom",
    save_metadata: bool | None = None,
    overwrite: bool = False,
    progress: bool = True,
) -> BatchReport:
    """Generate ``variants`` scans of every image under ``input_dir`` (or of one file)."""
    jobs = plan_jobs(input_dir, output_dir, variants, seed, config.encoding.format)
    if not overwrite:
        check_existing(jobs)
    return run_jobs(jobs, config, seed, workers, config_label, save_metadata, progress)


def run_jobs(
    jobs: list[Job],
    config: SimulationConfig,
    base_seed: int,
    workers: int,
    config_label: str,
    save_metadata: bool | None,
    progress: bool,
) -> BatchReport:
    report = BatchReport(jobs)
    args = (config, base_seed, config_label, save_metadata)
    bar = tqdm(total=len(jobs), unit="scan", disable=not progress, file=sys.stderr)
    if workers <= 1:
        for job in jobs:
            _collect(report, job, functools.partial(_run_job, job, *args))
            bar.update()
    else:
        ctx = multiprocessing.get_context("spawn")  # same behaviour on Linux and Windows
        with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_init_worker) as pool:
            futures: dict[Future[Path], Job] = {pool.submit(_run_job, j, *args): j for j in jobs}
            for future, job in futures.items():
                _collect(report, job, future.result)
                bar.update()
    bar.close()
    return report


def _collect(report: BatchReport, job: Job, get: Callable[[], Path]) -> None:
    try:
        report.written.append(get())
    except ScanSimError as exc:
        report.failures.append((job, str(exc)))
    except Exception:  # unexpected: keep the full traceback for the report
        report.failures.append((job, traceback.format_exc()))


def _init_worker() -> None:
    # Workers already run in parallel; nested OpenCV threads would oversubscribe the CPU.
    cv2.setNumThreads(1)


def _run_job(
    job: Job,
    config: SimulationConfig,
    base_seed: int,
    config_label: str,
    save_metadata: bool | None,
) -> Path:
    process_file(
        job.input_path,
        job.output_path,
        config,
        job.seed,
        config_label=config_label,
        base_seed=base_seed,
        variant=job.variant,
        relative=job.relative,
        save_metadata=save_metadata,
        page=job.page,
    )
    return job.output_path
