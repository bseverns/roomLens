# VCV Rack Patch Pack — Room Lens Scene Reactors

*Half modular playground, half lab notebook. These patches lift the same modular skeletons I keep in the `vcv_patch` repo — `trowaSoft OSCcv` for feature ingress, `Fundamental` VCO/VCF/VCA chains for tone shaping, `MindMeld` mix buses for quick routing — and wrap them in prompts so a fresh Room Lens pilot can get noisy fast without forgetting to take notes.*

> **Install list** (match the `vcv_patch` repo defaults): `Core`, `Fundamental`, `trowaSoft`, `MindMeld Modulation`, `Valley`, `Bogaudio`, and `Stoermelder PackOne`. All are free in the VCV Library. Sync first, patch second.

---

## Files

| File | What it’s for | Starter moves |
| --- | --- | --- |
| `roomlens_scene_receiver.vcv` | Eight-channel OSC bridge that mirrors the baseline patch in `vcv_patch/scene-receiver`. Routes raw feature streams into tone, filter, and dynamics lanes so you can hear a room breathe in under 60 seconds. | Fire up the Python host with `--osc-port 7000`, load the patch, assign your audio interface on **Audio-8**, and ride the mix using the `MindMeld MixMaster` scene macros. Annotate every mapping pivot in the Notes panel. |
| `roomlens_texture_memory.vcv` | Adds delay, shimmer, and feedback inspired by the `vcv_patch/perceptual-memory` example. Useful when you need to exaggerate slow drifts (HVAC swings, light dimming) for workshops. | Keep the OSC bridge but patch channels 5–8 into `Valley Plateau` and `Bogaudio DLY`. Record both the wet return and the dry reference so you can teach the difference between “room truth” and “processed myth.” |

Each patch includes two `Core/Notes` modules: the left one is a quick-start checklist, the right one is a log stub. Treat them like the margin scribbles in a studio workbook. Screenshot or export the notes before closing.

---

## Session recipe

1. **Sync with the host**
   - Launch `host/python/app.py --osc-port 7000 --profile default` so the OSC names match the patch labels (same convention as in the `vcv_patch` repo).
   - Confirm packets with `tools/capture_logger.py --preview` if you want to sniff the stream before trusting it.
2. **Patch recall**
   - In VCV Rack, open one of the `.vcv` files. If Rack complains about a missing module, grab it from the Library and re-open. Keep a running list of installs in your notebook.
   - Assign your audio device on `Audio-8`. Channels 1–2 are stereo out; channels 3–8 are free if you need to multitrack stems into a DAW.
3. **Map the scene**
   - Channel mapping matches the sensor order in `config/mapping.default.yaml`: `0` = loudness RMS, `1` = spectral centroid, `2` = motion energy, `3` = lux delta, `4` = occupancy probability, `5` = temperature drift, `6` = humidity swing, `7` = BLE presence density.
   - Each patch already uses the first six lanes. The last two are left dangling for you to claim mid-session. Document what you decided and why.
4. **Play + annotate**
   - Use the provided macro knobs (`MindMeld` module) or the `Stoermelder MIDI-CAT` mapping to improvise safe gain staging.
   - Log every “what just happened?” moment in the Notes module with timestamp + gesture + patch tweak.
5. **Bounce + archive**
   - Print stems out of Rack or capture them in your DAW.
   - Export the patch with a new filename, commit alongside your Room Lens sensor logs, and summarize the session in `examples/first-test/notes.md`.

---

## Teaching prompts

- Have learners solo each OSC channel through `MindMeld Aux` returns to hear the raw modulation before it hits the synth. Ask them to sketch the perceived gesture.
- Challenge: disconnect the provided LFO-to-ADSR modulation and replace it with an envelope follower from `Bogaudio`. Compare responsivity.
- After the jam, copy the Notes text into your research log and tag any “mystery responses” for deeper mapping tweaks.

Stay scrappy. The goal is to make the room feel like a collaborator, not a lab specimen.
