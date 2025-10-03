#!/usr/bin/env python3
"""Room Lens host (prototype)
================================

Same mission, clearer seams. This version delegates the feature→axis plumbing
into the :mod:`roomlens` package so any script in the repo can reuse the exact
pipeline. Treat this file as the CLI wrapper around that shared core.

Design tenets
-------------
* **Scene first**: the mapping stays in ``config/mapping.default.yaml`` so a
  rehearsal can tweak it live.
* **Data minimization**: nothing is persisted unless you intentionally pipe
  the JSON elsewhere.
* **Teaching forward**: docstrings and inline notes reference the same sources
  cited in the notebooks and docs.

References
----------
[1] PJRC. *Teensy 4.0 Technical Specifications.* https://www.pjrc.com/store/teensy40.html
[2] STMicroelectronics. *VL53L1X Time-of-Flight Ranging Sensor Datasheet.* Rev 7, 2023.
[3] TAOS/ams OSRAM. *TSL2591 High Dynamic Range Digital Light Sensor.* Rev B, 2016.
[4] Wright, M. & Freed, A. "Open Sound Control: A New Protocol for Communicating with Sound
    Synthesizers." ICMC, 1997.
[5] Tzanetakis, G. & Cook, P. "Musical Genre Classification of Audio Signals." IEEE Transactions
    on Speech and Audio Processing, 10(5), 2002.

Usage
-----
.. code-block:: bash

   python app.py --port auto --dry-audio
   python app.py --demo --osc 57120
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, Optional

# Make the repo root importable so ``roomlens`` is available when running
# ``python host/python/app.py`` straight from a clone.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:  # pragma: no cover - guard rails for classrooms without pyserial
    serial = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]
try:
    from pythonosc import udp_client
except Exception:  # pragma: no cover - allow OSC-less rehearsals
    udp_client = None  # type: ignore[assignment]

from roomlens import MappingPipeline, demo_frame, load_mapping


# --------- Utility ---------
def find_serial() -> Optional[str]:
    """Best-effort hunt for a Teensy board on the USB serial bus."""

    if serial is None or list_ports is None:
        return None
    ports = list(list_ports.comports())
    for p in ports:
        if "Teensy" in p.description or "ttyACM" in p.device or "tty.usbmodem" in p.device:
            return p.device
    return ports[0].device if ports else None


def serial_frames(port: str, baud: int) -> Iterator[Dict[str, float]]:
    """Yield JSON frames from a serial connection."""

    if serial is None:
        raise RuntimeError("pyserial not available; cannot read hardware")
    ser = serial.Serial(port, baud, timeout=0.1)
    print(f"# Connected to {port} @ {baud}", file=sys.stderr)
    try:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    finally:
        ser.close()


def demo_frames() -> Iterator[Dict[str, float]]:
    """Synthesize frames indefinitely using :func:`roomlens.demo.demo_frame`."""

    t0 = time.time()
    while True:
        t = time.time() - t0
        yield demo_frame(t)
        time.sleep(0.04)


def setup_pipeline(args: argparse.Namespace) -> MappingPipeline:
    """Load the mapping file and prepare the shared pipeline instance."""

    mapping = load_mapping(Path(args.mapping))
    pipeline = MappingPipeline(mapping)
    if args.osc:
        if udp_client is None:
            print("# python-osc not available; cannot send OSC", file=sys.stderr)
        else:
            try:
                client = udp_client.SimpleUDPClient("127.0.0.1", args.osc)
                pipeline.bind_osc_client(client)
                print(f"# OSC → 127.0.0.1:{args.osc}", file=sys.stderr)
            except Exception as exc:  # pragma: no cover - UI feedback only
                print(f"# OSC setup failed: {exc}", file=sys.stderr)
    return pipeline


def frame_iterator(args: argparse.Namespace) -> Iterator[Dict[str, float]]:
    """Select the appropriate frame source based on CLI flags."""

    if args.demo or serial is None:
        return demo_frames()

    port = find_serial() if args.port == "auto" else args.port
    if not port:
        print("# No serial device found; falling back to --demo", file=sys.stderr)
        return demo_frames()

    try:
        return serial_frames(port, args.baud)
    except Exception as exc:
        print(f"# Serial open failed ({exc}); falling back to --demo", file=sys.stderr)
        return demo_frames()


def main() -> None:
    """CLI entry point."""

    ap = argparse.ArgumentParser(description="Room Lens host bridge")
    ap.add_argument("--port", default="auto", help="serial port or 'auto'")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument(
        "--mapping",
        default=str(Path(__file__).parents[2] / "config/mapping.default.yaml"),
    )
    ap.add_argument(
        "--osc",
        type=int,
        default=0,
        help="OSC out port (0=disabled; pair with host/supercollider/RoomLens.scd on 57120)",
    )
    ap.add_argument("--demo", action="store_true", help="Ignore serial; generate frames")
    ap.add_argument("--dry-audio", action="store_true", help="Do not render sound; print mappings")
    args = ap.parse_args()

    pipeline = setup_pipeline(args)
    frames = frame_iterator(args)

    for i, frame in enumerate(frames, start=1):
        payload = pipeline.process_frame(frame)

        sent = False
        if pipeline.has_osc_client:
            try:
                sent = pipeline.emit_osc(payload)
            except Exception as exc:  # pragma: no cover - UI feedback only
                sent = False
                print(f"# OSC send failed: {exc}", file=sys.stderr)

        if args.dry_audio or not sent:
            print(json.dumps(payload), flush=True)

        if i % 100 == 0:
            print(
                "# tip: edit config/mapping.default.yaml and watch axes shift in real time",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
