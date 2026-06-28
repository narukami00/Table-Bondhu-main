/*
 * Save Recording Sketch
 * Record audio and save locally before sending
 * 
 * Place original save_arduino.ino content here
 */

#include <WiFi.h>
#include <TFT_eSPI.h>
#include "../config.h"
#include "../utils/i2s_setup.h"
#include "../utils/display.h"
#include "../utils/wifi.h"

#define BUTTON_PIN 0

TFT_eSPI tft = TFT_eSPI();
WiFiClient client;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  displayInit();
  displayMessage("Connecting WiFi...");
  
  connectWiFi();
  setupI2S();
  
  displayMessage("Hold BOOT to talk");
}

void loop() {
  if (!client.connected()) {
    if (!client.connect(SERVER_IP, SERVER_PORT)) {
      displayProgress("Connecting...");
      delay(2000);
      return;
    }
    client.setNoDelay(true);
  }
  
  // Record when button pressed
}
