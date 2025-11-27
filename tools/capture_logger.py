#!/usr/bin/env python3
"""
Capture Logger (opt-in)
======================

Pipe JSON frames from stdin, USB serial, or OSC into a CSV/NDJSON sink.
The goal is to keep field recordings honest: require a "YES" before writing,
mirror the mapping maths so you can log normalized axes alongside the raw
sensor payload, and stay dependency-light for classroom laptops.

Usage examples
--------------
- Log stdin (NDJSON) straight to CSV, no mapping:
    python tools/capture_logger.py --file data/capture.csv < stream.ndjson

- Tap the Teensy over serial, normalize through the mapping, and include
  axis_* columns:
    python tools/capture_logger.py --serial-port /dev/ttyACM0 \
        --file data/my_room.csv --mapping config/mapping.default.yaml

- Listen for OSC (``/roomlens``) payloads and keep a note of any per-frame
  issues the pipeline surfaced:
    python tools/capture_logger.py --osc-port 9000 --file data/osc_log.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, Optional

try:  # Optional: only needed when mapping/plotting OSC payloads
    from pythonosc import dispatcher, osc_server
except Exception:  # pragma: no cover - labs without python-osc
    dispatcher = None  # type: ignore[assignment]
    osc_server = None  # type: ignore[assignment]

try:  # Optional: hardware capture
    import serial
except Exception:  # pragma: no cover - allow laptop-only workflows
    serial = None  # type: ignore[assignment]

try:
    from roomlens import MappingPipeline
except Exception:  # pragma: no cover - keep logging usable without imports
    MappingPipeline = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Stream helpers
# ---------------------------------------------------------------------------
def iter_json_lines(stdin: Iterable[str]) -> Iterator[Dict[str, object]]:
    """Yield JSON objects from newline-delimited *stdin* style streams."""

    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(frame, Mapping):
            yield dict(frame)


def iter_serial_json(port: str, baud: int) -> Iterator[Dict[str, object]]:
    """Yield JSON frames from a serial port."""

    if serial is None:
        raise RuntimeError("pyserial not installed; cannot open serial streams")
    ser = serial.Serial(port, baud, timeout=0.1)
    print(f"# Connected to {port} @ {baud}", file=sys.stderr)
    try:
        for raw in iter(ser.readline, b""):
            try:
                line = raw.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, Mapping):
                yield dict(obj)
    finally:
        ser.close()


def iter_osc_payloads(listen_port: int, address: str) -> Iterator[Dict[str, object]]:
    """Yield OSC payloads (``address``) as dicts of axes."""

    if dispatcher is None or osc_server is None:
        raise RuntimeError("python-osc not installed; cannot listen for OSC")

    q: queue.Queue[Dict[str, object]] = queue.Queue()
    disp = dispatcher.Dispatcher()

    def _handler(addr: str, *args: object) -> None:
        if addr != address:
            return
        axes: Dict[str, float] = {}
        for i in range(0, len(args), 2):
            try:
                axes[str(args[i])] = float(args[i + 1])
            except Exception:
                continue
        q.put({"t": time.time(), "axes": axes})

    disp.map(address, _handler)
    server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", listen_port), disp)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"# Listening for OSC on {listen_port} ({address})", file=sys.stderr)

    try:
        while True:
            yield q.get()
    finally:  # pragma: no cover - manual teardown only
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Capture routines
# ---------------------------------------------------------------------------
def flatten_payload(frame: Dict[str, object], pipeline: Optional[MappingPipeline]) -> Dict[str, object]:
    """Merge raw frame + normalized axes into a flat dict ready for CSV."""

    merged: Dict[str, object] = dict(frame)
    if pipeline is not None:
        payload = pipeline.process_frame(frame)
        axes = payload.get("axes", {}) or {}
        for axis, value in axes.items():
            merged[f"axis_{axis}"] = value
        if payload.get("issues"):
            merged["issues_json"] = json.dumps(payload["issues"])
    elif "axes" in merged and isinstance(merged["axes"], Mapping):
        for axis, value in merged["axes"].items():
            merged[f"axis_{axis}"] = value
    return merged


def capture_stream(
    frames: Iterable[Dict[str, object]],
    out_path: Path,
    confirm_callback,
    pipeline: Optional[MappingPipeline] = None,
) -> bool:
    """Capture frames from *frames* and persist them to *out_path* as CSV."""

    if not confirm_callback(out_path):
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = None
    with out_path.open("w", newline="") as f:
        writer: Optional[csv.DictWriter] = None
        for frame in frames:
            if not isinstance(frame, Mapping):
                try:
                    frame = json.loads(frame) if isinstance(frame, str) else frame
                except Exception:
                    continue
            if not isinstance(frame, Mapping):
                continue
            row = flatten_payload(dict(frame), pipeline)
            if fieldnames is None:
                fieldnames = list(row.keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            if writer is None:
                break
            writer.writerow(row)
            f.flush()

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Capture JSON/OSC frames to CSV")
    ap.add_argument("--file", required=True, help="CSV destination (will be created)")
    ap.add_argument("--mapping", help="Optional mapping file to emit axis_* columns")
    ap.add_argument("--serial-port", help="Read frames from serial instead of stdin")
    ap.add_argument("--serial-baud", type=int, default=115200)
    ap.add_argument("--osc-port", type=int, default=0, help="Listen for OSC frames")
    ap.add_argument("--osc-address", default="/roomlens", help="OSC address to capture")
    ap.add_argument("--no-confirm", action="store_true", help="Skip interactive consent")
    return ap


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(list(argv) if argv is not None else None)

    out = Path(args.file)

    def confirm_callback(path: Path) -> bool:
        if args.no_confirm:
            return True
        print("This tool saves sensor frames to disk.")
        ans = input(f"Save to {path}? Type YES to proceed: ").strip()
        if ans != "YES":
            print("Aborting without saving.")
            return False
        return True

    pipeline: Optional[MappingPipeline] = None
    if args.mapping:
        if MappingPipeline is None:
            ap.error("roomlens package not importable; cannot apply mapping")
        pipeline = MappingPipeline.from_yaml(Path(args.mapping))  # type: ignore[assignment]

    if args.serial_port:
        frames = iter_serial_json(args.serial_port, args.serial_baud)
    elif args.osc_port:
        frames = iter_osc_payloads(args.osc_port, args.osc_address)
    else:
        frames = iter_json_lines(sys.stdin)

    capture_stream(frames, out, confirm_callback, pipeline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
