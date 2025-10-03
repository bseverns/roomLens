
/*
  Room Lens — Teensy 4.0 firmware skeleton
  ========================================

  This file is the "hardware diary" for the embedded side of Room Lens. It is
  intentionally over-commented so you can co-teach firmware, sensing, and sound
  mapping without flipping between notebooks.

  Intent
  ------
  * Poll a handful of staple sensors (mic preamp + ADC, VL53L1X ToF, TSL2591
    lux, PIR/IMU) at a gentle frame rate.
  * Compute a few deliberately transparent features: RMS loudness, spectral
    centroid proxy, motion deltas, flicker energy.
  * Stream normalized JSON frames over Serial where the Python host can catch
    them, map them, and shoot them into OSC.

  References
  ----------
  [1] PJRC. "Teensy 4.0 Technical Specifications." 2024.
  [2] SparkFun / STMicroelectronics. "VL53L1X Time-of-Flight Sensor Breakout".
      Hookup Guide, 2023.
  [3] Adafruit. "TSL2591 High Dynamic Range Digital Light Sensor". Learning
      Guide, 2022.
  [4] Analog Devices. "AN-1354 RMS-to-DC Conversion Techniques". 2015.

  BUILDING
  --------
  * PlatformIO env: `teensy40`
  * Adjust pin assignments and sensor choices below as your rig evolves. The
    helper functions are purposely stubbed so that dropping in real sensor
    drivers is obvious (see `readMicRms()`, etc.).
*/

#include <Arduino.h>
#include <math.h>

// ---- Sensor placeholders (swap real drivers later) ----
struct SensorFrame {
  float mic_rms;               // 0..1 (log scaled)
  float mic_spectral_centroid; // 0..1 (site-norm)
  float tof_motion;            // 0..1 (delta distance)
  float tof_proximity;         // 0..1 (near = 1)
  float lux_level;             // 0..1 (site-norm)
  float flicker_hz;            // 0..1 (normalized 50-120Hz band)
  bool  motion_flag;           // PIR/IMU burst
  uint32_t ms;                 // timestamp
};

// ---- Configuration knobs for demos ----
static const uint32_t FRAME_HZ = 25;     // how often we publish frames
static const uint32_t FRAME_MS = 1000 / FRAME_HZ;

// Pin aliases (adjust to your wiring). These default to common breakout wiring
// suggestions in the SparkFun / Adafruit guides noted above.
static const int PIN_MIC_ADC   = A2;  // Electret mic preamp output
static const int PIN_PIR       = 6;   // Digital PIR output
static const int PIN_IMU_INT   = 8;   // Optional IMU interrupt

// Simple helpers for smoothing / clamping -----------------------------------
static inline float clamp01(float x){ return x < 0 ? 0 : (x > 1 ? 1 : x); }

// Placeholder signal generators to simulate sensors during bringup. These
// provide deterministic wobble so host-side unit tests have stable behaviour.
float pseudo_noise(float phase) {
  // Cheap, deterministic wobble for demos
  return 0.5f + 0.5f * sinf(phase) * cosf(0.7f*phase);
}

// ---- Hardware abstraction stubs -------------------------------------------
// Each function returns a normalized value in [0, 1]. Replace the internals
// with real driver calls once you solder sensors.

float readMicRms() {
  // In production you would run a proper RMS or envelope follower here. See
  // Analog Devices AN-1354 (Ref. [4]) for practical RMS-to-DC approaches.
  return clamp01(0.15f + 0.1f * pseudo_noise(millis() * 0.0017f));
}

float readMicSpectralCentroid() {
  // Placeholder: a full implementation would buffer audio samples, run an FFT,
  // compute centroid, then normalise to a site-specific band (Refs. [1,4]).
  return clamp01(0.4f + 0.3f * pseudo_noise(millis() * 0.0009f));
}

float readToFMotion() {
  // A VL53L1X can report distance at ~50 Hz. Differencing successive readings
  // and rectifying gives a usable "motion energy" metric (Ref. [2]).
  return clamp01(fabsf(0.5f - pseudo_noise(millis() * 0.0023f)) * 2.0f);
}

float readToFProximity() {
  // Close range → value near 1. Map linearly for now; calibrate via YAML later.
  return clamp01(pseudo_noise(millis() * 0.0005f));
}

float readLuxLevel() {
  // The TSL2591 exposes lux via I2C. Here we just wobble. Refine using site
  // calibration and the lux_normalize helper on the host (Ref. [3]).
  return clamp01(0.3f + 0.6f * pseudo_noise(millis() * 0.0001f));
}

float readFlicker() {
  // Some light sensors expose flicker content directly; otherwise you can FFT a
  // rolling buffer. For the skeleton we just create motion in the 50-120 Hz band.
  return clamp01(pseudo_noise(millis() * 0.0031f));
}

bool readMotionFlag(float motionEnergy) {
  // Combine PIR and IMU status if available. Here we threshold the fake ToF
  // motion as a stand-in.
  return motionEnergy > 0.65f;
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000) { /* wait for USB */ }

  // In real builds: init I2C (Wire.begin()), configure ToF, light, mic front-end,
  // calibrate offsets, etc. Document every assumption in docs/ASSUMPTION_LEDGER.
  Serial.println(F("{\"event\":\"boot\",\"device\":\"roomlens-teensy\"}"));
}

void loop() {
  static uint32_t last = 0;
  const uint32_t now = millis();
  if (now - last < FRAME_MS) return;
  last = now;
  
  // Simulated demo signals; replace with real reads + feature extraction.
  // The helper functions above keep the "hardware" surface area obvious.
  SensorFrame f;
  f.mic_rms               = readMicRms();
  f.mic_spectral_centroid = readMicSpectralCentroid();
  f.tof_motion            = readToFMotion();
  f.tof_proximity         = readToFProximity();
  f.lux_level             = readLuxLevel();
  f.flicker_hz            = readFlicker();
  f.motion_flag           = readMotionFlag(f.tof_motion);
  f.ms                    = now;

  // Stream as compact JSON line (host/python/app.py expects this). The JSON is
  // easy to sniff with `screen` or `pyserial` during debugging sessions.
  Serial.print(F("{\"t\":")); Serial.print(f.ms);
  Serial.print(F(",\"mic_rms\":")); Serial.print(f.mic_rms, 3);
  Serial.print(F(",\"mic_sc\":")); Serial.print(f.mic_spectral_centroid, 3);
  Serial.print(F(",\"tof_motion\":")); Serial.print(f.tof_motion, 3);
  Serial.print(F(",\"tof_near\":")); Serial.print(f.tof_proximity, 3);
  Serial.print(F(",\"lux\":")); Serial.print(f.lux_level, 3);
  Serial.print(F(",\"flicker\":")); Serial.print(f.flicker_hz, 3);
  Serial.print(F(",\"motion\":")); Serial.print(f.motion_flag ? 1 : 0);
  Serial.println(F("}"));
}
