"""Print-scan simulator for OCR test data."""

__version__ = "0.1.0"

from scan_sim.batch import BatchReport, process_directory, process_file  # noqa: E402
from scan_sim.config import SimulationConfig, load_config  # noqa: E402
from scan_sim.pipeline import simulate_scan  # noqa: E402

__all__ = [
    "BatchReport",
    "SimulationConfig",
    "__version__",
    "load_config",
    "process_directory",
    "process_file",
    "simulate_scan",
]
