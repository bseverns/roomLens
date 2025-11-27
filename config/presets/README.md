# Patch presets (studio-notebook edition)

These YAML files ride on top of `config/mapping.default.yaml` via the new
preset resolver. Think of them as starting scenes you can hot-swap mid-set.

## How it works

- Drop a patch in this folder (e.g. `quiet_gallery.yaml`).
- The host deep-merges it over the base mapping, logging every field it
  overrides so you know exactly what changed.
- Snapshots land in `config/snapshots/` with timestamps so you can rewind your
  experiments later. Opt into a small in-memory ring buffer with
  `--snapshot-history 4` to flick between "now" and "previous".

## Live controls

- CLI: `python host/python/app.py --patch quiet_gallery`
- OSC: send `/patch <name>` to the host (enable with `--osc-in 57121`).
- MIDI: hit the configured note (default: Middle C) to cycle presets or sweep a
  CC (default: CC1) to jump to a preset by value.

## Preset ethos

Each patch here is annotated with intent and safety notes. The point is to
preserve scene vibes, not just flip switches. Use them as teaching artifacts or
as-need-now starting points.
