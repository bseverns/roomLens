
#!/usr/bin/env python3
"""
Room Lens host (prototype)

Intent:
- Read JSON frames from Teensy (or generate demo frames).
- Load YAML mapping and compute timbre targets.
- Optionally send OSC to a synth (SuperCollider), or just print.

Design:
- Scene-first. Keep the mapping legible and hackable.
- Data minimization: by default, we do NOT save to disk.

Usage:
  python app.py --port auto --dry-audio
  python app.py --demo --osc 57120
"""
import argparse, json, sys, time, math
from pathlib import Path

try:
    import serial, serial.tools.list_ports as list_ports
except Exception:
    serial = None
import yaml

# --------- Utility ---------
def find_serial():
    if serial is None:
        return None
    ports = list(list_ports.comports())
    for p in ports:
        if "Teensy" in p.description or "ttyACM" in p.device or "tty.usbmodem" in p.device:
            return p.device
    return ports[0].device if ports else None

def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1.0 else x)

def lerp(a,b,t): return a + (b-a)*t

# --------- Mapping ---------
def load_mapping(path: Path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def validate_mapping_axes(mapping):
    """Ensure every feature declares a destination axis."""
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

def apply_mapping(frame, mapping):
    """ Map normalized features to timbre axes. """
    axes = {}
    s = mapping.get("sensors", {})

    # Mic
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

    # ToF
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

    # Light
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

    # Motion burst
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

def demo_frame(t):
    def wob(f): return 0.5 + 0.5*math.sin(f*t)*math.cos(0.7*f*t)
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

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="auto", help="serial port or 'auto'")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--mapping", default=str(Path(__file__).parents[2] / "config/mapping.default.yaml"))
    ap.add_argument("--osc", type=int, default=0, help="OSC out port (0=disabled)")
    ap.add_argument("--demo", action="store_true", help="Ignore serial; generate frames")
    ap.add_argument("--dry-audio", action="store_true", help="Do not try to render sound here; print mappings")
    args = ap.parse_args()

    mapping = load_mapping(Path(args.mapping))
    validate_mapping_axes(mapping)

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

        # Print the result (dry-audio demo path)
        print(json.dumps({"t": frame.get("t"), "axes": axes}), flush=True)

        i += 1
        if i % 100 == 0:
            print("# tip: edit config/mapping.default.yaml and watch axes shift in real time", file=sys.stderr)

if __name__ == "__main__":
    main()
