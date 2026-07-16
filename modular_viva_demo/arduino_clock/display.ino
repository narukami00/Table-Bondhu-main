/*
 * display.ino - Handles tft eSPI double buffering, wipes, theme updates, and state rendering
 */

unsigned long speakingStartMs = 0;
unsigned long speakingDuration = 0;
unsigned long buzzerStartMs = 0;
bool buzzerActive = false;
int textPage = 0;
int bubbleLineCount = 0;
String lastBubbleText = "";
String currentResponseText = "";
unsigned long lastClockUpdateMs = 0;
unsigned long nextCameoTriggerMs = 0;

void dissolveWipe(uint16_t targetColor) {
  // Renders screen transition wipe using pseudo-random blocks
  int blockW = 8;
  int blockH = 8;
  int cols = 128 / blockW;
  int rows = 160 / blockH;
  int numBlocks = cols * rows;
  
  int order[numBlocks];
  for (int i = 0; i < numBlocks; i++) order[i] = i;
  for (int i = numBlocks - 1; i > 0; i--) {
    int r = random(i + 1);
    int temp = order[i];
    order[i] = order[r];
    order[r] = temp;
  }

  for (int i = 0; i < numBlocks; i++) {
    int col = order[i] % cols;
    int row = order[i] / cols;
    tft.fillRect(col * blockW, row * blockH, blockW, blockH, targetColor);
    if (i % 25 == 0) delay(1); // control speed of dissolve wipe
  }
}

void setAppState(AppState newState) {
  AppState oldState = currentState;
  currentState = newState;
  needRedraw = true;
  
  if (oldState == STATE_ALARM || oldState == STATE_TIMER_FINISHED) {
    ledcWriteTone(0, 0); // silent buzzer
  }

  dissolveWipe(COLOR_BG);
  Serial.printf("[State System] Transitioned: State %d -> State %d\n", oldState, newState);
}

void updateAnimations() {
  unsigned long now = millis();
  
  // Custom double buffering logic:
  // Render face sprites inside the faceSprite RAM block, then push to the physical screen
  faceSprite.fillSprite(COLOR_BG);

  if (currentState == STATE_CLOCK) {
    // Clock face mode: draw sleeping or idle pikachu avatar
    pushThemedImage(faceSprite, 0, 0, 128, 110, CURRENT_IDLE);
    faceSprite.pushSprite(0, 0);
  }
  else if (currentState == STATE_LISTENING) {
    // Pulse mic recording status
    pushThemedImage(faceSprite, 0, 0, 128, 110, pika_talk);
    faceSprite.pushSprite(0, 0);
  }
  else if (currentState == STATE_THINKING) {
    // Draw peaking loading sprites
    pushThemedImage(faceSprite, 0, 0, 128, 110, pika_wink);
    faceSprite.pushSprite(0, 0);
  }
  else if (currentState == STATE_SPEAKING) {
    // Speaking animations
    bool openMouth = ((now / 150) % 2 == 0);
    pushThemedImage(faceSprite, 0, 0, 128, 110, openMouth ? pika_talk : pika_idle);
    faceSprite.pushSprite(0, 0);
  }
  else if (currentState == STATE_ALARM) {
    // Alarm screen blinking colors
    bool alarmFlash = ((now / 200) % 2 == 0);
    faceSprite.fillSprite(alarmFlash ? TFT_RED : COLOR_BG);
    pushThemedImage(faceSprite, 0, 0, 128, 110, pika_shock);
    faceSprite.pushSprite(0, 0);
  }
}

void drawClockFace() {
  tft.fillRect(0, 110, 128, 50, COLOR_BG);
  tft.setTextSize(2);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);

  // Print NTP synced local time
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    char timeStr[10];
    strftime(timeStr, sizeof(timeStr), "%I:%M", &timeinfo);
    tft.setCursor(30, 120);
    tft.println(timeStr);
  } else {
    tft.setCursor(30, 120);
    tft.println("12:00");
  }

  // Draw Open-Meteo Weather Icons
  if (hasWeather) {
    tft.setTextSize(1);
    tft.setTextColor(COLOR_ACCENT, COLOR_BG);
    tft.setCursor(10, 142);
    tft.printf("%dC %s", weatherTemp, weatherDesc.c_str());
  }
}

void renderDisplay() {
  unsigned long now = millis();

  if (currentState == STATE_CLOCK) {
    if (now - lastClockUpdateMs > 1000) {
      drawClockFace();
      lastClockUpdateMs = now;
    }
  }
  else if (currentState == STATE_SPEAKING) {
    // Auto timeout speaking state
    if (now - speakingStartMs >= speakingDuration) {
      setAppState(STATE_CLOCK);
    }
  }
}
