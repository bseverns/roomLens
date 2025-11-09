# Room Lens — Pro Mini Field Pack

This is the scrappy field variant of the Room Lens firmware. It trades the
luxury sensor bar on the Teensy rig for a minimal stack that fits on an Arduino
Pro Mini (3.3 V / 8 MHz) and happily rides an FTDI cable. The goal is to have a
battery-sipping node that you can toss in a backpack, plug into a laptop
running Processing, and still stream meaningful room features back to the Room
Lens host.

## Intent
- Keep the feature frame shape compatible with the existing Python host so you
  can hot swap nodes without rewriting the mapping YAML.
- Focus on "always-available" parts: an electret mic breakout, a light sensor
  (LDR + resistor ladder or any analog lux breakout), and an optional PIR for
  binary motion.
- Accept a **webcam motion channel** piped in from a Processing sketch. The
  sketch computes per-frame motion from a USB webcam and drips normalized
  values down the same serial link; the Pro Mini folds that into the outgoing
  JSON.

## BOM shorthand
| Subsystem     | Suggested part                      | Notes |
| ------------- | ----------------------------------- | ----- |
| MCU           | Arduino Pro Mini (3.3 V / 8 MHz)    | Stick with 3.3 V so the analog breakouts stay happy. |
| Mic           | SparkFun Electret Mic Breakout      | Any amplified electret that outputs ~0–3.3 V works. |
| Light         | Photoresistor + 10 kΩ resistor      | Wire as a voltage divider into A1. |
| Motion (opt.) | PIR (HC-SR501 trimmed to 3.3 V)     | Jumper to digital pin 3 with a resistor divider if needed. |
| Host link     | FTDI Basic (3.3 V)                  | Share ground, match voltage levels. |

## Build + flash
1. Install [PlatformIO](https://platformio.org/). This repo already includes the
   config for the Pro Mini target.
2. Plug in the FTDI adapter and find its port (macOS/Linux: `ls /dev/tty.*`).
3. From this folder run:

   ```bash
   pio run -t upload --environment promini
   ```

   The `monitor_speed` is 115200 by default; `pio device monitor` will let you
   peek at the JSON stream.

## Processing webcam bridge
The firmware listens for ASCII lines that look like `cam:0.42`. We ship a
sketch in `examples/processing/serial_webcam_bridge/SerialWebcamBridge.pde` that
watches a webcam, computes a motion score, and sends those lines over serial.
You can remix it to drive other computer-vision features—just keep the `cam:`
label so the firmware knows which channel to update.

Workflow checklist:
1. Start the Processing sketch; confirm you see the webcam feed and the serial
   port is open.
2. Plug the Pro Mini node in via FTDI. Once it boots it will log a boot JSON and
   start streaming frames at ~12 Hz.
3. Move in front of the webcam; the Processing sketch pushes the normalized
   motion value. The Pro Mini includes it in each JSON frame as `cam_motion`.
4. Point the Room Lens host at the FTDI port (or bridge via the Processing
   sketch) and update the mapping YAML to reflect the leaner feature set.

## Frame shape
Each line of serial output is JSON with these keys:

| Field        | Description                                               |
| ------------ | --------------------------------------------------------- |
| `t`          | Milliseconds since boot                                   |
| `mic_rms`    | Envelope follower on the electret mic (0–1 normalized)    |
| `mic_peak`   | Peak detector on the same window (fast transient energy)  |
| `lux`        | Averaged analog light level (0–1 normalized)              |
| `pir`        | Digital PIR state (0 or 1)                                |
| `cam_motion` | Last webcam motion value sent from Processing (0–1 clamp) |

## Why this build exists
Think of this firmware as the "street team" version of Room Lens: it’s cheap,
understands just enough about the room to sketch a baseline, and lets your
laptop handle the heavier perception work (webcam, OSC, synthesis). Document
what you learn in your own field notes and share the good bits back here.
