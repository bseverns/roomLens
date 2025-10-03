# Room Lens Hardware Skeleton
*1/2 studio notebook, 1/2 teaching guide. Annotate it like you're explaining the solder joints to your future collaborators after a long gig.*

## Intent (why this rig exists)
- **Documented sensing chain**: leave a breadcrumb trail from each physical sensor to the feature names used in `config/mapping.default.yaml`.
- **Swap-friendly harness**: every sensor lives on JST/Grove headers or breadboard jumpers so students can yank hardware without rage.
- **Ethical defaults**: power rails and enclosures are planned to hide and mute sensors quickly. See `docs/PRIVACY_ETHICS.md` for the vibe.

## Reference build overview
```text
[12V DC brick]
      │
  [Buck converter 5V]──┬─────────────┬─────────────────────┬───────────┐
                        │             │                     │           │
                    Teensy 4.0   VL53L1X ToF          TSL2591 lux   PIR sensor
                        │             │                     │           │
                   ICS-43434 I2S mic  └─ I2C bus ───────────┘           │
                        │                                               │
                   I2C hub (optional)                                   │
                        │                                               │
                  BNO055 (9DoF IMU) <──── UART alt if I2C gets noisy ───┘
```

### Bill of materials (Rev 0.1, classroom friendly)
| Qty | Part | Notes |
| --- | ---- | ----- |
| 1 | [Teensy 4.0](https://www.pjrc.com/store/teensy40.html) | Main brain; 600 MHz headroom lets us prototype DSP on-device. |
| 1 | [SparkFun VL53L1X breakout](https://www.sparkfun.com/products/14722) | Time-of-flight range sensing, Ref. [2]. |
| 1 | [Adafruit TSL2591 breakout](https://www.adafruit.com/product/1980) | Lux + flicker, Ref. [3]. |
| 1 | [Adafruit ICS-43434 I2S mic breakout](https://www.adafruit.com/product/4379) | Low-noise digital mic; route to Teensy I2S pins for future DSP. |
| 1 | [Adafruit PIR sensor (Motion)](https://www.adafruit.com/product/189) | Classic PIR for burst detection. |
| 1 | [Adafruit BNO055 breakout](https://www.adafruit.com/product/2472) | Optional orientation/gesture sensor. |
| 1 | Buck converter 12V→5V (e.g. Pololu D24V5F5) | Power headroom for future LED feedback. |
| 1 | Meanwell 12V 2A wall wart | Keep noise low with a solid supply. |
| assorted | Grove/JST-SH cables + dupont jumpers | Quick swaps in workshops. |
| assorted | 3D-printed brackets or velcro ties | Affix sensors to walls/ceilings without damage. |

> Punk-rock tip: label *every* cable with painter's tape and a marker. Future you will thank present you when patching in the dark.

## Wiring cheatsheet
- **Power rails**: keep analog and digital grounds short and shared near the Teensy. Run 5V from the buck to the ToF/lux/PIR modules; tap 3.3V from the Teensy for the mic and IMU.
- **I2C bus**: Teensy SDA/SCL on pins 18/19 → ToF + Lux + IMU. Add a STEMMA QT/Grove hub if you want hot-swaps. Pull-ups: 4.7 kΩ to 3.3 V.
- **I2S mic**: ICS-43434 `SD`→Teensy pin 8, `SCK`→pin 21, `WS`→pin 20, `L/R` tied to ground for left channel only. Use twisted pair for SD/SCK.
- **PIR**: signal → Teensy pin 6 (`PIN_PIR` in firmware). Provide 5 V power but level-shift/voltage divide to 3.3 V logic if your module lacks it.
- **IMU (BNO055)**: prefer I2C @ 400 kHz. If you encounter bus hangs under heavy EMI, move to UART on Serial1 (pins 0/1) and flip the firmware stub.

## Feature mapping glossary
| Firmware stub | Physical source | Feature summary | Host alias |
| ------------- | ---------------- | --------------- | ---------- |
| `readMicRms()` | ICS-43434 mic → on-board DSP | RMS envelope (Ref. [4]) | `mic_rms` → grain density |
| `readMicSpectralCentroid()` | Same mic | Quick-and-dirty centroid (FFT or Goertzel) | `mic_sc` → filter cutoff |
| `readToFMotion()` | VL53L1X | Rectified distance deltas | `tof_motion` → FM index |
| `readToFProximity()` | VL53L1X | Normalized distance | `tof_near` → pitch cluster |
| `readLuxLevel()` | TSL2591 | Normalized lux | `lux` → reverb mix |
| `readFlicker()` | TSL2591 | Flicker energy 50–120 Hz | `flicker` → delay time |
| `readMotionFlag()` | PIR/IMU | Binary burst detection | `motion` → envelope attack |

## Bring-up protocol
1. **Power-only smoke test**: connect the 12 V brick, measure 5 V and 3.3 V rails before attaching sensors. Log the readings in your lab book.
2. **I2C scan**: load the standard Wire scanner sketch. Confirm addresses `0x29` (VL53L1X), `0x29` (TSL2591, yes same default — change one via solder bridge), `0x28` (BNO055). Document any address flips in `docs/MAPPING_TABLE.md`.
3. **Audio sanity**: run the ICS-43434 loopback sketch to verify the mic is alive. Hum near it and watch the RMS plot in Arduino Serial Plotter.
4. **Firmware skeleton**: flash `firmware/roomlens-teensy`. Watch the JSON stream in `host/python/app.py --dry-audio`. Confirm values wobble; annotate what each sensor physically does.
5. **Calibrate**: sit the rig in a quiet room, record baseline values, and tweak `config/mapping.default.yaml` ranges. Commit the changes like you would commit a patchbay reroute.

## Expansion ideas
- Add WS2812 LEDs as a visual feedback bar driven by `axes` values (remember level shifting!).
- Bring in BLE presence via an ESP32 co-processor speaking UART to the Teensy.
- Build a magnet-mount rig for ceilings. Document the load paths and be kind to the building.

## References
1. PJRC. *Teensy 4.0 Technical Specifications.* https://www.pjrc.com/store/teensy40.html (accessed 2024-03-05).
2. SparkFun. *VL53L1X Time-of-Flight Sensor Hookup Guide.* https://learn.sparkfun.com/tutorials/vl53l1x-distance-sensor-hookup-guide (2023).
3. Adafruit. *TSL2591 High Dynamic Range Digital Light Sensor.* https://learn.adafruit.com/adafruit-tsl2591 (2022).
4. Analog Devices. *AN-1354 RMS-to-DC Conversion Techniques.* https://www.analog.com/media/en/technical-documentation/application-notes/AN-1354.pdf (2015).
