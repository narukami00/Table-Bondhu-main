/*
 * Display Utility
 * TFT Display functions
 */

#ifndef DISPLAY_H
#define DISPLAY_H

#include <TFT_eSPI.h>

extern TFT_eSPI tft;

void displayInit() {
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
}

void displayMessage(const char* message) {
  tft.fillScreen(TFT_BLACK);
  tft.setCursor(0, 0);
  tft.println(message);
}

void displayProgress(const char* status) {
  tft.fillScreen(TFT_BLACK);
  tft.setCursor(0, 0);
  tft.setTextSize(1);
  tft.println(status);
  tft.setTextSize(2);
}

#endif // DISPLAY_H
