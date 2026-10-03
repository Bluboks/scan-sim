"""Simulation configuration: strict schema, preset loading, and CLI overrides.

Every physical parameter is either a fixed number or a ``[min, max]`` range that is
sampled per variant. Presets are complete YAML files; the schema has no hidden
defaults for physics parameters, so a preset documents everything it does.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from scan_sim.errors import ConfigError

PRESET_DIR = Path(__file__).parent / "configs"


def _check_range(value: Any) -> Any:
    if isinstance(value, tuple) and value[0] > value[1]:
        raise ValueError(f"range min {value[0]} is greater than max {value[1]}")
    return value


Range = Annotated[float | tuple[float, float], AfterValidator(_check_range)]
IntRange = Annotated[int | tuple[int, int], AfterValidator(_check_range)]
Vec3 = tuple[float, float, float]
Matrix3 = tuple[Vec3, Vec3, Vec3]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InputConfig(_Model):
    assumed_dpi: float = Field(gt=0)
    dpi_from_metadata: bool
    max_page_mm: float = Field(gt=0)


class WorkingConfig(_Model):
    dpi: float = Field(gt=0)


class PsfConfig(_Model):
    sigma_x: Range
    sigma_y: Range


class DotGainConfig(_Model):
    enabled: bool
    radius_px: Range
    strength: Range


class TonerDensityConfig(_Model):
    strength: Range
    scale_px: Range


class PrinterConfig(_Model):
    color_matrix: Matrix3
    gamma: Range
    black_density: Range
    psf: PsfConfig
    dot_gain: DotGainConfig
    edge_roughness_px: Range
    toner_density_noise: TonerDensityConfig


class NoiseLayerConfig(_Model):
    strength: Range
    scale_px: Range


class FiberConfig(_Model):
    strength: Range
    scale_px: Range
    elongation: Range


class FineGrainConfig(_Model):
    strength: Range


class PaperConfig(_Model):
    base_rgb: Vec3
    low_frequency: NoiseLayerConfig
    fiber: FiberConfig
    fine_grain: FineGrainConfig


class TranslationConfig(_Model):
    x: Range
    y: Range


class PerspectiveConfig(_Model):
    enabled: bool
    max_corner_shift_ratio: float = Field(ge=0)


class BackingConfig(_Model):
    rgb: Vec3
    brightness: Range
    texture_strength: Range


class EdgeShadowConfig(_Model):
    strength: Range
    width_px: Range


class GeometryConfig(_Model):
    rotation_deg: Range
    scale_x: Range
    scale_y: Range
    translation_px: TranslationConfig
    perspective: PerspectiveConfig
    scan_margin_mm: Range
    backing: BackingConfig
    edge_shadow: EdgeShadowConfig


class IlluminationConfig(_Model):
    strength: Range
    edge_falloff: Range


class SensorNoiseConfig(_Model):
    gaussian_sigma: Range
    shot_strength: Range
    row_sigma: Range
    column_sigma: Range


class ToneConfig(_Model):
    gamma: Range
    black_level: Range
    white_level: Range


class BackgroundSuppressionConfig(_Model):
    enabled: bool
    threshold: Range
    strength: Range


class SharpeningConfig(_Model):
    enabled: bool
    sigma: Range
    amount: Range


class ScannerConfig(_Model):
    dpi: int = Field(gt=0)
    resample: Literal["area", "lanczos", "cubic"]
    psf: PsfConfig
    illumination: IlluminationConfig
    noise: SensorNoiseConfig
    color_matrix: Matrix3
    white_balance: tuple[Range, Range, Range]
    tone: ToneConfig
    background_suppression: BackgroundSuppressionConfig
    sharpening: SharpeningConfig


class VerticalStreakConfig(_Model):
    probability: float = Field(ge=0, le=1)
    strength: Range
    width_px: IntRange


class HorizontalBandingConfig(_Model):
    probability: float = Field(ge=0, le=1)
    strength: Range
    scale_px: Range


class ArtifactsConfig(_Model):
    vertical_streak: VerticalStreakConfig
    horizontal_banding: HorizontalBandingConfig


class EncodingConfig(_Model):
    format: Literal["jpg", "png"]
    jpeg_quality: IntRange
    subsampling: Literal["auto", "444", "422", "420"]


class MetadataConfig(_Model):
    save: bool


class SimulationConfig(_Model):
    input: InputConfig
    working: WorkingConfig
    printer: PrinterConfig
    paper: PaperConfig
    geometry: GeometryConfig
    scanner: ScannerConfig
    artifacts: ArtifactsConfig
    encoding: EncodingConfig
    metadata: MetadataConfig


def list_presets() -> list[str]:
    return sorted(p.stem for p in PRESET_DIR.glob("*.yaml"))


def preset_summary(name: str) -> str:
    """The preset's leading YAML comment block, without the shared boilerplate lines."""
    lines = []
    for line in preset_path(name).read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        text = line.lstrip("# ").rstrip()
        if text.startswith(("Units and meaning", "A two-item list")):
            continue
        lines.append(text)
    return " ".join(lines)


