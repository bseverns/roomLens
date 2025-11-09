/**
 * SerialWebcamBridge — Processing sketch
 * --------------------------------------
 *
 * Watches a webcam, estimates frame-to-frame motion, and sends a normalized
 * motion value to the Room Lens Pro Mini firmware over serial. The firmware
 * expects lines that look like `cam:0.42`. Adjust the serial port index below
 * to match your FTDI adapter.
 */

import processing.video.*;
import processing.serial.*;

Capture cam;
Serial  port;

// Configuration --------------------------------------------------------------
float smoothing = 0.2;  // how quickly the motion responds (0..1)
float gain      = 0.025; // scale the raw diff sum into 0..1 motion
int   serialIndex = 0;   // pick the FTDI device from Serial.list()

// State ----------------------------------------------------------------------
PImage lastFrame;
float  motionValue = 0;

void setup() {
  size(640, 360);

  String[] cameras = Capture.list();
  if (cameras.length == 0) {
    println("No cameras found. Plug one in and restart.");
    exit();
  }
  println("Using camera: " + cameras[0]);
  cam = new Capture(this, cameras[0]);
  cam.start();

  println("Available serial ports:");
  printArray(Serial.list());
  port = new Serial(this, Serial.list()[serialIndex], 115200);
  port.clear();
}

void draw() {
  background(10);
  if (cam.available()) {
    cam.read();
  }
  image(cam, 0, 0, width, height);

  if (lastFrame == null) {
    lastFrame = createImage(cam.width, cam.height, RGB);
    lastFrame.copy(cam, 0, 0, cam.width, cam.height, 0, 0, cam.width, cam.height);
    lastFrame.updatePixels();
    return;
  }

  cam.loadPixels();
  lastFrame.loadPixels();

  float diffSum = 0;
  for (int i = 0; i < cam.pixels.length; i += 4) {
    color current = cam.pixels[i];
    color previous = lastFrame.pixels[i];
    float diff = abs(brightness(current) - brightness(previous));
    diffSum += diff;
  }

  lastFrame.copy(cam, 0, 0, cam.width, cam.height, 0, 0, cam.width, cam.height);
  lastFrame.updatePixels();

  float motion = constrain(diffSum * gain, 0, 1);
  motionValue = lerp(motionValue, motion, smoothing);

  noStroke();
  fill(255, 40, 120, 180);
  rect(0, height - 40, width * motionValue, 40);
  fill(255);
  textAlign(LEFT, CENTER);
  text("motion: " + nf(motionValue, 0, 3), 12, height - 20);

  if (frameCount % 2 == 0) { // keep serial traffic chill
    port.write("cam:" + nf(motionValue, 0, 3) + "\n");
  }
}
