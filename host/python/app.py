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

Patch inbox cheat-sheet
-----------------------
* **VCV Rack**: ``examples/vcv-rack/*roomlens*.vcv`` already listens for OSC
  on ``127.0.0.1:57120``.
* **SuperCollider**: ``host/supercollider/RoomLens.scd`` opens UDP ``57120``
  and routes ``/roomlens`` axes to LagControls.
* **Pd**: ``patches/puredata/roomlens.pd`` expects the same bundle and wires
  receivers you can tap inside other Pd patches.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

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

try:  # Optional: heartbeat LED when running on SBCs
    from gpiozero import LED
except Exception:  # pragma: no cover - GPIO-less dev hosts
    LED = None  # type: ignore[assignment]

from roomlens import MappingPipeline, demo_frame, load_mapping
from roomlens_output import DummyOutput, OutputFanout, parse_output_spec


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


def setup_pipeline(args: argparse.Namespace) -> Tuple[Dict[str, object], MappingPipeline]:
    """Load the mapping file and prepare the shared pipeline instance."""

    mapping = load_mapping(Path(args.mapping))
    pipeline = MappingPipeline(mapping)
    return mapping, pipeline

    def issue_sink(frame: Dict[str, float], issues: list[Dict[str, object]]) -> None:
        for issue in issues:
            sensor = issue.get("sensor")
            feature = issue.get("feature")
            print(
                f"# issue {sensor}.{feature}: {issue.get('type')} — {issue.get('detail')}",
                file=sys.stderr,
            )

    pipeline = MappingPipeline(mapping, on_frame_issue=issue_sink)
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


def setup_outputs(mapping_cfg: Dict[str, object], args: argparse.Namespace) -> OutputFanout:
    """Instantiate all requested outputs and prime their ping logs."""

    specs = list(mapping_cfg.get("outputs", []) or [])
    if args.osc:
        specs.append({"osc": args.osc})

    outputs = []
    for spec in specs:
        try:
            outputs.append(parse_output_spec(spec))
        except Exception as exc:
            print(f"# Skipping output {spec!r}: {exc}", file=sys.stderr)

    if not outputs:
        outputs = [DummyOutput(stream=sys.stdout)]

    fanout = OutputFanout(outputs)
    fanout.ping_targets()
    return fanout

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
    ap.add_argument(
        "--led-pin",
        type=int,
        default=-1,
        help="Optional GPIO LED to blink with the heartbeat",
    )
    args = ap.parse_args()

    mapping_cfg, pipeline = setup_pipeline(args)
    outputs = setup_outputs(mapping_cfg, args)
    frames = frame_iterator(args)

    heartbeat_interval_s = 1.0
    heartbeat_drift_s = 0.35

    @dataclass
    class Heartbeat:
        last: float
        led: Optional[object]

        def tick(self) -> None:
            now = time.time()
            delta = now - self.last
            if delta < heartbeat_interval_s:
                return
            self.last = now
            drift = delta - heartbeat_interval_s
            if pipeline.has_osc_client:
                try:
                    pipeline._osc_client.send_message("/heartbeat", [now, drift])
                except Exception as exc:  # pragma: no cover - UI feedback only
                    print(f"# heartbeat OSC send failed: {exc}", file=sys.stderr)
            if self.led:
                try:
                    self.led.toggle()
                except Exception:
                    pass
            if abs(drift) > heartbeat_drift_s:
                print(
                    f"# heartbeat cadence drifted by {drift:+.3f}s", file=sys.stderr
                )

    led = None
    if args.led_pin >= 0 and LED is not None:
        try:
            led = LED(args.led_pin)
            print(f"# Heartbeat LED on GPIO {args.led_pin}", file=sys.stderr)
        except Exception:
            print("# LED setup failed; continuing without blink", file=sys.stderr)

    heartbeat = Heartbeat(last=time.time(), led=led)

    for i, frame in enumerate(frames, start=1):
        heartbeat.tick()
        payload = pipeline.process_frame(frame)

        sent = outputs.broadcast(payload)

        if args.dry_audio or not sent:
            print(json.dumps(payload), flush=True)

        if i % 100 == 0:
            print(
                "# tip: edit config/mapping.default.yaml and watch axes shift in real time",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
