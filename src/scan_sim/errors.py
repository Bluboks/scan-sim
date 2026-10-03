"""User-facing error types. Their messages are printed verbatim by the CLI."""


class ScanSimError(Exception):
    """An expected failure caused by input, configuration, or file system state."""


class ConfigError(ScanSimError):
    """The configuration or a ``--set`` override is invalid."""


class InputImageError(ScanSimError):
    """An input image cannot be read or has an implausible physical size."""
