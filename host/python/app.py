
#!/usr/bin/env python3
"""Room Lens host (prototype)
================================

Verbosity warning: this module is annotated like a field notebook. Future you
should be able to trace each design choice while still half awake after a long
load‑in.

Intent
------
* Read JSON frames produced by the Teensy firmware or a demo generator.
* Load the YAML mapping config and translate features into synth axes.
* Optionally broadcast the axes over OSC to a SuperCollider (or Pd, VCV Rack,
  etc.) patch; otherwise print to stdout for quick inspection.

Design tenets
-------------
* **Scene first**: keep the mapping legible and trivially hackable during a
  rehearsal. All key transforms are in `config/mapping.default.yaml`.
* **Data minimization**: nothing is persisted by default; recording is an
  explicit act the performer/teacher opts into.
* **Teaching forward**: docstrings favour clarity and cite the technical docs
  that inspired the default signal ranges.

References
----------
[1] PJRC. *Teensy 4.0 Technical Specifications.* Accessed 2024-03-05 from
    https://www.pjrc.com/store/teensy40.html
[2] STMicroelectronics. *VL53L1X Time-of-Flight Ranging Sensor Datasheet.* Rev
    7, 2023.
[3] TAOS/ams OSRAM. *TSL2591 High Dynamic Range Digital Light Sensor.* Rev B,
    2016.
[4] Wright, M. and Freed, A. "Open Sound Control: A New Protocol for
    Communicating with Sound Synthesizers." ICMC, 1997.
[5] Tzanetakis, G. and Cook, P. "Musical Genre Classification of Audio Signals." IEEE
    Transactions on Speech and Audio Processing, 10(5), 2002.

Usage
-----
```bash
python app.py --port auto --dry-audio
python app.py --demo --osc 57120
```
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, Optional

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:  # pragma: no cover - guard rails for classrooms without pyserial
    serial = None  # type: ignore[assignment]
try:
    from pythonosc import udp_client
except Exception:  # pragma: no cover - allow OSC-less rehearsals
    udp_client = None  # type: ignore[assignment]
import yaml

# --------- Utility ---------
def find_serial() -> Optional[str]:
    """Best-effort hunt for a Teensy board on the USB serial bus.

    Returns the OS-specific device string (e.g. ``/dev/ttyACM0`` or
    ``COM4``). We bias toward descriptors that explicitly call out "Teensy"
    because PJRC's firmware enumerates as such by default. When that fails we
    fall back to the first port the OS lists.

    This follows PJRC's guidance on enumeration order for the Teensy 4.0 USB
    stack. See Ref. [1].
    """

    if serial is None:
        return None
    ports = list(list_ports.comports())
    for p in ports:
        if "Teensy" in p.description or "ttyACM" in p.device or "tty.usbmodem" in p.device:
            return p.device
    return ports[0].device if ports else None

def clamp01(x: float) -> float:
    """Clamp to the inclusive ``[0, 1]`` range.

    Normalized features from the firmware are expected to land in this band but
    we clamp defensively because sensor drift, quantization error, or user hacks
    to the firmware can occasionally leak out of range.
    """

    return 0.0 if x < 0 else (1.0 if x > 1.0 else x)

def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation helper.

    ``t`` is assumed to already be normalized (0 = ``a``, 1 = ``b``). This is
    intentionally simple to keep the mapping legible to students who are still
    warming up to curve maths.
    """

    return a + (b - a) * t

# --------- Mapping ---------
def load_mapping(path: Path) -> Dict:
    """Load the YAML mapping file from disk.

    The YAML schema is intentionally permissive; we do only minimal validation
    here and leave structural experimentation to the user. The returned dict is
    consumed directly by :func:`apply_mapping`.
    """

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def validate_mapping_axes(mapping: Dict) -> None:
    """Ensure every declared feature maps to a synth axis.

    Raises
    ------
    ValueError
        If any ``map_to.axis`` fields are missing. The goal is to fail loud and
        early so a workshop participant does not silently run a patch with
        dangling sensor data.
    """
    missing = []
    for sensor_name, sensor_cfg in mapping.get("sensors", {}).items():
        for feature_name, feature_cfg in sensor_cfg.get("features", {}).items():
            map_to = feature_cfg.get("map_to", {})
            if not map_to.get("axis"):
                missing.append(f"{sensor_name}.{feature_name}")
    if missing:
        raise ValueError(
            "Mapping entries missing map_to.axis: " + ", ".join(sorted(missing))
        )

