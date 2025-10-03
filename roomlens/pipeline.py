"""Reusable processing pipeline mirroring the Python host workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from .mapping import (
    MappingDict,
    SensorProcessor,
    apply_mapping,
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
    _osc_client: Any = field(default=None, repr=False)

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
        payload: Dict[str, Any] = {
            "t": frame.get("t"),
            "axes": axes,
        }
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
