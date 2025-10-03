
# First Test — Room tone → gesture

This micro‑ritual is the handshake between Room Lens, MOARkNOBS‑42 swagger, and perceptual‑drift patience. It’s the fastest way to hear how a space answers back when you poke it with sensors.

## Prep the stage
1. **Scout the room**: jot the time of day, lighting mood, HVAC noise, and anything else you’d scribble in a studio logbook.
2. **Tune the mapping**: tweak `config/mapping.default.yaml` before you hit record. Mark what you changed and *why*.
3. **Warm up the host**:
   ```bash
   cd ../../host/python
   python app.py --port auto --dry-audio
   ```
   Keep the terminal visible; call out any spikes or lulls like you’re narrating a live mix.

## Run the gesture experiment
1. **Stillness pass**: leave the room alone for 60 seconds. Note the baseline readings.
2. **Gesture sweep**: perform the prompts from `docs/TEST_PLAN.md` (door open, light change, walk through, etc.). Only change one thing at a time.
3. **Listen + react**: if you booted the SuperCollider patch, ride the faders (virtual or literal) as if you were on a 42‑knob monster. Capture those instincts in `notes.md`.
   - **VCV Rack spin**: load `../vcv-rack/roomlens_scene_receiver.vcv` (or `roomlens_texture_memory.vcv` if you need extra shimmer). Make sure the OSC ports match `app.py`. Use the MixMaster macros to exaggerate each gesture and print your settings inside the Notes module before closing.

## Capture + stash artifacts
- `notes.md` — observations, surprises, hypotheses, failed stunts. Paste the text from any VCV Rack Notes modules here too.
- `capture.csv` — exported sensor frames if you opted into logging. Highlight timestamps where something wild happened.
- `audio.wav` — synth output, whether glorious or busted. Annotate start/end gestures.
- `photos/` *(optional)* — snapshots of the setup, whiteboard scribbles, or the room mid‑performance.

## Debrief prompts
- What did the room refuse to do, even when you begged with extra gain?
- Which mapping choices felt like overkill once you heard the data?
- How would a collaborator inherit this session and push it further tomorrow?

Treat this folder like a studio notebook: messy, honest, but documented so the next drift session starts a little wiser.