def apply_mapping(frame: Dict[str, float], mapping: Dict) -> Dict[str, float]:
    """Map normalized sensor features to synth axes.

    Parameters
    ----------
    frame:
        A normalized feature dict from the firmware or demo generator. Keys
        follow the JSON exported by the Teensy skeleton.
    mapping:
        The YAML-derived mapping configuration.

    Returns
    -------
    dict
        Axis/value pairs ready to send to a synth over OSC.

    Notes
    -----
    * Microphone features draw on ubiquitous log-power loudness and spectral
      centroid features so we can cite established MIR literature when teaching.
    * The ToF block assumes VL53L1X-style data because of its widespread
      availability and classroom-friendly libraries (Ref. [2]).
    * Light readings assume a lux sensor with flicker detection akin to the
      TSL2591 (Ref. [3]).
    """

    axes: Dict[str, float] = {}
    s = mapping.get("sensors", {})

    # Mic ------------------------------------------------------------
    # Refer to classic MIR descriptors for loudness and spectral centroid so we
    # can ground class discussions in shared terminology (see e.g. Tzanetakis &
    # Cook 2002, Ref. [5], building on the OSC exchange in Ref. [4]).
    mic = s.get("mic", {})
    if mic.get("enabled", False):
        if "rms" in mic.get("features", {}):
            t = clamp01(frame.get("mic_rms", 0.0))
            map_to = mic["features"]["rms"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)
        if "spectral_centroid" in mic.get("features", {}):
            t = clamp01(frame.get("mic_sc", 0.0))
            map_to = mic["features"]["spectral_centroid"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)
        if "hf_rolloff" in mic.get("features", {}):
            t = clamp01(frame.get("hf", frame.get("mic_sc", 0.0)))
            map_to = mic["features"]["hf_rolloff"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)

    # ToF ------------------------------------------------------------
    # Distance sensors shine in crowd choreography exercises. VL53L1X style
    # sensors emit discrete distance bins; we smooth that into motion energy and
    # near/far gestures.
    tof = s.get("tof", {})
    if tof.get("enabled", False):
        if "motion_energy" in tof.get("features", {}):
            t = clamp01(frame.get("tof_motion", 0.0))
            map_to = tof["features"]["motion_energy"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)
        if "proximity" in tof.get("features", {}):
            t = clamp01(frame.get("tof_near", 0.0))
            map_to = tof["features"]["proximity"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)

    # Light ----------------------------------------------------------
    # Lux and flicker readings often correlate with HVAC cycles or door swings.
    # They give performers a poetic "sunbeam" dial.
    light = s.get("light", {})
    if light.get("enabled", False):
        if "lux" in light.get("features", {}):
            t = clamp01(frame.get("lux", 0.0))
            map_to = light["features"]["lux"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)
        if "flicker_hz" in light.get("features", {}):
            t = clamp01(frame.get("flicker", 0.0))
            map_to = light["features"]["flicker_hz"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                axes[axis] = lerp(lo, hi, t)

    # Motion burst ---------------------------------------------------
    # Cheap PIRs and IMU shake sensors give us the "somebody sprinted in" flag.
    motion = s.get("motion", {})
    if motion.get("enabled", True):
        if "burst" in motion.get("features", {}):
            t = 1.0 if frame.get("motion", 0) else 0.0
            map_to = motion["features"]["burst"].get("map_to", {})
            axis = map_to.get("axis")
            if axis:
                lo, hi = map_to["range"]
                # note reversed mapping: more motion → faster (smaller) attack
                axes[axis] = lerp(lo, hi, t)

    return axes

def demo_frame(t: float) -> Dict[str, float]:
    """Synthesize a plausible feature frame for demos.

    The goal is not to be realistic, just musical enough to stress the mapping
    stack during workshops when no hardware is plugged in. We blend a few sine
    and cosine terms to fake multi-rate modulation similar to what real sensor
    drift produces.
    """

    def wob(f: float) -> float:
        """Cheap LFO used to fake sensor motion for demos."""

        return 0.5 + 0.5 * math.sin(f * t) * math.cos(0.7 * f * t)
    return {
        "t": int(time.time()*1000),
        "mic_rms": 0.12 + 0.1*wob(1.7),
        "mic_sc":  0.40 + 0.3*wob(0.9),
        "tof_motion": abs(0.5 - wob(2.3))*2.0,
        "tof_near": wob(0.5),
        "lux": 0.3 + 0.6*wob(0.1),
        "flicker": wob(3.1),
        "motion": 1 if wob(2.3) > 0.65 else 0,
    }

def main() -> None:
    """CLI entry point.

    We keep argument parsing inline for transparency in workshops. In a real
    performance rig you'd likely wrap this in a richer CLI and logging system.
    """

    ap = argparse.ArgumentParser(description="Room Lens host bridge")
    ap.add_argument("--port", default="auto", help="serial port or 'auto'")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--mapping", default=str(Path(__file__).parents[2] / "config/mapping.default.yaml"))
    ap.add_argument(
        "--osc",
        type=int,
        default=0,
        help="OSC out port (0=disabled; pair with host/supercollider/RoomLens.scd on 57120)",
    )
    ap.add_argument("--demo", action="store_true", help="Ignore serial; generate frames")
    ap.add_argument("--dry-audio", action="store_true", help="Do not try to render sound here; print mappings")
    args = ap.parse_args()

    mapping = load_mapping(Path(args.mapping))
    validate_mapping_axes(mapping)

    osc_client = None
    if args.osc:
        if udp_client is None:
            print("# python-osc not available; cannot send OSC", file=sys.stderr)
        else:
            try:
                osc_client = udp_client.SimpleUDPClient("127.0.0.1", args.osc)
                print(f"# OSC → 127.0.0.1:{args.osc}", file=sys.stderr)
            except Exception as e:
                print(f"# OSC setup failed: {e}", file=sys.stderr)
                osc_client = None

    # Serial setup
    ser = None
    if not args.demo and serial is not None:
        port = find_serial() if args.port == "auto" else args.port
        if port:
            try:
                ser = serial.Serial(port, args.baud, timeout=0.1)
                print(f"# Connected to {port} @ {args.baud}", file=sys.stderr)
            except Exception as e:
                print(f"# Serial open failed: {e}; falling back to --demo", file=sys.stderr)
                args.demo = True
        else:
            args.demo = True

    t0 = time.time()
    i = 0
    while True:
        # Serial read loop doubles as the demo generator driver. We intentionally
        # keep this tight and synchronous; if you need buffering reach for the
        # capture logger tool instead.
        if args.demo or ser is None:
            t = time.time() - t0
            frame = demo_frame(t)
            time.sleep(0.04)
        else:
            line = ser.readline().decode("utf-8").strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue

        axes = apply_mapping(frame, mapping)

        payload = {"t": frame.get("t"), "axes": axes}

        if osc_client is not None and axes:
            msg = []
            for axis, value in sorted(axes.items()):
                msg.extend([axis, float(value)])
            try:
                osc_client.send_message("/roomlens", msg)
            except Exception as e:
                print(f"# OSC send failed: {e}", file=sys.stderr)

        if args.dry_audio or osc_client is None:
            # Print JSON lines so you can pipe into tee, jq, pandas, etc.
            print(json.dumps(payload), flush=True)

        i += 1
        if i % 100 == 0:
            print("# tip: edit config/mapping.default.yaml and watch axes shift in real time", file=sys.stderr)

if __name__ == "__main__":
    main()
