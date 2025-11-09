# Serial Webcam Bridge (Processing)

Pair this sketch with the Pro Mini firmware when you want to borrow a laptop’s
webcam as a makeshift motion sensor. It watches the camera, estimates simple
frame-to-frame change, and streams `cam:<value>` lines over serial so the Pro
Mini can fold them into its JSON frames.

## Quickstart
1. Open `SerialWebcamBridge.pde` in Processing 4.x.
2. Adjust `serialIndex` near the top of the file so it points at your FTDI
   adapter (check the console output after `printArray(Serial.list())`).
3. Hit run. You should see your webcam feed plus a magenta bar that mirrors the
   motion score.
4. Plug in the Pro Mini node. The sketch immediately starts writing `cam:` lines
   to the board; the firmware confirms the link by echoing `cam_motion` values in
   its JSON stream.

## Tuning knobs
- `smoothing` softens the motion envelope. Lower values track faster but jitter
  more.
- `gain` converts raw pixel differences into the 0–1 range. Increase it for more
  sensitivity in darker rooms.
- Swap the motion metric entirely if you want: optical flow, face detection, or
  brightness averages all fit—just keep writing `cam:<0..1>` lines.

Document what you discover in the field and push your variations back here. The
whole point is to keep the kit hackable.
