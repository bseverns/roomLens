
/*
  Room Lens — Teensy 4.0 firmware skeleton
  Intent: read a minimal set of sensors, compute simple features,
  and stream normalized frames over Serial for a host synth.
  Design: scene-first. Transparent data flow for teaching.

  BUILDING:
    - PlatformIO env: teensy40
    - Adjust pins/sensors as your hardware solidifies.
*/

#include <Arduino.h>

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

// Simple helpers for smoothing / clamping
static inline float clamp01(float x){ return x < 0 ? 0 : (x > 1 ? 1 : x); }

// Placeholder signal generators to simulate sensors during bringup.
float pseudo_noise(float phase) {
  // Cheap, deterministic wobble for demos
  return 0.5f + 0.5f * sinf(phase) * cosf(0.7f*phase);
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 2000) { /* wait for USB */ }

  // In real builds: init I2C, configure ToF, light, mic front-end, etc.
  Serial.println(F("{\"event\":\"boot\",\"device\":\"roomlens-teensy\"}"));
}

void loop() {
  static uint32_t last = 0;
  static float t = 0.0f;
  const uint32_t now = millis();
  if (now - last < FRAME_MS) return;
  last = now;
  t += 0.02f;

  // Simulated demo signals; replace with real reads + feature extraction
  SensorFrame f;
  f.mic_rms               = clamp01(0.15f + 0.1f * pseudo_noise(t*1.7f));
  f.mic_spectral_centroid = clamp01(0.4f  + 0.3f * pseudo_noise(t*0.9f));
  f.tof_motion            = clamp01(fabsf(0.5f - pseudo_noise(t*2.3f))*2.0f);
  f.tof_proximity         = clamp01(pseudo_noise(t*0.5f));
  f.lux_level             = clamp01(0.3f  + 0.6f * pseudo_noise(t*0.1f));
  f.flicker_hz            = clamp01(pseudo_noise(t*3.1f));
  f.motion_flag           = (f.tof_motion > 0.65f);
  f.ms                    = now;

  // Stream as compact JSON line (host/python/app.py expects this)
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
