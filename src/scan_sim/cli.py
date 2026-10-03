"""``scan-sim`` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scan_sim import __version__
from scan_sim.batch import check_existing, plan_jobs, run_jobs
from scan_sim.config import list_presets, load_config
from scan_sim.encoding import SUFFIX_FORMAT
from scan_sim.errors import ScanSimError

EXIT_FAILURES = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan-sim",
        description="Make digital documents look like office print-then-scan copies.",
    )
    p.add_argument("input", type=Path, help="input image or directory")
    p.add_argument("output", type=Path, help="output file (one variant) or directory")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--preset", choices=list_presets(), help="built-in preset (office-medium)")
    src.add_argument("--config", type=Path, help="YAML config file (may use 'extends: <preset>')")
    p.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override one config value, e.g. geometry.rotation_deg=-0.5,0.5 (repeatable)",
    )
    p.add_argument("--variants", type=int, default=1, help="scans per input (default 1)")
    p.add_argument("--seed", type=int, default=0, help="base seed (default 0)")
    p.add_argument("--workers", type=int, default=1, help="parallel processes (default 1)")
    p.add_argument("--save-metadata", action="store_true", help="always write JSON sidecars")
    p.add_argument("--overwrite", action="store_true", help="replace existing outputs")
    p.add_argument("--dry-run", action="store_true", help="list planned outputs and exit")
    p.add_argument("--no-progress", action="store_true", help="hide the progress bar")
    p.add_argument("--version", action="version", version=f"scan-sim {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except ScanSimError as exc:
        print(f"scan-sim: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def _run(args: argparse.Namespace) -> int:
    config, label = load_config(args.preset, args.config, args.set)
    fmt: str = config.encoding.format
    if args.input.is_file() and args.output.suffix and not args.output.is_dir():
        fmt = SUFFIX_FORMAT.get(args.output.suffix.lower(), fmt)
    jobs = plan_jobs(args.input, args.output, args.variants, args.seed, fmt)

    if args.dry_run:
        for job in jobs:
            print(
                f"{job.input_path}{'' if job.page is None else f' p{job.page}'} -> "
                f"{job.output_path}  (variant {job.variant}, seed {job.seed})"
            )
        print(f"{len(jobs)} scan(s) planned with {label}", file=sys.stderr)
        return 0
    if not args.overwrite:
        check_existing(jobs)

    save = True if args.save_metadata else None
    report = run_jobs(
        jobs, config, args.seed, args.workers, label, save, progress=not args.no_progress
    )
    for job, message in report.failures:
        print(
            f"scan-sim: failed: {job.input_path}{'' if job.page is None else f' p{job.page}'} "
            f"(variant {job.variant}): {message}",
            file=sys.stderr,
        )
    print(f"{len(report.written)} written, {len(report.failures)} failed", file=sys.stderr)
    return EXIT_FAILURES if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
