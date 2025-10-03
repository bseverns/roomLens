# MAPPING TABLE (human‑readable)
> Source features are normalized to 0–1. Curves are linear unless noted.

| Sensor | Feature | Transform | Timbre Axis | Target Range | Notes |
|---|---|---|---|---|---|
| Mic | RMS loudness | log10, clamp | Grain density | 0.05 → 0.45 | Quiet room = sparse grains |
| Mic | Spectral centroid | z-norm per site | Filter cutoff | 400 → 8000 Hz | Site-specific normalization |
| Mic | HF content (roll-off) | softclip | Distortion drive | 0.0 → 0.6 | Adds grit when room is bright |
| ToF distance | Δ distance/s | abs, smooth(200ms) | FM index | 0.1 → 2.0 | Motion energy = harmonic bite |
| ToF distance | Proximity (near) | inv exp | Pitch cluster width | ±0 → ±700 cents | Near = wider cluster |
| Light | Lux level | normalize per site | Reverb mix | 0.05 → 0.35 | Brighter room = more space |
| Light | Flicker Hz | band-pass | Delay time | 90 → 350 ms | AC flicker drives echoes |
| PIR/IMU | Motion flag | debounce | Envelope attack | 5 → 80 ms | More motion = snappier |
| Temp/RH | Δ over 5 min | scale | LFO rate | 0.05 → 0.4 Hz | Slow climate = slow drift |
| Presence (BLE) | Count | cap @ 10 | Stereo width | 0.1 → 0.9 | More bodies = wider image |
