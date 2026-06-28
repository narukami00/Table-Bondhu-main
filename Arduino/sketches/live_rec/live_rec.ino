/*
 * Live Recording Sketch
 * Real-time audio streaming to Python server
 * 
 * Place original live_rec.ino content here
 */

#include <WiFi.h>
#include <TFT_eSPI.h>
#include "../config.h"
#include "../utils/i2s_setup.h"
#include "../utils/display.h"
#include "../utils/wifi.h"

TFT_eSPI tft = TFT_eSPI();
WiFiClient client;

void setup() {
  Serial.begin(115200);
  displayInit();
  displayMessage("Connecting WiFi...");
  
  connectWiFi();
  setupI2S();
  
  displayMessage("Live Streaming Ready");
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
  
  // Stream audio here
}
