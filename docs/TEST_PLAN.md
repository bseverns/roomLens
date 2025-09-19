
# TEST PLAN — First pass: “Room tone → gesture”

**Goal:** Capture a 2–3 minute trace in a quiet room; introduce a single human gesture; confirm mappings feel musical.

## Setup
- Hardware: mic + distance (ToF) + light. Optional: PIR or IMU.
- Host: `host/python/app.py` in `--dry-audio` mode (prints targets).
- Mapping: start with `config/mapping.default.yaml` as‑is.

## Procedure
1. **Baseline** (60s): room empty, HVAC steady if possible.
2. **Gesture** (30s): one person slowly approaches, then exits.
3. **Light shift** (30s): occlude/unocclude a lamp or window.
4. **Stillness** (30s): return to baseline.

## Success criteria
- Spectral & loudness features track room tone without jumping.
- Approach increases “density” or “brightness” smoothly.
- Light change modulates slow timbre axis (e.g., stereo width or reverb mix).
- No clipping; no runaway feedback in synth.

## Outputs
- Optional CSV capture via `tools/capture_logger.py` (opt‑in).
- Notes: what felt expressive? what was dull? record in `docs/notes/` (create it).
