
# Room Lens
*A site‑sensing instrument that “plays” a room.*

Room Lens listens to the latent choreography of a space—air, light, distance, presence—and translates those micro‑movements into sound. Think of it as a lens you point **at** a room: it refracts the scene into musical behavior.

## Why this exists
- As an instrument: to improvise with architecture, HVAC, footsteps, sunbeams, and silence.
- As research: to test mappings from multi‑sensor “scenes” to sound synthesis parameters.
- As pedagogy: to give students a rigorous, hands‑on system for sensing → thinking → making.

> Design tenet: **scene first, synth second**. We earn our notes from the room.

---

## Repo layout
```
room-lens/
├── README.md
├── LICENSE
├── .gitignore
├── config/
│   ├── mapping.default.yaml         # Sensor→timbre axes (edit me first)
│   └── profiles/                    # Optional site-specific overrides
├── docs/
│   ├── CONCEPT.md                   # Intent, research frame, influences
│   ├── MAPPING_TABLE.md             # Human-readable mapping table
│   ├── ASSUMPTION_LEDGER.md         # What we're assuming & why
│   ├── PRIVACY_ETHICS.md            # Data minimization & classroom norms
│   └── TEST_PLAN.md                 # First test: room tone → gesture
├── firmware/
│   └── roomlens-teensy/             # PlatformIO Teensy 4.0 firmware
│       ├── platformio.ini
│       └── src/main.cpp
├── hardware/                        # KiCad, wiring, BOM (placeholders)
├── host/
│   ├── python/                      # Minimal host for prototyping
│   │   ├── app.py
│   │   └── requirements.txt
│   └── supercollider/
│       └── RoomLens.scd             # OSC receiver & synth graph
├── patches/
│   └── puredata/roomlens.pd         # Placeholder Pd patch
├── tools/
│   ├── capture_logger.py            # Logs sensor frames → CSV/Parquet
│   └── gen_mapping_md.py            # YAML → docs/MAPPING_TABLE.md
├── examples/
│   └── first-test/README.md         # “Room tone → gesture” protocol
├── tests/                           # Unit tests (stubs)
└── data/
    └── calibration/                 # Sensor offsets, mic calibration
```

---

## Quick start (prototype path)
1) **Edit mapping**: open `config/mapping.default.yaml` and tune a few mappings for your space.  
2) **Run host** (no audio libs required at first):
```bash
cd host/python
python app.py --port auto --dry-audio
```
You’ll see live sensor frames and the mapped timbre targets printed.  
3) **(Optional) SuperCollider**: boot `host/supercollider/RoomLens.scd` to hear basic synthesis over OSC.  
4) **First test**: follow `docs/TEST_PLAN.md` to capture “room tone → gesture.”

> Next micro‑step: **Sketch/adjust the mapping table**. Start in the YAML; regenerate the pretty table with `python tools/gen_mapping_md.py`.

---

## Architecture (minimal, swappable)
```
SENSORS → FEATURES → GESTURES → MAPPINGS → SYNTH
  (raw)     (RMS, SC)    (enter/exit)   (axes)     (SC/Pd/python)
```
- **Sensors**: mic, ToF/ultrasonic, PIR, IMU, light (lux/flicker), temp/RH, BLE presence.  
- **Features**: spectral centroid, roll‑off, loudness, motion energy, flicker Hz, deltas.  
- **Gestures**: *stillness*, *approach*, *crowd*, *pulse*, *draft*, *sun change*.  
- **Mappings**: normalized features → timbre axes (pitch cluster, filter cutoff, grain density…).  
- **Synth**: any engine that accepts OSC/MIDI. SuperCollider patch provided; Pd/prototyping path included.

---

## Artifacts to (re)gather
- [ ] **Sensing matrix + scene→sound mapping** (see `docs/MAPPING_TABLE.md` & `config/mapping.default.yaml`)
- [ ] **First test recording**: “room tone → gesture” (see `examples/first-test/`)

### Notes on style & lineage
- Verbose intent comments and assumption tracing are first‑class (see `docs/ASSUMPTION_LEDGER.md`).  
- Data minimization by default: ephemeral RAM processing; explicit opt‑in to save.  
- Friendly to classroom & performance contexts; portable between Teensy host and laptop host.

Have fun. Be gentle to rooms.
