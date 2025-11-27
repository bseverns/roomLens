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
import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
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
    from pythonosc import dispatcher, osc_server, udp_client
except Exception:  # pragma: no cover - allow OSC-less rehearsals
    dispatcher = None  # type: ignore[assignment]
    osc_server = None  # type: ignore[assignment]
    udp_client = None  # type: ignore[assignment]
try:
    import mido
except Exception:  # pragma: no cover - MIDI is optional
    mido = None  # type: ignore[assignment]

from roomlens import MappingPipeline, PatchManager, demo_frame


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


@dataclass
class PatchEvent:
    action: str
    value: Optional[str] = None
    source: str = "cli"


def emit_patch_confirmation(pipeline: MappingPipeline, patch: str) -> None:
    if not pipeline.has_osc_client:
        return
    try:
        pipeline._osc_client.send_message("/roomlens/patch", [patch, "loaded"])  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - UI feedback only
        print(f"# OSC confirmation failed: {exc}", file=sys.stderr)


def start_osc_listener(port: int, patch_queue: "queue.Queue[PatchEvent]") -> None:
    if dispatcher is None or osc_server is None:
        print("# python-osc not available; OSC patch listener disabled", file=sys.stderr)
        return
    disp = dispatcher.Dispatcher()

    def _handle_patch(address: str, *args: object) -> None:  # pragma: no cover - network/UI
        if not args:
            return
        target = str(args[0])
        patch_queue.put(PatchEvent(action="set", value=target, source="osc"))

    disp.map("/patch", _handle_patch)
    server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", port), disp)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"# Listening for OSC patch calls on 0.0.0.0:{port} (/patch <name>)", file=sys.stderr)


def start_midi_listener(
    *,
    port: Optional[str],
    cycle_note: int,
    select_cc: int,
    channel: int,
    patch_queue: "queue.Queue[PatchEvent]",
    preset_names: callable,
) -> None:
    if mido is None:
        print("# mido not available; MIDI patch binding disabled", file=sys.stderr)
        return
    input_name = port
    if not input_name:
        candidates = mido.get_input_names()
        if not candidates:
            print("# No MIDI inputs found; skipping MIDI patch binding", file=sys.stderr)
            return
        input_name = candidates[0]

    def _loop() -> None:  # pragma: no cover - hardware/UI
        try:
            with mido.open_input(input_name) as midi_in:
                print(f"# MIDI patch binding → {input_name}", file=sys.stderr)
                for msg in midi_in:
                    if channel >= 0 and getattr(msg, "channel", channel) != channel:
                        continue
                    if msg.type == "note_on" and msg.note == cycle_note:
                        patch_queue.put(PatchEvent(action="cycle", source="midi"))
                    elif msg.type == "control_change" and msg.control == select_cc:
                        names = preset_names()
                        if not names:
                            continue
                        idx = int(round((msg.value / 127) * (len(names) - 1))) if len(names) > 1 else 0
                        target = names[idx]
                        patch_queue.put(PatchEvent(action="set", value=target, source="midi"))
        except Exception as exc:
            print(f"# MIDI listener failed: {exc}", file=sys.stderr)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()


def setup_pipeline(mapping: Dict[str, object], args: argparse.Namespace) -> MappingPipeline:
    """Load the mapping file and prepare the shared pipeline instance."""

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
        "--presets-dir",
        default=str(Path(__file__).parents[2] / "config/presets"),
        help="Directory containing patch YAMLs",
    )
    ap.add_argument("--patch", default=None, help="Preset name from presets-dir")
    ap.add_argument(
        "--osc",
        type=int,
        default=0,
        help="OSC out port (0=disabled; pair with host/supercollider/RoomLens.scd on 57120)",
    )
    ap.add_argument(
        "--osc-in",
        type=int,
        default=0,
        help="OSC in port for /patch <name> hot-swaps (0=disabled)",
    )
    ap.add_argument("--demo", action="store_true", help="Ignore serial; generate frames")
    ap.add_argument("--dry-audio", action="store_true", help="Do not render sound; print mappings")
    ap.add_argument(
        "--snapshot-dir",
        default=str(Path(__file__).parents[2] / "config/snapshots"),
        help="Where to write timestamped mapping snapshots",
    )
    ap.add_argument(
        "--snapshot-history",
        type=int,
        default=4,
        help="How many snapshots to retain in the in-memory ring for toggling",
    )
    ap.add_argument(
        "--midi-input",
        default=None,
        help="Optional MIDI input port name for patch switching",
    )
    ap.add_argument(
        "--midi-cycle-note",
        type=int,
        default=60,
        help="Note number that cycles to the next preset (default: 60/Middle C)",
    )
    ap.add_argument(
        "--midi-select-cc",
        type=int,
        default=1,
        help="CC number that maps its value across available presets",
    )
    ap.add_argument(
        "--midi-channel",
        type=int,
        default=-1,
        help="Restrict MIDI listening to a channel (0-15) or -1 for omni",
    )
    ap.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="# %(levelname)s %(message)s",
    )

    patch_manager = PatchManager(
        base_mapping_path=Path(args.mapping),
        presets_dir=Path(args.presets_dir),
        snapshot_dir=Path(args.snapshot_dir),
        history_size=args.snapshot_history,
        logger=logging.getLogger("roomlens.patch"),
    )

    patch_queue: "queue.Queue[PatchEvent]" = queue.Queue()
    active_patch, mapping, _ = patch_manager.load_patch(args.patch)
    pipeline = setup_pipeline(mapping, args)
    emit_patch_confirmation(pipeline, active_patch)
    if args.osc_in:
        start_osc_listener(args.osc_in, patch_queue)
    start_midi_listener(
        port=args.midi_input,
        cycle_note=args.midi_cycle_note,
        select_cc=args.midi_select_cc,
        channel=args.midi_channel,
        patch_queue=patch_queue,
        preset_names=patch_manager.available_presets,
    )

    frames = frame_iterator(args)

    for i, frame in enumerate(frames, start=1):
        try:
            event = patch_queue.get_nowait()
        except queue.Empty:
            event = None

        if event:
            if event.action == "cycle":
                active_patch, mapping, conflicts = patch_manager.cycle()
            elif event.action == "set" and event.value:
                if event.value.lower() == "previous":
                    prev = patch_manager.previous()
                    if prev:
                        active_patch, mapping, conflicts = prev
                    else:
                        conflicts = []
                        print("# No previous patch in history", file=sys.stderr)
                        mapping = None
                else:
                    active_patch, mapping, conflicts = patch_manager.load_patch(
                        None if event.value == "default" else event.value
                    )
            else:
                conflicts = []
                mapping = None

            if mapping is not None:
                pipeline.update_mapping(mapping)
                emit_patch_confirmation(pipeline, active_patch)
                if conflicts:
                    print(
                        f"# Patch '{active_patch}' merged with overrides: {', '.join(conflicts)}",
                        file=sys.stderr,
                    )
                else:
                    print(f"# Patch → {active_patch} (source: {event.source})", file=sys.stderr)

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
                "# tip: edit config/mapping.default.yaml or drop a patch into config/presets",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
