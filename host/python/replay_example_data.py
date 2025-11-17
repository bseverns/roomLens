#!/usr/bin/env python3
"""Replay recorded sensor frames through the Room Lens mapping pipeline.

This script is the "no hardware" rehearsal path referenced in
``docs/ROOMLENS_OVERVIEW.md``. It reuses the :class:`roomlens.MappingPipeline`
so whatever mapping tweaks you make in ``config/mapping.default.yaml`` (or a
custom profile) immediately reflect in the replay stream.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

# Make ``roomlens`` importable when running from repo root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roomlens import MappingPipeline  # noqa: E402  (repo-local import)


def load_recording(path: Path) -> List[Dict[str, float]]:
    """Return a list of JSON frames from ``path`` (newline-delimited JSON)."""

    frames: List[Dict[str, float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - user feedback
                raise ValueError(f"Line {idx} is not valid JSON: {exc}") from exc
            if not isinstance(frame, dict):
                raise ValueError(f"Line {idx} must decode to an object, got {type(frame)!r}")
            frames.append(frame)
    if not frames:
        raise ValueError(f"Recording {path} did not contain any frames")
    return frames


def iter_frames(frames: List[Dict[str, float]], loop: bool) -> Iterator[Dict[str, float]]:
    """Yield ``frames`` once or forever depending on ``loop``."""

    while True:
        for frame in frames:
            yield frame
        if not loop:
            break


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay captured Room Lens frames without the hardware rig",
    )
    parser.add_argument(
        "--file",
        default=str(ROOT / "data/demo_walkthrough.ndjson"),
        help="newline-delimited JSON recording to replay",
    )
    parser.add_argument(
        "--mapping",
        default=str(ROOT / "config/mapping.default.yaml"),
        help="mapping file to apply during replay",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="seconds to wait between frames (set >0 to mimic live pacing)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="loop once the file ends so you can rehearse indefinitely",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="stop after this many frames (0 = entire replay)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    recording_path = Path(args.file)
    if not recording_path.exists():
        parser.error(f"Recording not found: {recording_path}")

    try:
        frames = load_recording(recording_path)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    pipeline = MappingPipeline.from_yaml(Path(args.mapping))

    emitted = 0
    for frame in iter_frames(frames, args.loop):
        payload = pipeline.process_frame(frame)
        print(json.dumps(payload), flush=True)
        emitted += 1
        if args.max_frames and emitted >= args.max_frames:
            break
        if args.sleep > 0:
            time.sleep(args.sleep)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