def preset_path(name: str) -> Path:
    path = PRESET_DIR / f"{name}.yaml"
    if not path.is_file():
        raise ConfigError(f"unknown preset {name!r}; available: {', '.join(list_presets())}")
    return path


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_raw(path: Path, _seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    """Read a config file, resolving ``extends: <preset name>`` chains."""
    resolved = path.resolve()
    if resolved in _seen:
        chain = " -> ".join(str(p) for p in (*_seen, resolved))
        raise ConfigError(f"circular 'extends' chain: {chain}")
    data = _read_yaml(path)
    parent = data.pop("extends", None)
    if parent is None:
        return data
    if not isinstance(parent, str):
        raise ConfigError(f"{path}: 'extends' must be a preset name, got {parent!r}")
    return _deep_merge(load_raw(preset_path(parent), (*_seen, resolved)), data)


def parse_override(text: str) -> tuple[list[str], Any]:
    """Parse ``a.b.c=value``. ``1,2`` becomes a list; each item is a YAML scalar."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise ConfigError(f"--set expects key.path=value, got {text!r}")
    parts = [p.strip() for p in key.split(".")]
    if any(not p for p in parts):
        raise ConfigError(f"--set has an empty key segment: {text!r}")
    try:
        if "," in raw and not raw.strip().startswith("["):
            value: Any = [yaml.safe_load(item) for item in raw.split(",")]
        else:
            value = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"--set {text!r}: value is not valid YAML: {exc}") from exc
    return parts, value


def apply_overrides(data: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    result = copy.deepcopy(data)
    for text in overrides:
        parts, value = parse_override(text)
        node = result
        for depth, part in enumerate(parts[:-1]):
            child = node.get(part)
            if not isinstance(child, dict):
                where = ".".join(parts[: depth + 1])
                raise ConfigError(f"--set {text!r}: {where!r} is not a config section")
            node = child
        if parts[-1] not in node:
            raise ConfigError(f"--set {text!r}: unknown key {'.'.join(parts)!r}")
        node[parts[-1]] = value
    return result


def build_config(data: dict[str, Any], source: str) -> SimulationConfig:
    try:
        return SimulationConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{source}: invalid configuration\n{exc}") from exc


def load_config(
    preset: str | None = None,
    config_path: Path | None = None,
    overrides: list[str] | None = None,
) -> tuple[SimulationConfig, str]:
    """Return the validated config and a label naming where it came from."""
    if preset is not None and config_path is not None:
        raise ConfigError("use either a preset or a config file, not both")
    if config_path is not None:
        data, label = load_raw(config_path), str(config_path)
    else:
        name = preset or "office-medium"
        data, label = load_raw(preset_path(name)), name
    data = apply_overrides(data, overrides or [])
    return build_config(data, label), label
