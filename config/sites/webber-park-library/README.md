# Room Lens site pack: Webber Park Library (no ToF)

This folder is an **add-only “translation”** for a library deployment. It does **not** modify
the Room Lens canon; it provides venue-specific presets and a repeatable calibration ritual.

## Assumptions
- **No ToF sensor**.
- Optional sensors:
  - **Webcam motion via Processing** `examples/processing/serial_webcam_bridge` (recommended)
  - **Mic** (recommended)
  - **Lux** (optional)
  - **PIR** (optional; only used in kids mode)
- The webcam bridge feeds `cam_motion` into the serial JSON stream (Pro Mini firmware supports this).

## Install (host)
From the Room Lens repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r host/python/requirements.txt
```

## Quickstart: run + pick a preset

### 1) Start webcam bridge (recommended)
Open in Processing:
- `examples/processing/serial_webcam_bridge/SerialWebcamBridge.pde`

Tune:
- Aim for **idle** `cam_motion ≈ 0.02–0.05` when nobody is at the portal/table.
- A deliberate player should peak ~`0.3–0.7`.

### 2) Start Room Lens host

**Transit-friendly placement (hard gate):**
```bash
python3 host/python/app.py --port auto \
  --presets-dir config/sites/webber-park-library/presets \
  --patch library_transit_noToF
```

**Kids stacks / discovery corner (more immediate):**
```bash
python3 host/python/app.py --port auto \
  --presets-dir config/sites/webber-park-library/presets \
  --patch library_kids_noToF
```

**Quiet corner / “breathing” mode:**
```bash
python3 host/python/app.py --port auto \
  --presets-dir config/sites/webber-park-library/presets \
  --patch library_idle_noToF
```

## Switching presets (two options)

### Option A: simplest (restart)
Stop the host (`Ctrl+C`) and re-run with a different `--patch`.

### Option B: hot-swap over OSC
Run the host with an OSC-in port:

```bash
python3 host/python/app.py --port auto \
  --presets-dir config/sites/webber-park-library/presets \
  --patch library_transit_noToF \
  --osc-in 9001
```

Then send a patch change from the same machine:

```bash
python3 -c "from pythonosc.udp_client import SimpleUDPClient as C; C('127.0.0.1',9001).send_message('/patch','library_kids_noToF')"
```

(Replace patch name as needed.)

## Calibration ritual (repeatable, quick)
1. **Frame camera** on the portal/table zone (avoid windows behind).
2. Set webcam bridge `smoothing` higher if walk-bys trigger.
3. Capture 3 quick recordings (optional but recommended):
   - `captures/still.ndjson` (30–60s, nobody at portal)
   - `captures/transit_2min.ndjson` (2 min normal traffic)
   - `captures/kids_2min.ndjson` (2 min real interaction)

If needed, tune presets:
- Too trigger-happy in transit → raise `softclip(threshold=...)` (e.g. 0.86 → 0.90) + increase smoothing.
- Too sleepy in kids mode → lower thresholds slightly (0.68 → 0.62).
- Too chaotic → reduce max of `pitch_cluster_width_cents`, `distortion_drive`, or `fm_index`.

## Placement guidance
Best results come from a **portal station**:
- A small table/cart with a taped “play zone”.
- Webcam aimed down at hands/books in that zone.
- Screen shows abstraction (not camera feed), to keep privacy comfortable.

## Files
- `presets/` contains:
  - `library_idle_noToF.yaml`
  - `library_transit_noToF.yaml`
  - `library_kids_noToF.yaml`
