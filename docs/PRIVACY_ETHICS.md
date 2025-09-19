
# PRIVACY & ETHICS

- **People > product**: The room is full of humans; treat them with care.
- **Data minimization**: Process in RAM. Saving requires explicit opt‑in from participants.
- **Transparency**: Plain‑language labels for what is sensed and how it affects sound.
- **Instructional fit**: These norms scaffold classroom use and public demos.

**Default behavior**
- No images; no biometrics; no unique identifiers.
- Sensors target *ambient* properties: sound pressure (RMS/SC), light level/flicker, distance, motion energy.
- Logs off by default. `tools/capture_logger.py` prompts before writing to disk.

**Opt‑in capture**
- If recording is desired, show a live “data flow” sketch: `Sensor → Detect (RAM) → Review [Save/Discard]`.
- Provide **Show me my data** and **Delete now** actions at end of session.
