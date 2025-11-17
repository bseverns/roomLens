# Room Lens system overview
*A postcard for the whole rig — sensors → computer → mapping code → output.*

The instrument is intentionally legible: every piece is hackable and the flow is
traceable enough to use as a classroom handout. Tape this page above your work
bench.

```
[ Sensors ] --raw data--> [ Teensy firmware ] --feature JSON--> [ Host computer ]
     |                          |                                       |
     |                          |--pre-processed frames----------------->|
     |                                                                  \
     v                                                                   \
  Mic / ToF / Light / PIR                                               [ roomlens.MappingPipeline ]
                                                                          |
                                                                          |--axes--> OSC / logs / notebooks
                                                                          v
                                                                    SuperCollider / Pd / VCV / visualizers
```

1. **Sensors**: microphones for loudness + spectral centroid, a VL53L1X
   time-of-flight ranger for motion and proximity, lux/flicker sensing, and PIR
   or IMU motion. Swap anything you want—just keep the JSON keys stable or edit
   the mapping YAML.
2. **Teensy firmware**: polls the sensors, extracts features (RMS, Δ distance,
   flicker bands, etc.), and spits newline-delimited JSON over USB serial.
3. **Host computer**: `host/python/app.py` listens to serial (or uses the
   built-in demo generator) and shares frames with the reusable
   `roomlens.MappingPipeline` package.
4. **Mapping code**: `MappingPipeline` + `config/mapping.default.yaml` translate
   normalized features into synth axes. Everything downstream — OSC synths,
   SuperCollider patches, logging notebooks — reads the exact same mapping math.
5. **Output**: OSC to `host/supercollider/RoomLens.scd`, Pd/VCV patches, or a
   plain JSON log when you run with `--dry-audio`.

## "No hardware" replay mode
Sometimes the rig is across town or checked out by another group. Use the
``host/python/replay_example_data.py`` helper to replay a captured dataset
through the live mapping stack.

```bash
cd host/python
python replay_example_data.py --file ../data/demo_walkthrough.ndjson --sleep 0.05
```

* `data/demo_walkthrough.ndjson` is a 120-frame capture of the fake demo sensor
  generator (smooth motion, proximity sweeps, slow lux drift). Swap in your own
  logs from `tools/capture_logger.py` to audition a site before hauling in the
  synth rig.
* Pass `--loop` to cycle endlessly, `--max-frames 512` to rehearse a short
  burst, and `--mapping config/profiles/gymnasium.yaml` (for example) when you
  want to test a custom mapping.

Replay mode prints the processed axis payloads to stdout, so you can pipe them
into other scripts, feed OSC recorders, or just watch the numbers bend as you
edit the YAML. All of this keeps the repo a split-brain notebook: half studio
experiments, half teaching aid.
