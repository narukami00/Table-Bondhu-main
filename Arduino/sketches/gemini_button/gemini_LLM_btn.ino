/*
 * Gemini Button Sketch
 * Press button to record and get AI response
 * 
 * Place original gemini_LLM_btn.ino content here
 */

#include <WiFi.h>
#include <TFT_eSPI.h>
#include "../config.h"
#include "../utils/i2s_setup.h"
#include "../utils/display.h"
#include "../utils/wifi.h"

#define BUTTON_PIN 14

TFT_eSPI tft = TFT_eSPI();
WiFiClient client;
bool isRecording = false;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  displayInit();
  displayMessage("Connecting WiFi...");
  
  connectWiFi();
  setupI2S();
  
  displayMessage("Ready. Press BOOT");
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
  
  // Handle button press
  if (digitalRead(BUTTON_PIN) == LOW) {
    isRecording = !isRecording;
    delay(200); // Debounce
  }
}
