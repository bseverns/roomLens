"""Preset and patch helpers for live mapping swaps.

This module keeps the patch UX in one place so hosts and notebooks can share
the same semantics:

* Presets live in ``config/presets`` and overlay the base
  ``config/mapping.default.yaml``.
* Merging is deep and opinionated: the patch wins, but we log every override so
  you can audit surprises mid-rehearsal.
* Snapshots always land on disk (timestamped) and can optionally be mirrored in
  a ring buffer for quick "previous patch" toggles.

Everything here is plain Python so a classroom can read it like a studio
notebook—minimal black boxes, lots of inline intent.
"""
from __future__ import annotations

import copy
import datetime as _dt
import logging
from collections import deque
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Tuple

import yaml

from .mapping import MappingDict, load_mapping

logger = logging.getLogger(__name__)


def deep_merge(
    base: MutableMapping[str, Any],
    patch: Mapping[str, Any],
    *,
    path: Tuple[str, ...] | None = None,
    conflicts: list[str] | None = None,
) -> MutableMapping[str, Any]:
    """Deep-merge ``patch`` into ``base`` with conflict tracking.

    * Dicts are merged recursively.
    * Scalars and lists are replaced wholesale, and any replacement is logged
      as a conflict so you know exactly which knobs the patch grabbed.
    * The merge is in-place for ``base`` and returned for convenience.
    """

    path = path or ()
    conflicts = conflicts if conflicts is not None else []

    for key, patch_val in patch.items():
        key_path = path + (str(key),)
        if key not in base:
            base[key] = copy.deepcopy(patch_val)
            continue

        base_val = base[key]
        if isinstance(base_val, MutableMapping) and isinstance(patch_val, Mapping):
            deep_merge(base_val, patch_val, path=key_path, conflicts=conflicts)
        else:
            if base_val != patch_val:
                conflicts.append("/".join(key_path))
            base[key] = copy.deepcopy(patch_val)

    return base


class PresetResolver:
    """Load and merge presets on top of the base mapping file."""

    def __init__(
        self,
        base_mapping_path: Path,
        presets_dir: Path,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_mapping_path = Path(base_mapping_path)
        self.presets_dir = Path(presets_dir)
        self.logger = logger or logging.getLogger(__name__)

    def available_presets(self) -> list[str]:
        """Return a sorted list of preset names (without extensions)."""

        if not self.presets_dir.exists():
            return []
        return sorted(p.stem for p in self.presets_dir.glob("*.yaml"))

    def _load_patch(self, name: str) -> MappingDict:
        patch_path = self.presets_dir / f"{name}.yaml"
        if not patch_path.exists():
            raise FileNotFoundError(f"Preset '{name}' not found at {patch_path}")
        with patch_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def resolve(self, patch_name: str | None) -> tuple[MappingDict, list[str]]:
        """Return the merged mapping and a list of conflicts."""

        base = load_mapping(self.base_mapping_path)
        conflicts: list[str] = []
        if not patch_name:
            return base, conflicts

        try:
            patch = self._load_patch(patch_name)
        except FileNotFoundError:
            self.logger.error("Preset '%s' not found; staying on base mapping", patch_name)
            return base, conflicts

        merged = deep_merge(base, patch, conflicts=conflicts)
        if conflicts:
            self.logger.info(
                "Patch '%s' overrode %d fields: %s",
                patch_name,
                len(conflicts),
                ", ".join(conflicts),
            )
        else:
            self.logger.info("Patch '%s' merged without conflicts", patch_name)

        return merged, conflicts


class SnapshotWriter:
    """Persist mapping snapshots with optional in-memory history."""

    def __init__(
        self,
        snapshot_dir: Path,
        *,
        history_size: int = 0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)
        self._history: deque[tuple[str, MappingDict]] | None = None
        if history_size > 0:
            self._history = deque(maxlen=history_size)

    def snapshot(self, name: str, mapping: MappingDict) -> Path:
        timestamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = name.replace("/", "-") if name else "default"
        path = self.snapshot_dir / f"{timestamp}_{safe_name}.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(mapping, fh, sort_keys=False)
        if self._history is not None:
            self._history.append((name or "default", copy.deepcopy(mapping)))
        self.logger.info("Snapshot saved: %s", path)
        return path

    def previous(self) -> tuple[str, MappingDict] | None:
        """Return the previous mapping from the ring buffer, if enabled."""

        if not self._history or len(self._history) < 2:
            return None
        # The most recent is at -1; we want the one before it for a toggle.
        return self._history[-2]


class PatchManager:
    """Coordinate preset resolution, snapshots, and cycling."""

    def __init__(
        self,
        base_mapping_path: Path,
        presets_dir: Path,
        *,
        snapshot_dir: Path,
        history_size: int = 0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.resolver = PresetResolver(base_mapping_path, presets_dir, logger=self.logger)
        self.snapshot_writer = SnapshotWriter(snapshot_dir, history_size=history_size, logger=self.logger)
        self.current_name: str = "default"

    def available_presets(self) -> list[str]:
        presets = self.resolver.available_presets()
        return ["default"] + presets

    def load_patch(self, patch_name: str | None) -> tuple[str, MappingDict, list[str]]:
        name = patch_name or "default"
        mapping, conflicts = self.resolver.resolve(patch_name)
        self.current_name = name
        self.snapshot_writer.snapshot(name, mapping)
        return name, mapping, conflicts

    def cycle(self, step: int = 1) -> tuple[str, MappingDict, list[str]]:
        presets = self.available_presets()
        if not presets:
            return self.load_patch(None)
        try:
            idx = presets.index(self.current_name)
        except ValueError:
            idx = 0
        next_idx = (idx + step) % len(presets)
        target = presets[next_idx]
        return self.load_patch(None if target == "default" else target)

    def previous(self) -> tuple[str, MappingDict, list[str]] | None:
        prev = self.snapshot_writer.previous()
        if not prev:
            return None
        name, mapping = prev
        conflicts: list[str] = []
        self.current_name = name
        self.snapshot_writer.snapshot(name, mapping)
        return name, mapping, conflicts

