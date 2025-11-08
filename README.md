
# Room Lens
*A site‑sensing instrument that “plays” a room*

Room Lens listens to the latent choreography of a space—air, light, distance, presence—and translates those micro‑movements into sound. Think of it as a lens you point **at** a room: it refracts the scene into musical behavior. Like MOARkNOBS‑42 it is unapologetically tweakable, and like perceptual‑drift it wants to linger in the in‑between moments where nothing and everything is happening.

## Why this exists
- **Instrument**: improvise with architecture, HVAC, footsteps, sunbeams, and silence. Twist it, but let the room push back.
- **Research rig**: test mappings from multi‑sensor “scenes” to sound synthesis parameters; keep a log like a perceptual‑drift field journal.
- **Teaching tool**: give students a rigorous, hands‑on system for sensing → thinking → making. Annotate, question, annotate again.

> Design tenet: **scene first, synth second**. We earn our notes from the room.

---

## Repo layout
*Half lab notebook, half demo kit. Every folder wants you to scribble margin notes.*
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
│   ├── first-test/README.md         # “Room tone → gesture” protocol
│   └── vcv-rack/                    # OSC-driven VCV Rack scenes + README
│       ├── README.md                # Install list, teaching notes, mapping chart
│       ├── roomlens_scene_receiver.vcv
│       └── roomlens_texture_memory.vcv
├── tests/                           # Unit tests (stubs)
└── data/
    └── calibration/                 # Sensor offsets, mic calibration
```

---

## Quick start (prototype path)
Treat this like a fast jam session where the first rule is “document the jam.”

1) **Mark the room**: walk the space, describe it in your notebook, then open `config/mapping.default.yaml` and tune a few mappings for your space.
2) **Spin up the host** (no audio libs required at first):
```bash
cd host/python
python app.py --port auto --dry-audio
```
   Watch the terminal like a VU meter; scribble what you notice.
3) **Patch a synth** (optional but encouraged): boot `host/supercollider/RoomLens.scd` and run the python host with `--osc 57120` (the SuperCollider patch's default inbox) to fling axes over OSC: `python app.py --demo --osc 57120`. Hack parameters in real time; note what felt feral vs. fragile.
   - **VCV Rack path**: open `examples/vcv-rack/roomlens_scene_receiver.vcv` for the same OSC mappings used in the `vcv_patch` repo. Follow the in-patch Notes cards and log what each sensor lane does to the sound.
4) **First test**: follow `docs/TEST_PLAN.md` to capture “room tone → gesture.” Save any field recordings, even the messy ones.

> Next micro‑step: **Sketch/adjust the mapping table**. Start in the YAML; regenerate the pretty table with `python tools/gen_mapping_md.py`. Snapshot before/after in your notes like you would for a patchbay experiment on MOARkNOBS‑42.

---

## Tests (keep the rig honest)
Before you poke at the suite, make sure your Python environment knows how to read our mapping spells. Install the host deps:

```bash
pip install -r host/python/requirements.txt  # or at minimum: pip install pyyaml
```

Both test runners matter because contributors roll with different habits. We keep them in lockstep:

```bash
python -m unittest
```

```bash
pytest
```

The fixtures lean on `config/mapping.default.yaml`; if you scribble in that file, update the tests/fixtures so they vibe together.

---

## Architecture (minimal, swappable)
```
SENSORS → FEATURES → GESTURES → MAPPINGS → SYNTH
  (raw)     (RMS, SC)    (enter/exit)   (axes)     (SC/Pd/python)
```
- **Sensors**: mic, ToF/ultrasonic, PIR, IMU, light (lux/flicker), temp/RH, BLE presence. Swap or stack—treat each as another knob on that mythical 42‑bank console.
- **Features**: spectral centroid, roll‑off, loudness, motion energy, flicker Hz, deltas. Annotate what each means in the context of your room; drift with it.
- **Gestures**: *stillness*, *approach*, *crowd*, *pulse*, *draft*, *sun change*. Name your own gestures when the room suggests better poetry.
- **Mappings**: normalized features → timbre axes (pitch cluster, filter cutoff, grain density…). Version control your experiments; paste snippets into critiques.
- **Synth**: any engine that accepts OSC/MIDI. SuperCollider patch provided; Pd/prototyping path included. Bonus points for routing into MOARkNOBS‑style modular chaos.

### Shared processing pipeline
* The feature→axis glue now lives in [`roomlens/`](roomlens/README.md). Import it from any Python context (`from roomlens import MappingPipeline`) so the firmware notes, capture tools, and teaching notebooks all agree on the same maths.
* The CLI host (`host/python/app.py`) now wraps that package, meaning whatever changes you test in a notebook land in the performance rig instantly. Hack responsibly, annotate obsessively.

---

## Artifacts to (re)gather
- [ ] **Sensing matrix + scene→sound mapping** (see `docs/MAPPING_TABLE.md` & `config/mapping.default.yaml`). Print it. Draw arrows. Coffee stains welcome.
- [ ] **First test recording**: “room tone → gesture” (see `examples/first-test/`). Write a short critique of the room’s performance.
- [ ] **Teaching reflections**: log what students or collaborators noticed, what confused them, what they hacked.

### Notes on style & lineage
- Verbose intent comments and assumption tracing are first‑class (see `docs/ASSUMPTION_LEDGER.md`). Write like you’re leaving clues for the next art‑engineer.
- Data minimization by default: ephemeral RAM processing; explicit opt‑in to save. Ethics is a knob you always keep within reach.
- Friendly to classroom & performance contexts; portable between Teensy host and laptop host. Field test it in a rehearsal, then debrief like a perceptual‑drift diary.
- References held in the background: *MOARkNOBS‑42* for bravado and tweakability, *perceptual‑drift* for patience and listening discipline.

Have fun. Be gentle to rooms.
