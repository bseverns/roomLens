"""Mapping helpers shared across hosts and tools.

The original prototype stored all transformation helpers directly in
``host/python/app.py``. That made workshops harder because every other script
had to reimplement the same mic/tof/light plumbing. This module is the
central, documented home for those helpers so firmware shims, capture tools,
and notebooks all share the same assumptions.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

import yaml

Frame = Mapping[str, Any]
MappingDict = Dict[str, Any]
Transform = Callable[[float], float]
TransformFactory = Callable[..., Transform]


# ---------------------------------------------------------------------------
# Basic math helpers
# ---------------------------------------------------------------------------
def clamp01(x: float) -> float:
    """Clamp ``x`` into the inclusive ``[0, 1]`` range."""

    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation helper."""

    return a + (b - a) * t


def _identity(x: float) -> float:
    return x


def log10_clamp(*, floor_db: float = -60.0) -> Transform:
    """Return a callable that maps linear amplitude to ``[0, 1]`` via dB scaling."""

    floor_db = float(floor_db)

    def _inner(x: float) -> float:
        if x <= 0.0:
            return 0.0
        db = 20.0 * math.log10(x)
        # Normalize so ``floor_db`` → 0 and ``0 dB`` → 1.
        norm = (db - floor_db) / max(-floor_db, 1e-9)
        return clamp01(norm)

    return _inner


def softclip(threshold: float = 0.8, *, slope: float = 4.0) -> Transform:
    """Return a soft clipping curve for values above ``threshold``."""

    threshold = clamp01(float(threshold))
    slope = max(float(slope), 1.0)

    def _inner(x: float) -> float:
        x = clamp01(x)
        if x <= threshold or threshold >= 1.0:
            return x
        t = (x - threshold) / (1.0 - threshold)
        eased = t ** slope
        return clamp01(threshold + (1.0 - threshold) * eased)

    return _inner


def inverse_exp(*, centers: list[float] | tuple[float, ...], k: float = 1.0) -> Transform:
    """Return a callable that weights proximity to one or more ``centers``.

    ``centers`` should contain positive reference distances. Values at or beyond
    a centre decay exponentially toward zero, while values closer than the
    centre approach one.
    """

    centers = [float(c) for c in centers if float(c) > 0.0] if centers else []
    if not centers:
        centers = [1.0]
    k = float(k)
    if k <= 0.0:
        k = 1.0

    def _inner(x: float) -> float:
        x = float(x)
        scores = []
        for centre in centers:
            if x >= centre:
                scores.append(0.0)
                continue
            norm = (centre - x) / centre
            scores.append(1.0 - math.exp(-k * norm))
        return clamp01(sum(scores) / len(scores))

    return _inner


_TRANSFORM_FACTORIES: Dict[str, TransformFactory] = {
    "log10_clamp": log10_clamp,
    "inverse_exp": inverse_exp,
    "softclip": softclip,
    "identity": lambda: _identity,
    "clamp01": lambda: clamp01,
}

_TRANSFORM_CACHE: Dict[str, Transform] = {}


def _parse_transform_spec(spec: str) -> tuple[str, tuple[Any, ...], Dict[str, Any]]:
    """Parse a ``transform`` specification string into name/args/kwargs."""

    spec = spec.strip()
    if not spec:
        raise ValueError("Empty transform spec")
    try:
        expr = ast.parse(spec, mode="eval").body
    except SyntaxError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid transform syntax: {spec!r}") from exc

    if isinstance(expr, ast.Name):
        return expr.id, (), {}
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
        args = tuple(ast.literal_eval(arg) for arg in expr.args)
        kwargs = {
            kw.arg: ast.literal_eval(kw.value)
            for kw in expr.keywords
            if kw.arg is not None
        }
        return expr.func.id, args, kwargs
    raise ValueError(f"Unsupported transform spec: {spec!r}")


def _resolve_transform(feature_cfg: Mapping[str, Any]) -> Transform:
    transform_spec = feature_cfg.get("transform")
    if not transform_spec:
        return _identity

    if callable(transform_spec):
        return transform_spec  # type: ignore[return-value]

    if not isinstance(transform_spec, str):
        raise TypeError(
            "transform must be a string or callable, got "
            f"{type(transform_spec).__name__}"
        )

    cached = _TRANSFORM_CACHE.get(transform_spec)
    if cached:
        return cached

    name, args, kwargs = _parse_transform_spec(transform_spec)
    factory = _TRANSFORM_FACTORIES.get(name)
    if not factory:
        raise ValueError(f"Unknown transform '{name}' for feature {feature_cfg!r}")
    try:
        transform = factory(*args, **kwargs)
    except TypeError as exc:
        raise TypeError(
            f"Transform '{name}' could not be constructed: {exc}"
        ) from exc
    _TRANSFORM_CACHE[transform_spec] = transform
    return transform


# ---------------------------------------------------------------------------
# Mapping file I/O
# ---------------------------------------------------------------------------
def load_mapping(path: str | Path) -> MappingDict:
    """Load the YAML mapping specification.

    Parameters
    ----------
    path:
        Path to the YAML file. Strings are converted to :class:`Path`
        internally.
    """

    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_mapping_axes(mapping: MappingDict) -> None:
    """Ensure every declared feature resolves to a synth axis.

    A missing ``axis`` silently drops data on the floor. We fail fast with a
    ``ValueError`` so workshops notice the misconfiguration before a show or
    class run.
    """

    missing: list[str] = []
    for sensor_name, sensor_cfg in mapping.get("sensors", {}).items():
        for feature_name, feature_cfg in sensor_cfg.get("features", {}).items():
            if not feature_cfg.get("map_to", {}).get("axis"):
                missing.append(f"{sensor_name}.{feature_name}")
    if missing:
        raise ValueError(
            "Mapping entries missing map_to.axis: " + ", ".join(sorted(missing))
        )


