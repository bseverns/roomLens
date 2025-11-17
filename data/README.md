# data/
*What lives here, why it's shaped like NDJSON, and how to regen it without a lab full of sensors.*

## `demo_walkthrough.ndjson`
- **What it is**: 120 frames emitted by the fake sensor generator that ships in
  `host/python/app.py --demo`. Each frame captures the same feature set the
  Teensy would publish: `mic_rms`, `mic_sc`, `tof_motion`, `tof_near`,
  `distance_cm`, `lux`, `flicker`, `motion`, plus a `t` timestamp in
  milliseconds.
- **Why NDJSON**: newline-delimited JSON is stream-friendly; the host and
  `MappingPipeline` already expect one JSON blob per line. You can `tail -f` the
  file, `rg` through it, or feed it directly into
  `host/python/replay_example_data.py` without touching Pandas.
- **How it was captured**: run the host demo with recording enabled so we only
  depend on repo code, no secret hardware:
  ```bash
  cd host/python
  python app.py --demo --record ../../data/demo_walkthrough.ndjson --max-frames 120
  ```
  That bakes the same smooth walk-up / walk-away behavior the README references.
- **When to use it**: anytime you want to validate mapping math, teach the
  pipeline, or hack a synth with no physical rig connected. Pair it with
  `python replay_example_data.py --loop` for laptop rehearsals.
- **Replace/extend it**: log your own frames with `tools/capture_logger.py` or
  `python app.py --port /dev/ttyACM0 --record data/my_room.ndjson`. Drop the file
  anywhere under `data/` and point the replay CLI at it via `--file`.
- **Safety note**: scrub files before sharing—NDJSON is plain text, so it’s easy
  to confirm there’s no personally identifying info. Keep samples short and
  anonymized when working with students.

If you add new recordings, jot a quick note below (what room, which sensors, any
quirks) so future hackers know what vibe they’re importing:

| file | origin | notes |
|------|--------|-------|
| `demo_walkthrough.ndjson` | `host/python/app.py --demo` | Smooth sweep through faux motion + lux drift, 120 frames |
