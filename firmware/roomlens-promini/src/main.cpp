/*
  Room Lens — Pro Mini field firmware
  ===================================

  This sketch is the lean cousin of the Teensy firmware. It lives on a 3.3 V
  Arduino Pro Mini, keeps only the evergreen sensors (mic + light + PIR), and
  leaves the fancy perception to a Processing sketch that can mail webcam motion
  scores over the same serial link.

  Design notes
  ------------
  * Frame cadence is intentionally slower (~12 Hz) to stay kind to the 8-bit MCU
    and leave room for serial chatter from the Processing bridge.
  * Audio features are computed with tiny, comprehensible math: an RMS window and
    a peak detector over a short sample burst.
  * Incoming lines that start with `cam:` are parsed as normalized webcam motion
    values. The most recent value is echoed in every JSON frame as `cam_motion`.
  * Everything else is old-school Arduino: analogRead on A0/A1, digitalRead on
    D3. No dynamic allocation, no surprises.

  Wiring cheatsheet
  -----------------
  * A0 — Electret mic breakout output
  * A1 — Light sensor voltage divider (0–3.3 V)
  * D3 — PIR output (HIGH = motion)
  * FTDI RX/TX — Serial console @ 115200 baud
*/

#include <Arduino.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

// --- Configuration knobs -----------------------------------------------------
static const uint8_t PIN_MIC = A0;
static const uint8_t PIN_LUX = A1;
static const uint8_t PIN_PIR = 3;

static const uint16_t FRAME_HZ = 12;
static const uint16_t FRAME_MS = 1000 / FRAME_HZ;

static const uint16_t MIC_WINDOW_MS = 16;   // sampling window for RMS/peak
static const float    MIC_PEAK_DECAY = 0.9; // decay factor per frame

static const uint32_t CAM_DECAY_MS = 4000;  // fade webcam motion if host stops

// --- Helpers -----------------------------------------------------------------
static inline float clamp01(float x) {
  if (x < 0.0f) return 0.0f;
  if (x > 1.0f) return 1.0f;
  return x;
}

// Rolling storage for the host-provided webcam motion value.
static float    g_camMotion = 0.0f;
static uint32_t g_camMotionMs = 0;

// Parse ASCII commands of the form "cam:0.42".
void parseCommand(const char *line) {
  if (strncmp(line, "cam:", 4) == 0 || strncmp(line, "cam=", 4) == 0) {
    const float value = atof(line + 4);
    g_camMotion = clamp01(value);
    g_camMotionMs = millis();
  }
}

void ingestHostSerial() {
  static char buffer[32];
  static uint8_t index = 0;

  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r' || c == '\n') {
      if (index > 0) {
        buffer[index] = '\0';
        parseCommand(buffer);
        index = 0;
      }
    } else if (index < sizeof(buffer) - 1) {
      buffer[index++] = c;
    }
  }
}

float readLightLevel() {
  // Average a few samples to tame noise and normalise to 0..1.
  const uint8_t sampleCount = 8;
  uint32_t accumulator = 0;
  for (uint8_t i = 0; i < sampleCount; ++i) {
    accumulator += analogRead(PIN_LUX);
  }
  const float average = static_cast<float>(accumulator) / sampleCount;
  return clamp01(average / 1023.0f);
}

float readMicRms(uint16_t windowMs, float *outPeak) {
  const uint32_t startMs = millis();
  uint32_t sumSquares = 0;
  uint16_t sampleCount = 0;
  uint16_t peak = 0;

  while ((millis() - startMs) < windowMs) {
    const uint16_t raw = analogRead(PIN_MIC);
    const int16_t centered = static_cast<int16_t>(raw) - 512;
    const uint16_t magnitude = abs(centered);
    if (magnitude > peak) {
      peak = magnitude;
    }
    sumSquares += static_cast<uint32_t>(centered) * static_cast<uint32_t>(centered);
    ++sampleCount;
  }

  const float meanSquares = (sampleCount > 0)
                                ? static_cast<float>(sumSquares) / sampleCount
                                : 0.0f;
  const float rms = sqrtf(meanSquares) / 512.0f;  // 512 ≈ mid-scale at 10-bit

  if (outPeak) {
    const float peakNorm = clamp01(static_cast<float>(peak) / 512.0f);
    *outPeak = peakNorm;
  }
  return clamp01(rms);
}

bool readPirState() {
  return digitalRead(PIN_PIR) == HIGH;
}

void setup() {
  pinMode(PIN_PIR, INPUT);
  Serial.begin(115200);
  // No Serial.waitForUSB() on AVR; the FTDI link is just there.
  delay(50);

  Serial.println(F("{\"event\":\"boot\",\"device\":\"roomlens-promini\"}"));
}

void loop() {
  static uint32_t lastFrameMs = 0;
  static float micPeakHold = 0.0f;

  ingestHostSerial();

  const uint32_t now = millis();
  if (now - lastFrameMs < FRAME_MS) {
    return;
  }
  lastFrameMs = now;

  float micPeakInstant = 0.0f;
  const float micRms = readMicRms(MIC_WINDOW_MS, &micPeakInstant);
  micPeakHold = max(micPeakInstant, micPeakHold * MIC_PEAK_DECAY);

  const float luxLevel = readLightLevel();
  const bool pirActive = readPirState();

  // Fade webcam motion toward zero if the host stops sending updates.
  if ((now - g_camMotionMs) > CAM_DECAY_MS) {
    g_camMotion *= 0.8f;
  }

  Serial.print(F("{\"t\":"));
  Serial.print(now);
  Serial.print(F(",\"mic_rms\":"));
  Serial.print(micRms, 3);
  Serial.print(F(",\"mic_peak\":"));
  Serial.print(micPeakHold, 3);
  Serial.print(F(",\"lux\":"));
  Serial.print(luxLevel, 3);
  Serial.print(F(",\"pir\":"));
  Serial.print(pirActive ? 1 : 0);
  Serial.print(F(",\"cam_motion\":"));
  Serial.print(g_camMotion, 3);
  Serial.println(F("}"));
}
