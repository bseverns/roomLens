# calibration/
*Keep the sensors honest. This is the drawer for baseline offsets, mic trims, and other “don’t drift on me” notes.*

## What lives here
- `example_baseline.yaml`: synthetic offsets taken from the repo’s own demo stream so nobody chases a ghost path. Use it as a format reference or a zero-drift fallback when you’re hacking without hardware.
- Your future files: one YAML per rig or room. Keep the filename human (e.g., `studio-a-2024-05.yaml`).

## Why bother
Sensors creep. HVAC kicks in, LEDs flicker, and suddenly your “still room” is screaming. Baseline offsets let you center the inputs so mapping math stays musical instead of brittle.

## Fast path (no hardware, just vibes)
1. Keep `example_baseline.yaml` in place. It assumes a quiet, synthetic room and keeps demo runs from blowing up your mappings.
2. Point any quick script at it to subtract offsets before shoving frames through the pipeline:
   ```python
   import yaml, json

   offsets = yaml.safe_load(open("data/calibration/example_baseline.yaml"))['offsets']
   frame = json.loads('{"mic_rms": 0.05, "lux": 123}')
   calibrated = {k: frame.get(k, 0) - offsets.get(k, 0) for k in frame}
   print(calibrated)
   ```

## Generate your own baseline (actual rig)
1. **Warm up**: let the rig sit 2–3 minutes so sensors stop drifting. Note the room vibe in your lab notebook.
2. **Record a still room**: capture ~10–30 seconds of frames to NDJSON. With hardware connected it might look like:
   ```bash
   cd host/python
   python app.py --port /dev/ttyACM0 --record ../../data/calibration/studio-a.ndjson --max-frames 900
   ```
   No rig yet? Use `--demo` to create a synthetic capture; it still exercises the same code path.
3. **Crunch offsets**: take medians so outliers don’t punk your math. This inline script writes a YAML next to your capture:
   ```bash
   python - <<'PY'
   import json, statistics, yaml, pathlib

   capture = pathlib.Path("data/calibration/studio-a.ndjson")
   values = {}
   for line in capture.read_text().splitlines():
       frame = json.loads(line)
       for k, v in frame.items():
           if isinstance(v, (int, float)):
               values.setdefault(k, []).append(v)

   offsets = {k: statistics.median(vs) for k, vs in values.items()}
   out = capture.with_suffix(".yaml")
   out.write_text(yaml.safe_dump({"captured_at": "now", "source": str(capture), "offsets": offsets}, sort_keys=True))
   print(f"wrote {out}")
   PY
   ```
4. **Track context**: add a `notes` field to your YAML: room size, light sources, HVAC state. Future you will care.

## How to use offsets
- **Host Python**: subtract offsets before you normalize or map. The `MappingPipeline` accepts plain dicts, so pre-process frames inline like the snippet above.
- **Firmware experiments**: mirror the numbers in your microcontroller constants if you’re trimming raw ADC values upstream.
- **Docs/tests**: if you ship a new baseline, mention it in `data/README.md` and adjust fixtures when needed so CI doesn’t yell.

## File format
YAML with three keys: `captured_at` (ISO-ish string), `source` (command or rig name), `offsets` (dict of sensor → baseline). Extra fields are welcome—this folder is half studio notebook, half teaching guide. No binary blobs; keep it diffable.
