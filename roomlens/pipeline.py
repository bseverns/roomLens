"""Reusable processing pipeline mirroring the Python host workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from .mapping import (
    MappingDict,
    SensorProcessor,
    _resolve_feature_value,
    _resolve_transform,
    apply_mapping,
    clamp01,
    load_mapping,
    validate_mapping_axes,
)


@dataclass
class MappingPipeline:
    """Bridge normalized sensor frames into synth axes.

    The class keeps the same behaviour as ``host/python/app.py`` but wraps it in
    a reusable, testable object. Scripts across the repo can share one
    ``MappingPipeline`` instance and therefore agree on mapping semantics.
    """

    mapping: MappingDict
    processors: Optional[Mapping[str, SensorProcessor]] = None
    osc_address: str = "/roomlens"
    on_frame_issue: Optional[
        Callable[[Mapping[str, Any], list[Dict[str, Any]]], None]
    ] = None
    jitter_threshold: float = 0.35
    _osc_client: Any = field(default=None, repr=False)
    _last_feature_values: Dict[tuple[str, str], float] = field(
        default_factory=dict, repr=False
    )
    _last_frame_time: Optional[float] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        validate_mapping_axes(self.mapping)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        processors: Optional[Mapping[str, SensorProcessor]] = None,
        osc_address: str = "/roomlens",
    ) -> "MappingPipeline":
        """Load a mapping file and construct a pipeline."""

        mapping = load_mapping(path)
        return cls(mapping=mapping, processors=processors, osc_address=osc_address)

    # ------------------------------------------------------------------
    # OSC integration
    # ------------------------------------------------------------------
    def bind_osc_client(self, client: Any) -> None:
        """Attach a python-osc style client for convenience."""

        self._osc_client = client

    @property
    def has_osc_client(self) -> bool:
        """Return ``True`` if an OSC client has been bound."""

        return self._osc_client is not None

    def prepare_osc_message(self, payload: Mapping[str, Any]) -> Tuple[str, list[Any]]:
        """Return the OSC address and flat argument list for a payload."""

        axes = payload.get("axes", {}) or {}
        args: list[Any] = []
        for axis, value in sorted(axes.items()):
            args.extend([axis, float(value)])
        return self.osc_address, args

    def emit_osc(self, payload: Mapping[str, Any]) -> bool:
        """Send ``payload`` to the bound OSC client if present."""

        if self._osc_client is None:
            return False
        address, args = self.prepare_osc_message(payload)
        if not args:
            return False
        self._osc_client.send_message(address, args)
        return True

    # ------------------------------------------------------------------
    # Core mapping behaviour
    # ------------------------------------------------------------------
    def process_frame(self, frame: Mapping[str, Any]) -> Dict[str, Any]:
        """Translate a normalized frame into a timestamped axis payload."""

        axes = apply_mapping(frame, self.mapping, processors=self.processors)
        issues = self.inspect_frame(frame)
        payload: Dict[str, Any] = {
            "t": frame.get("t"),
            "axes": axes,
        }
        if issues:
            payload["issues"] = issues
            if self.on_frame_issue:
                self.on_frame_issue(frame, issues)
        return payload

    def iter_process(self, frames: Iterable[Mapping[str, Any]]) -> Iterable[Dict[str, Any]]:
        """Generator that yields processed payloads for each frame."""

        for frame in frames:
            yield self.process_frame(frame)

    def update_mapping(self, mapping: MutableMapping[str, Any]) -> None:
        """Swap in a new mapping dict at runtime."""

        validate_mapping_axes(mapping)
        self.mapping = mapping

    def reload_from_yaml(self, path: str | Path) -> None:
        """Reload the mapping file from disk."""

        self.update_mapping(load_mapping(path))

    # ------------------------------------------------------------------
    # Issue detection / diagnostics
    # ------------------------------------------------------------------
    def inspect_frame(self, frame: Mapping[str, Any]) -> list[Dict[str, Any]]:
        """Return a list of per-feature issues detected in ``frame``.

        The inspection watches for NaN/Inf payloads, values that get clamped
        during normalization, and jitter spikes compared to the previous frame.
        Each issue is emitted as a dict so CLI/GUI layers can render structured
        warnings without parsing log strings.
        """

        issues: list[Dict[str, Any]] = []
        sensor_cfgs = self.mapping.get("sensors", {})
        t_now = frame.get("t")
        previous_t = self._last_frame_time
        if isinstance(t_now, (int, float)):
            self._last_frame_time = float(t_now)

        for sensor_name, sensor_cfg in sensor_cfgs.items():
            if not sensor_cfg.get("enabled", False):
                continue
            for feature_name, feature_cfg in sensor_cfg.get("features", {}).items():
                raw_value = _resolve_feature_value(
                    sensor_name, feature_name, feature_cfg, frame
                )
                transform = _resolve_transform(feature_cfg)
                try:
                    transformed = transform(raw_value)
                except Exception as exc:  # pragma: no cover - defensive path
                    issues.append(
                        {
                            "sensor": sensor_name,
                            "feature": feature_name,
                            "type": "transform_error",
                            "detail": str(exc),
                        }
                    )
                    continue

                normalized = clamp01(transformed)

                if not math.isfinite(raw_value) or not math.isfinite(transformed):
                    issues.append(
                        {
                            "sensor": sensor_name,
                            "feature": feature_name,
                            "type": "nan",
                            "raw": raw_value,
                            "normalized": normalized,
                            "detail": "Non-finite payload (NaN/Inf)",
                        }
                    )
                if transformed != normalized:
                    issues.append(
                        {
                            "sensor": sensor_name,
                            "feature": feature_name,
                            "type": "clamped",
                            "raw": raw_value,
                            "normalized": normalized,
                            "detail": "Value exceeded [0,1] normalization window",
                        }
                    )

                key = (sensor_name, feature_name)
                previous_raw = self._last_feature_values.get(key)
                if (
                    previous_raw is not None
                    and math.isfinite(raw_value)
                    and math.isfinite(previous_raw)
                ):
                    delta = abs(raw_value - previous_raw)
                    if delta > self.jitter_threshold:
                        issues.append(
                            {
                                "sensor": sensor_name,
                                "feature": feature_name,
                                "type": "jitter",
                                "raw": raw_value,
                                "normalized": normalized,
                                "previous_raw": previous_raw,
                                "delta": delta,
                                "detail": f"Jumped by {delta:.2f} since last frame",
                                "dt_ms": (
                                    float(t_now) - float(previous_t)
                                    if t_now is not None and previous_t is not None
                                    else None
                                ),
                            }
                        )
                self._last_feature_values[key] = raw_value

        return issues
