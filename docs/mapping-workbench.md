# Mapping workbench (browser + OSC)

This notebook-style guide walks through the new FastAPI control surface that
ships with `host/python/app.py`. The vibe is half studio notebook, half
teaching crib sheet: keep it open during rehearsals and save the diff trail when
something magical happens.

## Why this exists
- To expose the live mapping dict that the synth actually listens to.
- To give workshops a panic/undo button when experiments go sideways.
- To send OSC test pings that respect whatever tweaks you just made.
- To save deltas back to YAML so the performance history is a paper trail, not a
  game of telephone.

## Boot it up
```bash
# optional: install FastAPI/uvicorn extras if you don't already have them
pip install -r host/python/requirements.txt fastapi uvicorn

# run the host with the inspector on port 9000
python host/python/app.py --demo --osc 57120 --api-port 9000
```
Visit [http://localhost:9000](http://localhost:9000) and you get:
- cards for each `sensor → feature → axis` route
- sliders/text inputs for `min/max/expo/offset`
- a panic/undo button
- a live log and a diff preview against the YAML on disk
- a **Save to YAML** button that writes to `config/mapping.default.yaml` (or a
  path you pass in the prompt)

## Patch flow
1. Move a slider or type a new number for an axis.
2. Hit **Apply**; the app updates every feature mapped to that axis, updates the
   live `MappingPipeline`, and emits an OSC ping for the axis so your synth
   mirrors the change.
3. Need to test? Hit **Send OSC test ping** to fire a frame through the current
   mapping.
4. Undo is one click away; the history stack keeps the last 32 snapshots.
5. Click **Show diff** before saving to see exactly what will be written.

## Demo profile
See `config/mapping.demo.yaml` for a talk-through-ready preset with annotated
ranges explaining the "why" behind each choice. Load it with:
```bash
python host/python/app.py --mapping config/mapping.demo.yaml --demo --api-port 9000
```
Tweak, save, and commit your own presets as you go.

## Paper trail etiquette
Save early, save noisy. Each **Save** call writes the YAML, refreshes the diff
baseline, and logs the event with a timestamp so your future self can replay the
session without digging through git history.