# ---------------------------------------------------------------------------
# Frame processing
# ---------------------------------------------------------------------------
# Default resolvers per (sensor, feature).
FrameResolver = Callable[[Frame], float]
_DEFAULT_RESOLVERS: Dict[tuple[str, str], FrameResolver] = {
    ("mic", "rms"): lambda frame: float(frame.get("mic_rms", 0.0)),
    ("mic", "spectral_centroid"): lambda frame: float(
        frame.get("mic_sc", frame.get("mic_centroid", 0.0))
    ),
    (
        "mic",
        "hf_rolloff",
    ): lambda frame: float(
        frame.get("mic_hf", frame.get("hf", frame.get("mic_sc", 0.0)))
    ),
    ("tof", "motion_energy"): lambda frame: float(frame.get("tof_motion", 0.0)),
    ("tof", "proximity"): lambda frame: float(frame.get("tof_near", 0.0)),
    ("light", "lux"): lambda frame: float(frame.get("lux", 0.0)),
    ("light", "flicker_hz"): lambda frame: float(frame.get("flicker", 0.0)),
    ("motion", "burst"): lambda frame: float(1.0 if frame.get("motion") else 0.0),
    ("climate", "drift"): lambda frame: float(frame.get("climate_drift", 0.0)),
    (
        "presence",
        "count",
    ): lambda frame: float(frame.get("presence_count", frame.get("count", 0.0))),
}


def _resolve_feature_value(
    sensor_name: str, feature_name: str, feature_cfg: Mapping[str, Any], frame: Frame
) -> float:
    """Derive the normalized feature value from an incoming frame.

    The YAML config can specify ``frame_key`` to override the lookup. Otherwise
    we fall back to the baked-in resolvers above and finally a set of string
    heuristics. This keeps the pipeline predictable for classrooms while still
    letting hackers reroute values.
    """

    frame_key = feature_cfg.get("frame_key")
    if frame_key:
        return float(frame.get(frame_key, 0.0))

    source = feature_cfg.get("source")
    if isinstance(source, str) and source:
        candidates = [part.strip() for part in source.split("|") if part.strip()]
        if not candidates:
            candidates = [source]
        for candidate in candidates:
            if candidate in frame:
                return float(frame.get(candidate, 0.0))
    elif isinstance(source, (list, tuple)):
        for candidate in source:
            if isinstance(candidate, str) and candidate in frame:
                return float(frame.get(candidate, 0.0))

    resolver = _DEFAULT_RESOLVERS.get((sensor_name, feature_name))
    if resolver:
        return resolver(frame)

    # Heuristic fallback: try ``{sensor}_{feature}`` then raw ``feature``.
    compound_key = f"{sensor_name}_{feature_name}"
    if compound_key in frame:
        return float(frame.get(compound_key, 0.0))
    return float(frame.get(feature_name, 0.0))


def _apply_single_feature(
    sensor_name: str,
    feature_name: str,
    feature_cfg: Mapping[str, Any],
    frame: Frame,
    axes: Dict[str, float],
) -> None:
    map_to = feature_cfg.get("map_to", {})
    axis = map_to.get("axis")
    if not axis:
        return

    raw_value = _resolve_feature_value(sensor_name, feature_name, feature_cfg, frame)
    transform = _resolve_transform(feature_cfg)
    transformed = transform(raw_value)
    t = clamp01(transformed)
    rng = map_to.get("range", [0.0, 1.0])
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        lo, hi = float(rng[0]), float(rng[1])
    else:
        # Defensive: if the mapping forgot a range we just forward the raw value.
        lo, hi = 0.0, 1.0
    axes[axis] = lerp(lo, hi, t)


SensorProcessor = Callable[[str, Frame, Mapping[str, Any], Dict[str, float]], None]


def apply_mapping(
    frame: Frame,
    mapping: MappingDict,
    *,
    processors: Mapping[str, SensorProcessor] | None = None,
) -> Dict[str, float]:
    """Map normalized sensor features to synth axes.

    Parameters
    ----------
    frame:
        Normalized feature dictionary from firmware, capture logs, or
        :func:`roomlens.demo.demo_frame`.
    mapping:
        YAML-derived mapping configuration.
    processors:
        Optional dict of callables keyed by sensor name. Use this to patch in
        custom behaviour (e.g. if you add a new sensor type) without forking
        the base pipeline.
    """

    axes: Dict[str, float] = {}
    sensor_cfgs = mapping.get("sensors", {})

    default_processors: Dict[str, SensorProcessor] = {
        "mic": _process_generic_sensor,
        "tof": _process_generic_sensor,
        "light": _process_generic_sensor,
        "motion": _process_generic_sensor,
        "climate": _process_generic_sensor,
        "presence": _process_generic_sensor,
    }
    if processors:
        default_processors.update(processors)

    for sensor_name, sensor_cfg in sensor_cfgs.items():
        if not sensor_cfg.get("enabled", False):
            continue
        processor = default_processors.get(sensor_name, _process_generic_sensor)
        processor(sensor_name, frame, sensor_cfg, axes)

    return axes


def _process_generic_sensor(
    sensor_name: str, frame: Frame, sensor_cfg: Mapping[str, Any], axes: Dict[str, float]
) -> None:
    features = sensor_cfg.get("features", {})
    for feature_name, feature_cfg in features.items():
        feature_cfg = dict(feature_cfg)
        _apply_single_feature(sensor_name, feature_name, feature_cfg, frame, axes)
