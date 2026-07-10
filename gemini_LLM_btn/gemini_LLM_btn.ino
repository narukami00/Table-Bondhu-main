 
#include <WiFi.h>
#include <TFT_eSPI.h>
#include <driver/i2s.h>
#include <time.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "config.h"

#define BUTTON_PIN 14 // Tactile Button (GND + D14)
#define BOOT_BTN 0    // Built-in BOOT button for text pagination
#define LDR_PIN 34   // ADC1_CH6 - Light Dependent Resistor
#define BUZZER_PIN 13 // Active Buzzer (HIGH = sound)
#define PIR_PIN 27    // PIR Motion Sensor (digital OUT)
#define I2S_SAMPLE_RATE 16000

// Theme selection macros (required by images.h conditional compilation)
#define THEME_GIRL 0
#define THEME_PIKACHU 1
#define ACTIVE_THEME THEME_PIKACHU

// Default colors (Pikachu theme is the default and only active theme)
#define DEFAULT_BG 0x18E6
#define DEFAULT_ACCENT 0xFEE0
#define DEFAULT_BORDER 0xFEE0
#define DEFAULT_BUBBLE_BG TFT_BLACK
#define DEFAULT_TEXT TFT_WHITE
#define DEFAULT_STATUS TFT_RED
#define ASSET_BG 0x18E6

#include "images.h"

// Runtime color variables (changed by theme switching)
uint16_t COLOR_BG = DEFAULT_BG;
uint16_t COLOR_ACCENT = DEFAULT_ACCENT;
uint16_t COLOR_BORDER = DEFAULT_BORDER;
uint16_t COLOR_BUBBLE_BG = DEFAULT_BUBBLE_BG;
uint16_t COLOR_TEXT = DEFAULT_TEXT;
uint16_t COLOR_STATUS = DEFAULT_STATUS;

// Adaptive theme: 4-level LDR-based palettes
struct ThemePalette {
  uint16_t bg, accent, border, bubbleBg, text, status;
};

const ThemePalette THEMES[4] = {
  { 0x0000, 0xFFE0, 0xFFE0, 0x0000, 0xFFFF, 0xFFE0 },  // Night: black bg, yellow accent
  { 0x000F, 0x867D, 0x867D, 0x000A, 0xFFFF, 0x867D },  // Dusk: navy bg, light blue accent
  { 0xFD00, 0x3800, 0x3800, 0xFFFF, 0x0000, 0x3800 },  // Autumn: orange bg, dark red-brown accent
  { 0xFFFF, 0x001F, 0x001F, 0xFFFF, 0x001F, 0x001F }   // Bright: white bg, dark blue text
};

#define THEME_COOLDOWN_MS 5000
#define THEME_CLOCK_MIN_MS 2000

int activeTheme = 3;  // Start at Bright
unsigned long lastSwitchMs = 0;
unsigned long lastThemeLdrMs = 0;
int cachedLdr = 2048;

// Weather variables
int weatherTemp = 25;
String weatherDesc = "SUNNY";
int weatherIconIdx = 0;
bool hasWeather = false;

// Timer / Countdown variables
int timerSecondsLeft = 0;
unsigned long lastTimerTickMs = 0;
unsigned long buttonPressStartMs = 0;
bool buttonHeldProcessed = false;
unsigned long lastServerConnectAttemptMs = 0;

// PIR Motion Sensor variables
unsigned long lastPirMotionMs = 0;          // Last time PIR detected motion
const unsigned long SLEEP_TIMEOUT_MS = 30000; // 30 seconds → sleeping mode

// Sleep / Wake pre-wake flow variables (added for robust sleep monitoring)
unsigned long clockStateEnteredMs = 0;      // Time when STATE_CLOCK was entered continuously
unsigned long preWakeEnteredMs = 0;         // Time when STATE_SLEEPING_PREWAKE was entered
unsigned long lastSleepHeartbeatMs = 0;     // Last time sleep heartbeat keep-alive command was sent
int preWakeRisingEdges = 0;                 // Count PIR LOW->HIGH transitions during pre-wake
unsigned long lastSleepEnteredMs = 0;       // Time when STATE_SLEEPING was entered

// Sleep animation flare variables (added for sleep animation and clock updates)
int sleepAnimState = 0;                     // 0 = normal sleep loop, 3 = smiling
unsigned long lastSleepAnimUpdateMs = 0;    // Last time sleep animation frame changed
bool sleepFrameToggle = false;              // Toggles between sleep_1 and sleep_2
unsigned long sleepSmileStartMs = 0;        // Time when the sleeping smile started
unsigned long nextSleepSmileTriggerMs = 0;  // Next time the smile will trigger
unsigned long lastSleepClockUpdateMs = 0;   // Last time sleep clock was drawn

// Sleep Summary variables
String sleepSummaryType = "Sleep";      // "Sleep" or "Nap"
float sleepSummaryDuration = 0.0f;     // duration in hours
int sleepSummaryMovements = 0;         // movement count
float sleepSummaryAvgNoise = 0.0f;     // average noise
int sleepSummaryAvgLdr = 0;            // average light level
String sleepSummaryQuality = "Good";   // "Good", "Fair", "Poor"
unsigned long sleepSummaryStartMs = 0; // time when summary screen was displayed

// Redraw control
bool needRedraw = true;

// Forward declarations
void dissolveWipe(uint16_t targetColor);

// TFT and sprites — must be before any function that uses them
TFT_eSPI tft = TFT_eSPI();
TFT_eSprite faceSprite = TFT_eSprite(&tft);
TFT_eSprite cameoSprite = TFT_eSprite(&tft);
WiFiClient client;

enum AppState {
  STATE_CLOCK,
  STATE_CAMEO,
  STATE_WAVING_INTRO,
  STATE_IDLE,
  STATE_LISTENING,
  STATE_THINKING,
  STATE_SPEAKING,
  STATE_WAVING_OUTRO,
  STATE_ALARM,
  STATE_REMINDERS,
  STATE_TIMER,
  STATE_TIMER_PAUSED,
  STATE_TIMER_FINISHED,
  STATE_SLEEPING,
  STATE_SLEEPING_PREWAKE,
  STATE_SLEEP_SUMMARY
};

int ldrToTheme(int ldr) {
  if (ldr < 300) return 0;       // Night
  if (ldr < 700) return 1;       // Dusk
  if (ldr < 1200) return 2;      // Autumn
  return 3;                       // Bright
}

void switchTheme(int idx) {
  activeTheme = idx;
  COLOR_BG = THEMES[idx].bg;
  COLOR_ACCENT = THEMES[idx].accent;
  COLOR_BORDER = THEMES[idx].border;
  COLOR_BUBBLE_BG = THEMES[idx].bubbleBg;
  COLOR_TEXT = THEMES[idx].text;
  COLOR_STATUS = THEMES[idx].status;
  dissolveWipe(COLOR_BG);
  needRedraw = true;
  Serial.printf("[THEME] Switched to theme %d (LDR=%d)\n", idx, cachedLdr);
}

// Buffer for pushThemedImage (sprite background replacement) — heap-allocated in setup()
static uint16_t *themedBuf = NULL;

void pushThemedImage(TFT_eSprite &spr, int x, int y, int w, int h, const uint16_t *data) {
  if (!themedBuf) return;  // safety: not yet allocated
  int total = w * h;
  memcpy(themedBuf, data, total * sizeof(uint16_t));
  for (int i = 0; i < total; i++) {
    if (themedBuf[i] == ASSET_BG) themedBuf[i] = COLOR_BG;
  }
  spr.pushImage(x, y, w, h, themedBuf);
}

// Sprite frame macros (reference images.h arrays, independent of runtime colors)
#define CURRENT_IDLE pika_idle
#define CURRENT_HALF_BLINK pika_half_blink
#define CURRENT_SMILE_BLINK pika_smile_blink
#define CURRENT_TALK_20 pika_talk_20
#define CURRENT_TALK_60 pika_talk_60
#define CURRENT_TALK_100 pika_talk_100
#define CURRENT_TALK_BLINK pika_talk_blink
#define CURRENT_SMILE pika_smile
#define CAMEO_FRAME_COUNT 7

// Sleep animation frame macros
#define CURRENT_SLEEP_1 pika_sleep_1
#define CURRENT_SLEEP_2 pika_sleep_2
#define CURRENT_SLEEP_SMILE pika_sleep_smile
#define CURRENT_SLEEP_PARTIAL pika_sleep_partial
#define CURRENT_SLEEP_NEUTRAL_1 pika_sleep_neutral_1
#define CURRENT_SLEEP_NEUTRAL_2 pika_sleep_neutral_2

bool isRecording = false;
bool alarmFlashState = false;

// Buzzer state
bool buzzerActive = false;
unsigned long buzzerStartMs = 0;

// Audio Filter Variables
float dc_filter_y = 0;
float dc_filter_x = 0;

AppState currentState = STATE_CLOCK;

// Animation and Timing Variables
unsigned long lastAnimationUpdateMs = 0;
unsigned long lastBlinkMs = 0;
unsigned long nextBlinkIntervalMs = 4000;
unsigned long speakingStartMs = 0;
unsigned long speakingDuration = 5000;
unsigned long stateTimerMs = 0;
unsigned long lastShakeMs = 0;
unsigned long lastClockUpdateMs = 0;
unsigned long nextCameoTriggerMs = 30000; // Trigger first cameo in 30s
unsigned long lastLdrReadMs = 0;
const unsigned long LDR_READ_INTERVAL_MS = 5000; // Read LDR every 5 seconds

// NTP sync state
bool ntpSynced = false;
unsigned long lastNtpRetryMs = 0;
const unsigned long NTP_RETRY_INTERVAL_MS = 30000;

String currentResponseText = "";
String lastBubbleText = "";  // Anti-flicker: only redraw when text changes
unsigned long serverDuration = 0;  // Server-provided audio duration override
int textPage = 0;           // Current page of text being displayed
int textTotalPages = 0;     // Total pages for current text
bool lastBootBtnState = false; // Edge detection for BOOT button
bool lastButtonState = false;  // Edge detection for main button
int mouthFrame = 0;
int blinkFrame = 0;
bool isBlinking = false;
unsigned long blinkStateStartMs = 0;

// Shake offsets
int shakeX = 0;
int shakeY = 0;

// Cameo animation variables
int cameoFrame = 0;
unsigned long cameoFrameStartMs = 0;

// Waving animation variables
int waveFrame = 0;
unsigned long waveFrameStartMs = 0;
int waveCycleCount = 0;

// Text pagination globals (must be before updateAnimations)
#define BUBBLE_LINES_MAX 20
#define BUBBLE_LINES_PER_PAGE 5
String bubbleLines[BUBBLE_LINES_MAX];
int bubbleLineCount = 0;
bool greetingMode = false;  // True when wave was triggered by greeting (skip LISTENING on finish)

// Timezone offset (Bangladesh Standard Time GMT+6 = 6 * 3600 seconds)
const long gmtOffset_sec = 6 * 3600;
const int daylightOffset_sec = 0;

void drawClockFace();
void drawSleepClockOverlay(TFT_eSprite &spr);
void drawIdleOverlay();
void drawListeningOverlay();
void drawThinkingOverlay();
void drawBubbleText(String text);
void drawCameoFrame();
void drawWaveFrame();
void dissolveWipe(uint16_t targetColor);
void drawRemindersPage();
void drawTimerPage();
void drawSleepSummaryPage();

void setupI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_ADC_BUILT_IN),
    .sample_rate = I2S_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_LSB,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 16,     
    .dma_buf_len = 1024,     
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_adc_mode(ADC_UNIT_1, ADC1_CHANNEL_4); // GPIO 32
  i2s_adc_enable(I2S_NUM_0);
}

void setAppState(AppState newState) {
  if (currentState != newState) {
    AppState oldState = currentState;
    currentState = newState;
    stateTimerMs = millis();
    needRedraw = true;
    
    // Stop buzzer when leaving alarm or timer finished state
    if (oldState == STATE_ALARM || oldState == STATE_TIMER_FINISHED) {
      ledcWriteTone(0, 0);
      buzzerActive = false;
      alarmFlashState = false;
    }

    
    // Shrink sprite and play waking transition when leaving sleep states
    if (oldState == STATE_SLEEPING || oldState == STATE_SLEEPING_PREWAKE) {
      tft.fillScreen(COLOR_BG); // Clear full screen to wipe sleep border/layout
      
      // Draw waking transition on the full 128x160 canvas
      faceSprite.fillSprite(COLOR_BG);
      pushThemedImage(faceSprite, 0, 0, 128, 160, CURRENT_SLEEP_NEUTRAL_1);
      faceSprite.pushSprite(0, 0);
      delay(400);
      
      faceSprite.fillSprite(COLOR_BG);
      pushThemedImage(faceSprite, 0, 0, 128, 160, CURRENT_SLEEP_NEUTRAL_2);
      faceSprite.pushSprite(0, 0);
      delay(400);

      // Now shrink sprite back to 128x110 for normal clocks and speech bubbles
      faceSprite.deleteSprite();
      faceSprite.createSprite(128, 110);
    }
    
    // Dissolve only on button press (Clock → Waving Intro) — skip for greeting and routine transitions
    if (oldState == STATE_CLOCK && currentState == STATE_WAVING_INTRO && !greetingMode) {
      dissolveWipe(COLOR_BG);
    }
    
    // Clear screen depending on target state and handle sleep/wake tracking
    if (currentState == STATE_CLOCK) {
      tft.fillScreen(COLOR_BG);
      drawClockFace();
      lastPirMotionMs = millis();
      clockStateEnteredMs = millis(); // Track when we entered the active clock state
      nextCameoTriggerMs = millis() + random(300000, 600000); // Cooldown of 5-10 mins to prevent instant peaking on wake
      
      // If waking up from sleep, notify the server
      if (oldState == STATE_SLEEPING || oldState == STATE_SLEEPING_PREWAKE) {
        if (client.connected()) {
          client.print("PIR:WAKE\n");
        }
        Serial.println("PIR: Woke up fully. Notification sent to server.");
      }
    } else if (currentState == STATE_SLEEPING) {
      // Falling asleep transition: normal ear -> drooped ear
      if (oldState == STATE_CLOCK) {
        faceSprite.fillSprite(COLOR_BG);
        pushThemedImage(faceSprite, 0, 0, 128, 128, CURRENT_SLEEP_NEUTRAL_2);
        faceSprite.pushSprite(0, 0);
        delay(500);
        
        faceSprite.fillSprite(COLOR_BG);
        pushThemedImage(faceSprite, 0, 0, 128, 128, CURRENT_SLEEP_NEUTRAL_1);
        faceSprite.pushSprite(0, 0);
        delay(500);
      }
      
      // Enlarge faceSprite to full screen (128x160) for sleeping
      faceSprite.deleteSprite();
      faceSprite.createSprite(128, 160);
      
      tft.fillScreen(COLOR_BG);
      // Custom HUD Border Outline for sleeping screen
      tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
      tft.drawRect(4, 4, 120, 152, COLOR_BG);
      
      // Initialize sleep animation state variables
      sleepAnimState = 0; // normal loop
      lastSleepAnimUpdateMs = millis();
      sleepFrameToggle = false;
      nextSleepSmileTriggerMs = millis() + random(15000, 30000); // 15-30s first trigger
      lastSleepClockUpdateMs = 0; // force clock draw instantly
      
      // Notify server we went to sleep and start keep-alive heartbeat timer
      if (client.connected()) {
        client.print("PIR:SLEEP\n");
      }
      lastSleepHeartbeatMs = millis();
      lastSleepEnteredMs = millis(); // Track when we entered sleep for motion cooldown
      Serial.println("PIR: Went to sleep. Notification sent to server.");
    } else if (currentState == STATE_SLEEPING_PREWAKE) {
      preWakeEnteredMs = millis();
      preWakeRisingEdges = 1; // The motion triggering pre-wake counts as the first wave
      lastSleepClockUpdateMs = 0; // force sleep clock redraw
      
      // Notify server we entered pre-wake standby
      if (client.connected()) {
        client.print("PIR:PREWAKE\n");
      }
      Serial.println("PIR: Entered pre-wake standby. Notification sent to server.");
      // Do not clear the screen, keep it black/themed with the existing sleeping HUD outline
    } else if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED || currentState == STATE_REMINDERS) {
      // Full-screen states need a complete clear
      tft.fillScreen(COLOR_BG);
    } else {
      tft.fillRect(0, 110, 128, 50, COLOR_BG);
    }
    
    // Setup state counters
    if (currentState == STATE_CAMEO) {
      cameoFrame = 1;
      cameoFrameStartMs = millis();
      drawCameoFrame();
    } else if (currentState == STATE_WAVING_INTRO || currentState == STATE_WAVING_OUTRO) {
      shakeX = 0;
      shakeY = 0;
      waveFrame = 0;
      waveFrameStartMs = millis();
      waveCycleCount = 0;
      drawWaveFrame();
    } else if (currentState == STATE_IDLE) {
        drawIdleOverlay();  
    } else if (currentState == STATE_LISTENING) {
      drawListeningOverlay();
    } else if (currentState == STATE_THINKING) {
      drawThinkingOverlay();
    } else if (currentState == STATE_SPEAKING) {
      lastBubbleText = "";  // Force bubble redraw on new text
      drawBubbleText(currentResponseText);
    } else if (currentState == STATE_ALARM) {
      lastBubbleText = "";  // Force bubble redraw on new text
      drawBubbleText(currentResponseText);
    } else if (currentState == STATE_REMINDERS) {
      bubbleLineCount = 0;  // Force re-pagination
      textPage = 0;
      drawRemindersPage();
    } else if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED) {
      drawTimerPage();
    } else if (currentState == STATE_TIMER_FINISHED) {
      shakeX = 0;
      shakeY = 0;
      waveFrame = 0;
      waveFrameStartMs = millis();
      needRedraw = true;
    }
  }
}

void drawAvatar() {
  const uint16_t* frameData = CURRENT_IDLE;
  
  if (currentState == STATE_SLEEPING) {
    if (sleepAnimState == 3) {
      frameData = CURRENT_SLEEP_SMILE;
    } else {
      frameData = sleepFrameToggle ? CURRENT_SLEEP_2 : CURRENT_SLEEP_1;
    }
  } else if (currentState == STATE_SLEEPING_PREWAKE) {
    frameData = CURRENT_SLEEP_PARTIAL;
  } else if (currentState == STATE_TIMER_FINISHED) {
    frameData = (waveFrame % 2 == 0) ? pika_wave_1 : pika_wave_2; // Waving high
  } else if (currentState == STATE_SPEAKING || currentState == STATE_ALARM) {
    if (currentState == STATE_ALARM) {
      frameData = CURRENT_TALK_100; // Wide open mouth for alarm shocked face
    } else if (isBlinking) {
      frameData = CURRENT_TALK_BLINK;
    } else {
      if (mouthFrame == 0) frameData = CURRENT_IDLE;
      else if (mouthFrame == 1) frameData = CURRENT_TALK_20;
      else if (mouthFrame == 2) frameData = CURRENT_TALK_60;
      else if (mouthFrame == 3) frameData = CURRENT_TALK_100;
      else if (mouthFrame == 4) frameData = CURRENT_TALK_60;
      else if (mouthFrame == 5) frameData = CURRENT_TALK_20;
    }
  } else {
    if (isBlinking) {
      if (blinkFrame == 1 || blinkFrame == 3) {
        frameData = CURRENT_HALF_BLINK;
      } else if (blinkFrame == 2) {
        frameData = CURRENT_SMILE_BLINK;
      }
    } else {
      frameData = (currentState == STATE_LISTENING) ? CURRENT_SMILE : CURRENT_IDLE;
    }
  }

  // Draw avatar to sprite and push with flashing background if in Alarm state
  uint16_t bgCol = ((currentState == STATE_ALARM || currentState == STATE_TIMER_FINISHED) && alarmFlashState) ? TFT_RED : COLOR_BG;
  faceSprite.fillSprite(bgCol);
  if (currentState == STATE_SLEEPING || currentState == STATE_SLEEPING_PREWAKE) {
    pushThemedImage(faceSprite, 0, 0, 128, 160, frameData);
    drawSleepClockOverlay(faceSprite);
  } else {
    pushThemedImage(faceSprite, 0, 0, 128, 128, frameData);
  }
  faceSprite.pushSprite(shakeX, shakeY);
}

void drawCameoFrame() {
  const uint16_t* frameData = NULL;
  int w = 128;
  int h = 0;
  int yPos = 0;

  // Cameo frames for Pikachu: peek 1->2->3->4->3->2->1 (frame indices 1 to 7)
  if (cameoFrame == 1 || cameoFrame == 7) {
    frameData = pika_cameo_1;
    h = 46;
    yPos = 114;
  } else if (cameoFrame == 2 || cameoFrame == 6) {
    frameData = pika_cameo_2;
    h = 82;
    yPos = 78;
  } else if (cameoFrame == 3 || cameoFrame == 5) {
    frameData = pika_cameo_3;
    h = 124;
    yPos = 36;
  } else if (cameoFrame == 4) {
    frameData = pika_cameo_4;
    h = 128;
    yPos = 32;
  }

  if (frameData != NULL) {
    // Clear the vertical region occupied by the cameo
    tft.fillRect(0, 32, 128, 128, COLOR_BG);
    
    cameoSprite.createSprite(w, h);
    cameoSprite.setSwapBytes(true);
    cameoSprite.fillSprite(COLOR_BG);
    pushThemedImage(cameoSprite, 0, 0, w, h, frameData);
    cameoSprite.pushSprite(0, yPos);
    cameoSprite.deleteSprite();
  }
}

void drawWaveFrame() {
  const uint16_t* frameData = NULL;
  // wave 1->2->3->2->3->1 (indices 0 to 5)
  if (waveFrame == 0 || waveFrame == 5) frameData = pika_wave_1;
  else if (waveFrame == 1 || waveFrame == 3) frameData = pika_wave_2;
  else frameData = pika_wave_3;

  if (frameData != NULL) {
    faceSprite.fillSprite(COLOR_BG);
    pushThemedImage(faceSprite, 0, 0, 128, 128, frameData);
    faceSprite.pushSprite(shakeX, shakeY);
  }
}

void dissolveWipe(uint16_t targetColor) {
  int blockSize = 16;
  for (int step = 0; step < 8; step++) {
    for (int x = 0; x < 128; x += blockSize) {
      for (int y = 0; y < 160; y += blockSize) {
        if (random(8) <= step) {
          tft.fillRect(x, y, blockSize, blockSize, targetColor);
        }
      }
    }
    delay(15);
  }
  tft.fillScreen(targetColor);
}

void drawClockFace() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 100)) {
    // Retry NTP periodically only if WiFi is actually connected
    if (WiFi.status() == WL_CONNECTED) {
      unsigned long now = millis();
      if (now - lastNtpRetryMs > NTP_RETRY_INTERVAL_MS) {
        configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.google.com", "time.nist.gov");
        lastNtpRetryMs = now;
        Serial.println("[NTP] Retrying time sync...");
      }
    }

    // Custom HUD Border Outline
    tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
    tft.drawRect(4, 4, 120, 152, COLOR_BG);

    tft.setTextColor(COLOR_ACCENT, COLOR_BG);
    tft.setTextSize(1);
    if (WiFi.status() != WL_CONNECTED) {
      tft.setCursor(16, 55);
      tft.println("Offline Mode");
    } else {
      tft.setCursor(24, 55);
      tft.println("Syncing Time...");
    }

    tft.drawRoundRect(10, 115, 108, 30, 4, COLOR_BORDER);
    tft.setTextColor(COLOR_STATUS, COLOR_BG);
    tft.setTextSize(1);
    if (WiFi.status() != WL_CONNECTED || !client.connected()) {
      tft.setCursor(28, 126);
      tft.println("DISCONNECTED");
    } else {
      tft.setCursor(28, 126);
      tft.println("SYSTEM READY");
    }
    return;
  }
  
  ntpSynced = true;
  
  // Custom HUD Border Outline
  tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
  tft.drawRect(4, 4, 120, 152, COLOR_BG);
  
  if (hasWeather) {
    if (weatherIconIdx == 0) {
      tft.fillCircle(24, 14, 4, TFT_YELLOW);
    } else if (weatherIconIdx == 1) {
      tft.fillCircle(22, 16, 3, COLOR_BORDER);
      tft.fillCircle(26, 14, 4, COLOR_BORDER);
    } else if (weatherIconIdx == 2) {
      tft.fillCircle(22, 14, 3, COLOR_BORDER);
      tft.fillCircle(26, 12, 4, COLOR_BORDER);
      tft.drawLine(22, 18, 20, 21, COLOR_ACCENT);
      tft.drawLine(26, 18, 24, 21, COLOR_ACCENT);
    } else if (weatherIconIdx == 3) {
      tft.fillCircle(22, 14, 3, COLOR_BORDER);
      tft.fillCircle(26, 12, 4, COLOR_BORDER);
      tft.drawPixel(22, 19, COLOR_ACCENT);
      tft.drawPixel(26, 19, COLOR_ACCENT);
    }
    tft.setTextColor(COLOR_ACCENT, COLOR_BG);
    tft.setTextSize(1);
    tft.setCursor(38, 11);
    tft.printf("%dC %s", weatherTemp, weatherDesc.c_str());
  } else {
    // Fallback text when offline
    tft.setTextColor(COLOR_ACCENT, COLOR_BG);
    tft.setTextSize(1);
    tft.setCursor(16, 11);
    tft.print("HAVE A GOOD DAY!");
  }
  
  // Clear "Syncing Time..." area from previous failed NTP attempt
  tft.fillRect(4, 20, 120, 20, COLOR_BG);
  
  tft.drawLine(2, 20, 8, 20, COLOR_BORDER);
  tft.drawLine(120, 20, 126, 20, COLOR_BORDER);
  tft.drawLine(2, 140, 8, 140, COLOR_BORDER);
  tft.drawLine(120, 140, 126, 140, COLOR_BORDER);
  
  char dateStr[32];
  strftime(dateStr, sizeof(dateStr), "%a %d %b", &timeinfo);
  for (int i = 0; dateStr[i]; i++) dateStr[i] = toupper(dateStr[i]);
  
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.setTextSize(1);
  int dateWidth = strlen(dateStr) * 6;
  tft.setCursor((128 - dateWidth) / 2, 40);
  tft.println(dateStr);
  
  char timeStr[16];
  strftime(timeStr, sizeof(timeStr), "%I:%M", &timeinfo);
  const char* ampm = (timeinfo.tm_hour >= 12) ? "PM" : "AM";
  
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.setTextSize(3);
  int timeWidth = strlen(timeStr) * 18;
  tft.setCursor((128 - timeWidth) / 2, 55);
  tft.print(timeStr);
  
  // AM/PM below the time
  tft.setTextSize(1);
  int ampmWidth = strlen(ampm) * 6;
  tft.setCursor((128 - ampmWidth) / 2, 85);
  tft.print(ampm);
  
  tft.drawRoundRect(10, 115, 108, 30, 4, COLOR_BORDER);
  tft.setTextColor(COLOR_STATUS, COLOR_BG);
  tft.setTextSize(1);
  if (WiFi.status() != WL_CONNECTED || !client.connected()) {
    tft.setCursor(28, 126);
    tft.println("DISCONNECTED");
  } else {
    tft.setCursor(28, 126);
    tft.println("SYSTEM READY");
  }
}

void drawSleepClockOverlay(TFT_eSprite &spr) {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo, 100)) {
    char timeStr[16];
    strftime(timeStr, sizeof(timeStr), "%I:%M %p", &timeinfo);
    
    int textWidth = strlen(timeStr) * 6; // 6px per character at size 1
    int boxWidth = textWidth + 14;      // Space for padding and status dot
    int boxHeight = 14;
    int x = 124 - boxWidth;              // 4px margin from right edge
    int y = 6;                          // 6px margin from top edge
    
    // Draw high-tech status capsule bubble
    spr.fillRoundRect(x, y, boxWidth, boxHeight, 3, COLOR_BUBBLE_BG);
    spr.drawRoundRect(x, y, boxWidth, boxHeight, 3, COLOR_BORDER);
    
    // Draw a blinking/pulsing heart monitor dot
    uint16_t dotColor = (millis() % 1000 < 500) ? TFT_ORANGE : COLOR_ACCENT;
    spr.fillCircle(x + 6, y + 7, 2, dotColor);
    
    // Print time text
    spr.setTextColor(COLOR_ACCENT, COLOR_BUBBLE_BG);
    spr.setTextSize(1);
    spr.setCursor(x + 12, y + 4);
    spr.print(timeStr);
  }
}

void drawIdleOverlay() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 100)) {
    tft.fillRoundRect(4, 110, 120, 46, 6, COLOR_BUBBLE_BG);
    tft.drawRoundRect(4, 110, 120, 46, 6, COLOR_BORDER);
    tft.fillTriangle(64, 104, 60, 110, 68, 110, COLOR_BORDER);
    tft.fillTriangle(64, 106, 61, 110, 67, 110, COLOR_BUBBLE_BG);
    tft.setTextColor(COLOR_STATUS, COLOR_BUBBLE_BG);
    tft.setTextSize(1);
    tft.setCursor(26, 130);
    tft.print("NO TIME");
    return;
  }
  
  tft.fillRoundRect(4, 110, 120, 46, 6, COLOR_BUBBLE_BG);
  tft.drawRoundRect(4, 110, 120, 46, 6, COLOR_BORDER);
  
  tft.fillTriangle(64, 104, 60, 110, 68, 110, COLOR_BORDER);
  tft.fillTriangle(64, 106, 61, 110, 67, 110, COLOR_BUBBLE_BG);
  
  char timeStr[16];
  strftime(timeStr, sizeof(timeStr), "%I:%M", &timeinfo);
  const char* ampm = (timeinfo.tm_hour >= 12) ? "PM" : "AM";
  char idleTimeStr[20];
  snprintf(idleTimeStr, sizeof(idleTimeStr), "%s %s", timeStr, ampm);
  tft.setTextColor(COLOR_TEXT, COLOR_BUBBLE_BG);
  tft.setTextSize(2);
  int timeWidth = strlen(idleTimeStr) * 12;
  tft.setCursor(4 + (120 - timeWidth) / 2, 116);
  tft.print(idleTimeStr);
  
  tft.setTextColor(COLOR_STATUS, COLOR_BUBBLE_BG);
  tft.setTextSize(1);
  if (WiFi.status() != WL_CONNECTED || !client.connected()) {
    tft.setCursor(28, 138);
    tft.print("DISCONNECTED");
  } else {
    tft.setCursor(28, 138);
    tft.print("SYSTEM READY");
  }
}

void updateAnimations() {
  unsigned long now = millis();
  
  if (currentState == STATE_SLEEPING || currentState == STATE_SLEEPING_PREWAKE) {
    // 1. Redraw when the minute changes to keep the clock overlay updated
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 100)) {
      static int lastMin = -1;
      if (timeinfo.tm_min != lastMin) {
        lastMin = timeinfo.tm_min;
        needRedraw = true;
      }
    }
    
    // 2. Sleeping loop animations (only in main sleeping state)
    if (currentState == STATE_SLEEPING) {
      if (sleepAnimState == 3) {
        // Smiling state: return to normal breathing loop after 3 seconds
        if (now - sleepSmileStartMs > 3000) {
          sleepAnimState = 0;
          needRedraw = true;
        }
      } else {
        // Trigger occasional sleep smile
        if (now > nextSleepSmileTriggerMs) {
          sleepAnimState = 3; // smile
          sleepSmileStartMs = now;
          nextSleepSmileTriggerMs = now + random(20000, 45000); // next smile in 20-45s
          needRedraw = true;
        } 
        // Swap sleep_1 and sleep_2 every 1500ms to simulate breathing
        else if (now - lastSleepAnimUpdateMs > 1500) {
          sleepFrameToggle = !sleepFrameToggle;
          lastSleepAnimUpdateMs = now;
          needRedraw = true;
        }
      }
    }
    
    // Draw the avatar sprite if redraw is triggered
    if (needRedraw) {
      drawAvatar();
      needRedraw = false;
    }
    return;
  }
  
  // 1. CLOCK FACE STATE Updates
  if (currentState == STATE_CLOCK) {
    if (now - lastClockUpdateMs > 1000) {
      drawClockFace();
      lastClockUpdateMs = now;
    }
    
    // LDR-based theme switching (disable I2S ADC temporarily for analogRead)
    if (now - lastThemeLdrMs > 1500) {
      lastThemeLdrMs = now;
      i2s_stop(I2S_NUM_0);
      i2s_adc_disable(I2S_NUM_0);
      cachedLdr = analogRead(LDR_PIN);
      i2s_adc_enable(I2S_NUM_0);
      i2s_start(I2S_NUM_0);
      if (client.connected()) {
        client.print("LDR:" + String(cachedLdr) + "\n");
      }
      
      int detectedTheme = ldrToTheme(cachedLdr);
      if (detectedTheme != activeTheme
          && (now - stateTimerMs > THEME_CLOCK_MIN_MS)
          && (now - lastSwitchMs > THEME_COOLDOWN_MS)) {
        switchTheme(detectedTheme);
        lastSwitchMs = now;
      }
    }
    
    if (now > nextCameoTriggerMs) {
      // Only trigger cameo peaking if we have been continuously in STATE_CLOCK for >= 45 seconds,
      // and only with a 15% probability. This makes the peaking animation a super rare Easter egg.
      if ((now - clockStateEnteredMs >= 45000) && (random(0, 100) < 15)) {
        setAppState(STATE_CAMEO);
      }
      nextCameoTriggerMs = now + random(300000, 600000); // Cooldown of 5 to 10 minutes
    }
    return;
  }
  
  // 2. CAMEO PEAKING Animation
  if (currentState == STATE_CAMEO) {
    unsigned long elapsed = now - cameoFrameStartMs;
    
    if (elapsed > 150) {
      // Pause at full-peek for 1 second
      if (cameoFrame == 4 && elapsed < 1000) return;
      
      cameoFrame++;
      cameoFrameStartMs = now;
      
      if (cameoFrame > CAMEO_FRAME_COUNT) {
        tft.fillRect(0, 32, 128, 128, COLOR_BG);
        setAppState(STATE_CLOCK);
      } else {
        drawCameoFrame();
      }
    }
    return;
  }
  
  // 3. WAVING INTRO / OUTRO Animation
  if (currentState == STATE_WAVING_INTRO || currentState == STATE_WAVING_OUTRO) {
    unsigned long elapsed = now - waveFrameStartMs;
    
    if (elapsed > 300) {
      // Advance wave frame index: 0->1->2->3->4->5 (wave cycle mapping)
      waveFrame = (waveCycleCount + 1) % 6;
      
      waveFrameStartMs = now;
      waveCycleCount++;
      
      if (waveCycleCount >= 6) {
        if (greetingMode) {
          // Greeting wave: go straight back to clock
          greetingMode = false;
          setAppState(STATE_CLOCK);
        } else if (currentState == STATE_WAVING_INTRO) {
          setAppState(STATE_LISTENING);
        } else {
          setAppState(STATE_CLOCK);
        }
      } else {
        drawWaveFrame();
      }
    }
    return;
  }

  // 4. Idle Bottom Clock Update
  if (currentState == STATE_IDLE) {
    if (now - lastClockUpdateMs > 1000) {
      drawIdleOverlay();
      lastClockUpdateMs = now;
    }
  }

  // 5. Shake / Breathing offsets
  if (now - lastShakeMs > 300) {
    if (currentState == STATE_LISTENING || currentState == STATE_THINKING || currentState == STATE_ALARM) {
      needRedraw = true;
      if (currentState == STATE_LISTENING) {
        shakeX = random(-1, 2);
        shakeY = random(-1, 2);
      } else if (currentState == STATE_THINKING) {
        shakeX = random(-1, 2);
        shakeY = random(-1, 2);
      } else if (currentState == STATE_ALARM) {
        shakeX = random(-4, 5);
        shakeY = random(-4, 5);
      }
    } else if (currentState == STATE_IDLE) {
      // Keep idle static to save power and reduce current spikes
      shakeX = 0;
      shakeY = 0;
    }
    lastShakeMs = now;
  }

  // 6. Blink Timer and Frame Sequence
  if (!isBlinking) {
    if (now - lastBlinkMs > nextBlinkIntervalMs) {
      isBlinking = true;
      blinkFrame = 1;
      blinkStateStartMs = now;
      lastBlinkMs = now;
      nextBlinkIntervalMs = random(3000, 7000);
      needRedraw = true;
    }
  } else {
    unsigned long elapsed = now - blinkStateStartMs;
    if (currentState == STATE_SPEAKING) {
      if (elapsed > 120) {
        isBlinking = false;
        needRedraw = true;
      }
    } else {
      if (blinkFrame == 1 && elapsed > 60) {
        blinkFrame = 2;
        blinkStateStartMs = now;
        needRedraw = true;
      } else if (blinkFrame == 2 && elapsed > 120) {
        blinkFrame = 3;
        blinkStateStartMs = now;
        needRedraw = true;
      } else if (blinkFrame == 3 && elapsed > 60) {
        isBlinking = false;
        blinkFrame = 0;
        needRedraw = true;
      }
    }
  }
  
  // 7. Mouth Animation & Shaking for Speaking
  if (currentState == STATE_SPEAKING) {
    if (now - lastAnimationUpdateMs > 150) {
      mouthFrame = (mouthFrame + 1) % 6;
      // Synchronize shake offset with mouth update to redraw once
      shakeX = random(-2, 3);
      shakeY = random(-2, 3);
      lastAnimationUpdateMs = now;
      needRedraw = true;
    }
    
    if (now - speakingStartMs > speakingDuration) {
      lastBubbleText = "";  // Clear so next text redraws
      bubbleLineCount = 0;  // Reset pagination
      textPage = 0;
      setAppState(STATE_IDLE);
    }
  }
  
  // 20-seconds idle timeout to return back to clock state
  if (currentState == STATE_IDLE && (now - stateTimerMs > 20000)) {
    setAppState(STATE_WAVING_OUTRO);
  }
  
  // Timeout for STATE_REMINDERS to return back to clock state after 20 seconds
  if (currentState == STATE_REMINDERS && (now - stateTimerMs > 20000)) {
    setAppState(STATE_CLOCK);
  }
  
  // Local timer decrement
  if (currentState == STATE_TIMER) {
    if (now - lastTimerTickMs >= 1000) {
      timerSecondsLeft--;
      lastTimerTickMs = now;
      if (timerSecondsLeft <= 0) {
        // Trigger timer finished alarm locally!
        buzzerActive = true;
        buzzerStartMs = millis();
        ledcWriteTone(0, 1000);
        setAppState(STATE_TIMER_FINISHED);
        // Notify server that timer completed
        if (client.connected()) {
          client.print("TIMER_DONE\n");
        }
        Serial.println("[TIMER] Countdown finished, buzzer activated");
      } else {
        needRedraw = true;
      }
    }
  }
  
  // Waving animation update for TIMER_FINISHED
  if (currentState == STATE_TIMER_FINISHED) {
    unsigned long elapsed = now - waveFrameStartMs;
    if (elapsed > 300) {
      waveFrame = (waveFrame == 0) ? 1 : 0;
      waveFrameStartMs = now;
      needRedraw = true;
    }
  }
  
  // 8. Thinking Status Dots Animation
  if (currentState == STATE_THINKING) {
    if (now - lastAnimationUpdateMs > 500) {
      drawThinkingOverlay();
      lastAnimationUpdateMs = now;
      needRedraw = true;
    }
  }
  
  // 9. Listening Status Dots Animation
  if (currentState == STATE_LISTENING) {
    if (now - lastAnimationUpdateMs > 500) {
      drawListeningOverlay();
      lastAnimationUpdateMs = now;
      needRedraw = true;
    }
  }
  
  // 10. Draw UI only when there's an actual change
  if (needRedraw) {
    if (currentState == STATE_REMINDERS) {
      drawRemindersPage();
    } else if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED) {
      drawTimerPage();
    } else if (currentState == STATE_SLEEPING) {
      // Do nothing, screen is kept black
    } else if (currentState == STATE_SLEEP_SUMMARY) {
      drawSleepSummaryPage();
    } else {
      drawAvatar();
      
      // Redraw overlay on top of the avatar's bottom overlap area
      if (currentState == STATE_IDLE) {
        drawIdleOverlay();
      } else if (currentState == STATE_LISTENING) {
        drawListeningOverlay();
      } else if (currentState == STATE_THINKING) {
        drawThinkingOverlay();
      } else if (currentState == STATE_SPEAKING || currentState == STATE_ALARM) {
        drawBubbleText(currentResponseText);
      } else if (currentState == STATE_TIMER_FINISHED) {
        drawBubbleText("TIME'S UP!");
      }
    }
    needRedraw = false;
  }

  // 11. Safety timeout: recover from stuck LISTENING/THINKING
  if ((currentState == STATE_LISTENING || currentState == STATE_THINKING) &&
      (now - stateTimerMs > 30000)) {
    Serial.printf("[TIMEOUT] %s stuck for 30s, returning to clock\n",
                  currentState == STATE_LISTENING ? "LISTENING" : "THINKING");
    setAppState(STATE_CLOCK);
  }

  // 12. Alarm flashing state update
  static unsigned long lastAlarmFlashMs = 0;
  if (currentState == STATE_ALARM || currentState == STATE_TIMER_FINISHED) {
    if (now - lastAlarmFlashMs > 250) {
      alarmFlashState = !alarmFlashState;
      lastAlarmFlashMs = now;
      needRedraw = true;
    }
    
    // Aggressive buzzer: 100ms toggle (5Hz)
    if (buzzerActive) {
      unsigned long elapsed = now - buzzerStartMs;
      unsigned long maxBuzzTime = (currentState == STATE_TIMER_FINISHED) ? 60000 : 10000;
      if (elapsed < maxBuzzTime) {
        bool on = (elapsed / 100) % 2 == 0;
        ledcWriteTone(0, on ? 1000 : 0);
        static unsigned long lastBuzzerLogMs = 0;
        if (now - lastBuzzerLogMs > 1000) {
          Serial.printf("[BUZZER] Toggling D13: %d, elapsed: %lu ms\n", on, elapsed);
          lastBuzzerLogMs = now;
        }
      } else {
        ledcWriteTone(0, 0);
        buzzerActive = false;
        Serial.printf("[BUZZER] Buzzer stopped after timeout\n");
        setAppState(STATE_CLOCK);  // Auto-dismiss alarm after buzzer stops
        return;
      }
    }
    
    // Hard backup timeout
    unsigned long maxAlarmTimeout = (currentState == STATE_TIMER_FINISHED) ? 60000 : 30000;
    if (now - stateTimerMs > maxAlarmTimeout) {
      Serial.println("[ALARM] Auto-dismissed after backup timeout");
      ledcWriteTone(0, 0);
      buzzerActive = false;
      setAppState(STATE_CLOCK);
      return;
    }
  }
}

void drawListeningOverlay() {
  bool dotVisible = (millis() / 500) % 2 == 0;
  
  tft.fillRoundRect(4, 110, 120, 46, 6, COLOR_BUBBLE_BG);
  tft.drawRoundRect(4, 110, 120, 46, 6, COLOR_STATUS);
  
  tft.fillCircle(18, 133, 4, dotVisible ? COLOR_STATUS : TFT_DARKGREY);
  tft.setTextColor(COLOR_STATUS);
  tft.setTextSize(1);
  tft.setCursor(28, 130);
  tft.println("LISTENING...");
}

void drawThinkingOverlay() {
  tft.fillRoundRect(4, 110, 120, 46, 6, COLOR_BUBBLE_BG);
  tft.drawRoundRect(4, 110, 120, 46, 6, COLOR_ACCENT);
  
  tft.setTextColor(COLOR_ACCENT);
  tft.setTextSize(1);
  tft.setCursor(20, 130);
  
  int dotsCount = (millis() / 500) % 4;
  String text = "Thinking";
  for (int i = 0; i < dotsCount; i++) {
    text += ".";
  }
  tft.println(text);
}

// Text pagination: split response into display lines
void paginateText(String text) {
  bubbleLineCount = 0;
  text.replace("\r", "");  // normalize
  
  int startX = 10;
  int maxW = 108;
  
  // Split on newlines first
  int searchStart = 0;
  while (searchStart < text.length() && bubbleLineCount < BUBBLE_LINES_MAX) {
    int nlIdx = text.indexOf('\n', searchStart);
    String line;
    if (nlIdx == -1) {
      line = text.substring(searchStart);
      searchStart = text.length();
    } else {
      line = text.substring(searchStart, nlIdx);
      searchStart = nlIdx + 1;
    }
    line.trim();
    if (line.length() == 0) {
      bubbleLines[bubbleLineCount++] = "";
      continue;
    }
    
    // Word-wrap this line
    int wordStart = 0;
    String currentLine = "";
    while (wordStart < line.length() && bubbleLineCount < BUBBLE_LINES_MAX) {
      // Skip spaces
      while (wordStart < line.length() && line[wordStart] == ' ') wordStart++;
      if (wordStart >= line.length()) break;
      
      // Find word end
      int wordEnd = wordStart;
      while (wordEnd < line.length() && line[wordEnd] != ' ') wordEnd++;
      
      String word = line.substring(wordStart, wordEnd);
      
      if (currentLine.length() == 0) {
        // First word on line — if it's too long, char-break it
        if (word.length() * 6 > maxW) {
          int charsFit = maxW / 6;
          int pos = 0;
          while (pos < word.length() && bubbleLineCount < BUBBLE_LINES_MAX) {
            bubbleLines[bubbleLineCount++] = word.substring(pos, pos + charsFit);
            pos += charsFit;
          }
        } else {
          currentLine = word;
        }
      } else {
        // Check if word fits on current line
        int testW = (currentLine.length() + 1 + word.length()) * 6;
        if (testW > maxW) {
          // Wrap to next line
          bubbleLines[bubbleLineCount++] = currentLine;
          currentLine = "";
          // Re-check if this word alone is too long
          if (word.length() * 6 > maxW) {
            int charsFit = maxW / 6;
            int pos = 0;
            while (pos < word.length() && bubbleLineCount < BUBBLE_LINES_MAX) {
              bubbleLines[bubbleLineCount++] = word.substring(pos, pos + charsFit);
              pos += charsFit;
            }
          } else {
            currentLine = word;
          }
        } else {
          currentLine += " " + word;
        }
      }
      wordStart = wordEnd;
    }
    if (currentLine.length() > 0 && bubbleLineCount < BUBBLE_LINES_MAX) {
      bubbleLines[bubbleLineCount++] = currentLine;
    }
  }
  
  textTotalPages = (bubbleLineCount + BUBBLE_LINES_PER_PAGE - 1) / BUBBLE_LINES_PER_PAGE;
  if (textTotalPages < 1) textTotalPages = 1;
  textPage = 0;
}

void drawBubbleText(String text) {
  // Anti-flicker: skip redraw if text unchanged
  if (text == lastBubbleText) return;
  
  // Reset pagination for new text
  bubbleLineCount = 0;
  textPage = 0;
  lastBubbleText = text;
  paginateText(text);
  
  // Speech Bubble Rectangle
  tft.fillRoundRect(4, 110, 120, 46, 6, COLOR_BUBBLE_BG);
  uint16_t borderCol = text.startsWith("ALARM:") ? TFT_RED : COLOR_BORDER;
  tft.drawRoundRect(4, 110, 120, 46, 6, borderCol);
  
  // Tail pointing UP to the avatar's mouth
  tft.fillTriangle(64, 104, 60, 110, 68, 110, COLOR_BORDER);
  tft.fillTriangle(64, 106, 61, 110, 67, 110, COLOR_BUBBLE_BG);
  
  tft.setTextColor(COLOR_TEXT, COLOR_BUBBLE_BG);
  tft.setTextSize(1);
  
  int startX = 10;
  int startY = 116;
  int lineH = 9;
  
  int lineIdx = textPage * BUBBLE_LINES_PER_PAGE;
  int lineEnd = lineIdx + BUBBLE_LINES_PER_PAGE;
  if (lineEnd > bubbleLineCount) lineEnd = bubbleLineCount;
  
  int cursorY = startY;
  for (int i = lineIdx; i < lineEnd && cursorY + 8 <= 110 + 46 - 4; i++) {
    tft.setCursor(startX, cursorY);
    tft.print(bubbleLines[i]);
    cursorY += lineH;
  }
  
  // Page indicator if multiple pages
  if (textTotalPages > 1) {
    tft.setCursor(90, 150);
    tft.printf("%d/%d", textPage + 1, textTotalPages);
  }
}

void drawRemindersPage() {
  tft.fillScreen(COLOR_BG);
  tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
  tft.drawRect(4, 4, 120, 152, COLOR_BG);
  
  // Title
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.setTextSize(1);
  tft.setCursor(15, 12);
  tft.print("ACTIVE REMINDERS");
  tft.drawLine(6, 22, 122, 22, COLOR_BORDER);
  
  // Paginate if not already done
  if (bubbleLineCount == 0) {
    paginateText(currentResponseText);
  }
  
  int itemsPerPage = 10;
  int totalPages = (bubbleLineCount + itemsPerPage - 1) / itemsPerPage;
  if (totalPages < 1) totalPages = 1;
  
  int startIdx = textPage * itemsPerPage;
  int endIdx = startIdx + itemsPerPage;
  if (endIdx > bubbleLineCount) endIdx = bubbleLineCount;
  
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  int cursorY = 30;
  for (int i = startIdx; i < endIdx; i++) {
    tft.setCursor(8, cursorY);
    tft.print(bubbleLines[i]);
    cursorY += 11;
  }
  
  // Page indicator at bottom
  tft.setTextColor(COLOR_STATUS, COLOR_BG);
  tft.setCursor(45, 142);
  tft.printf("%d / %d", textPage + 1, totalPages);
}

void drawTimerPage() {
  // Clear the content area (preserve border by only clearing inner region)
  tft.fillRect(5, 5, 118, 150, COLOR_BG);
  
  // Borders
  tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
  tft.drawRect(4, 4, 120, 152, COLOR_BG);
  
  // Title
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.setTextSize(1);
  tft.setCursor(30, 15);
  tft.print("FOCUS TIMER");
  tft.drawLine(6, 25, 122, 25, COLOR_BORDER);
  
  // Format MM:SS or HH:MM:SS
  char timeBuffer[16];
  int h = timerSecondsLeft / 3600;
  int m = (timerSecondsLeft % 3600) / 60;
  int s = timerSecondsLeft % 60;
  
  if (h > 0) {
    snprintf(timeBuffer, sizeof(timeBuffer), "%02d:%02d:%02d", h, m, s);
  } else {
    snprintf(timeBuffer, sizeof(timeBuffer), "%02d:%02d", m, s);
  }
  
  // Large timer text with dynamic sizing to prevent overflow
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  int textSize = (h > 0) ? 2 : 3;
  tft.setTextSize(textSize);
  int charWidth = (textSize == 2) ? 12 : 18;
  int textW = strlen(timeBuffer) * charWidth;
  int cursorY = (textSize == 2) ? 68 : 62;
  tft.setCursor((128 - textW) / 2, cursorY);
  tft.print(timeBuffer);
  
  // Instructions & Status Info
  tft.setTextSize(1);
  tft.drawRoundRect(10, 124, 108, 24, 4, COLOR_BORDER);
  
  if (currentState == STATE_TIMER_PAUSED) {
    tft.setTextColor(COLOR_ACCENT, COLOR_BG);
    tft.setCursor((128 - (12 * 6)) / 2, 105);
    tft.print("** PAUSED **");
    
    tft.setTextColor(COLOR_STATUS, COLOR_BG);
    tft.setCursor((128 - (15 * 6)) / 2, 132);
    tft.print("CLICK TO RESUME");
  } else {
    tft.setTextColor(COLOR_STATUS, COLOR_BG);
    tft.setCursor((128 - (16 * 6)) / 2, 105);
    tft.print("[ CLICK: PAUSE ]");
    
    tft.setTextColor(COLOR_STATUS, COLOR_BG);
    tft.setCursor((128 - (14 * 6)) / 2, 132);
    tft.print("HOLD TO CANCEL");
  }
}

void drawSleepSummaryPage() {
  // Clear the content area (preserve border by only clearing inner region)
  tft.fillRect(5, 5, 118, 150, COLOR_BG);
  
  // Borders
  tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
  tft.drawRect(4, 4, 120, 152, COLOR_BG);
  
  // Title - capsule-shaped header
  tft.fillRoundRect(8, 8, 112, 16, 3, COLOR_BUBBLE_BG);
  tft.drawRoundRect(8, 8, 112, 16, 3, COLOR_BORDER);
  tft.setTextColor(COLOR_ACCENT, COLOR_BUBBLE_BG);
  tft.setTextSize(1);
  String title = sleepSummaryType + " Summary";
  title.toUpperCase();
  int titleW = title.length() * 6;
  tft.setCursor((128 - titleW) / 2, 12);
  tft.print(title);
  
  // Duration display (Large text in center)
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setTextSize(2);
  char durStr[16];
  snprintf(durStr, sizeof(durStr), "%.1fh", sleepSummaryDuration);
  int durW = strlen(durStr) * 12;
  tft.setCursor((128 - durW) / 2, 34);
  tft.print(durStr);
  tft.setTextSize(1);
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.setCursor((128 - (8 * 6)) / 2, 52);
  tft.print("DURATION");
  
  tft.drawLine(10, 64, 118, 64, COLOR_BORDER);
  
  // Stats block
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  
  // Movements
  tft.setCursor(10, 72);
  tft.print("Movements: ");
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.print(sleepSummaryMovements);
  
  // Noise level (RMS)
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(10, 88);
  tft.print("Noise Avg: ");
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.printf("%.0f", sleepSummaryAvgNoise);
  
  // LDR Light level
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(10, 104);
  tft.print("Room Ldr : ");
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.print(sleepSummaryAvgLdr);
  
  tft.drawLine(10, 118, 118, 118, COLOR_BORDER);
  
  // Quality rating capsule at bottom
  tft.fillRoundRect(10, 126, 108, 20, 3, COLOR_BUBBLE_BG);
  tft.drawRoundRect(10, 126, 108, 20, 3, COLOR_BORDER);
  
  tft.setTextSize(1);
  String qualStr = "Quality: " + sleepSummaryQuality;
  qualStr.toUpperCase();
  int qualW = qualStr.length() * 6;
  tft.setTextColor(COLOR_TEXT, COLOR_BUBBLE_BG);
  tft.setCursor((128 - qualW) / 2, 132);
  tft.print(qualStr);
}



void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Disable brownout detector
  
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BOOT_BTN, INPUT_PULLUP);  // BOOT button for text pagination
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT_PULLDOWN);
  digitalWrite(BUZZER_PIN, LOW);
  
  lastPirMotionMs = millis();
  
  // Setup LEDC channel 0 for buzzer/speaker
  ledcSetup(0, 1000, 8);  // channel 0, 1kHz base, 8-bit resolution
  ledcAttachPin(BUZZER_PIN, 0);
  ledcWriteTone(0, 0);    // Silent by default

  // PIR Motion Sensor
  pinMode(PIR_PIN, INPUT);

  tft.init();
  tft.setRotation(2); // Rotate to Portrait 128x160
  tft.setSwapBytes(true);
  
  // Create 128x110 Sprite
  faceSprite.createSprite(128, 110);
  faceSprite.setSwapBytes(true);
  
  tft.fillScreen(COLOR_BG);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setTextSize(1);
  tft.setCursor(10, 10);
  tft.println("Connecting...");

  // Allocate themedBuf on heap (sized to support up to 128x160 full-screen sleep sprites)
  themedBuf = (uint16_t *)malloc(128 * 160 * sizeof(uint16_t));
  if (!themedBuf) {
    Serial.println("[FATAL] themedBuf alloc failed");
    while(1) delay(1000);
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int connAttempts = 0;
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED && connAttempts < 10) {
    delay(500);
    Serial.print(".");
    connAttempts++;
  }
  Serial.println("");
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi Connected! IP Address: ");
    Serial.println(WiFi.localIP());
    configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.google.com", "time.nist.gov");
  } else {
    Serial.println("WiFi Connection Failed. Starting in Offline Mode.");
  }

  client.setTimeout(2);
  setupI2S();



  tft.fillScreen(COLOR_BG);
  setAppState(STATE_CLOCK);
}



void loop() {
  updateAnimations();

  // Read PIR sensor (HC-SR501 on PIR_PIN = 27)
  bool pirRawState = (digitalRead(PIR_PIN) == HIGH);
  unsigned long currentMs = millis();
  
  static unsigned long pirTransitionToHighMs = 0;
  static bool debouncedPirState = false;
  
  // Software validation/debounce check:
  // Since a real PIR motion trigger stays HIGH for at least 2.5 seconds (the minimum hardware time delay),
  // brief pulses that go back to LOW in less than 200ms are filtered out as RF/Power noise.
  if (pirRawState) {
    if (pirTransitionToHighMs == 0) {
      pirTransitionToHighMs = currentMs; // Start tracking transition to HIGH
    } else if (currentMs - pirTransitionToHighMs >= 200) {
      debouncedPirState = true; // Confirmed motion event (sustained HIGH)
    }
  } else {
    pirTransitionToHighMs = 0;
    debouncedPirState = false;
  }
  
  bool pirState = debouncedPirState; // Use debounced state for transitions and logs
  static bool lastPirState = false;
  static unsigned long lastPirMsgSentMs = 0;
  
  // Track LOW -> HIGH transitions (rising edge)
  bool risingEdge = (pirState && !lastPirState);
  lastPirState = pirState;
  
  if (pirState) {
    lastPirMotionMs = currentMs; // update motion timer
  }

  // Track 30-second motion history (sampled once per second)
  static bool motionHistory[30] = {false};
  static int historyIdx = 0;
  static unsigned long lastHistorySampleMs = 0;
  
  if (currentMs - lastHistorySampleMs >= 1000) {
    lastHistorySampleMs = currentMs;
    motionHistory[historyIdx] = pirState; // Sample the debounced PIR state
    historyIdx = (historyIdx + 1) % 30;
  }
  
  // Count seconds of motion in the last 30 seconds
  int motionSeconds = 0;
  for (int i = 0; i < 30; i++) {
    if (motionHistory[i]) {
      motionSeconds++;
    }
  }

  // --- SLEEP / WAKE STATE MACHINE LOGIC (added for sleep monitoring foundation) ---
  if (currentState == STATE_CLOCK) {
    // Sleep transition condition:
    // 1. Continuous time in Clock State > 30s (must be in clock for 30s)
    // 2. Light level is dark (LDR < 500)
    // 3. PIR is mostly motionless (motion detected in <= 3 seconds of the last 30 seconds)
    if ((currentMs - clockStateEnteredMs > 30000) && 
        (cachedLdr < 500) && 
        (motionSeconds <= 3)) {
      setAppState(STATE_SLEEPING);
      Serial.println("PIR: In Clock state, dark, and mostly motionless. Entering SLEEPING state.");
    }
  } 
  else if (currentState == STATE_SLEEPING) {
    // Sample LDR during sleep every 10 seconds and send to the server to monitor optimal light conditions
    static unsigned long lastSleepLdrMs = 0;
    if (currentMs - lastSleepLdrMs > 10000) {
      lastSleepLdrMs = currentMs;
      i2s_stop(I2S_NUM_0);
      i2s_adc_disable(I2S_NUM_0);
      cachedLdr = analogRead(LDR_PIN);
      i2s_adc_enable(I2S_NUM_0);
      i2s_start(I2S_NUM_0);
      if (client.connected()) {
        client.print("LDR:" + String(cachedLdr) + "\n");
      }
    }

    // 1. Send sleep heartbeat command every 15s to keep TCP connection alive
    if (currentMs - lastSleepHeartbeatMs > 15000) {
      if (client.connected()) {
        client.print("PIR:SLEEP\n");
      }
      lastSleepHeartbeatMs = currentMs;
      Serial.println("PIR: Standby heartbeat keep-alive sent to server.");
    }
    
    // 2. Any motion (rising edge) triggers the pre-wake standby state, but ignore motion during the first 20s grace period
    if (risingEdge && (currentMs - lastSleepEnteredMs > 20000)) {
      setAppState(STATE_SLEEPING_PREWAKE);
      Serial.println("PIR: Motion detected. Entering pre-wake standby.");
    }
  } 
  else if (currentState == STATE_SLEEPING_PREWAKE) {
    // In Pre-Wake: Screen remains black, but audio/keyword streaming is enabled
    bool fullyWakeUp = false;
    
    // Confirmation Trigger A: Motion held HIGH continuously for >= 2.0 seconds
    if (pirState && (currentMs - preWakeEnteredMs >= 2000)) {
      fullyWakeUp = true;
      Serial.println("PIR: Confirmed wakeup - Motion held for 2 seconds.");
    }
    
    // Confirmation Trigger B: Second distinct wave (rising edge) during the window
    if (risingEdge) {
      preWakeRisingEdges++;
      Serial.printf("PIR: Wave detected in pre-wake. Edge count: %d\n", preWakeRisingEdges);
      // Notify companion server of the additional motion event during sleep pre-wake
      if (client.connected()) {
        client.print("PIR:MOTION\n");
      }
      if (preWakeRisingEdges >= 2) {
        fullyWakeUp = true;
        Serial.println("PIR: Confirmed wakeup - Second distinct wave detected.");
      }
    }
    
    // Pre-wake 10-second timeout
    if (currentMs - preWakeEnteredMs > 10000) {
      // Pre-wake expired without confirmation trigger -> go straight back to sleep
      setAppState(STATE_SLEEPING);
      Serial.println("PIR: Pre-wake timed out without confirmation. Returning to SLEEPING.");
    } 
    else if (fullyWakeUp) {
      // Fully woke up to clock state (resets sleep timers)
      setAppState(STATE_CLOCK);
    }
  }
  else if (currentState == STATE_SLEEP_SUMMARY) {
    if (currentMs - sleepSummaryStartMs > 15000) {
      setAppState(STATE_CLOCK);
    }
    if (digitalRead(BUTTON_PIN) == LOW) {
      delay(200); // debounce
      setAppState(STATE_CLOCK);
    }
  }
  
  // Periodic Debug Logs for calibration (modified to include Pre-Wake status, LDR, and motion density)
  static unsigned long lastDebugPrintMs = 0;
  if ((currentState == STATE_CLOCK || currentState == STATE_SLEEPING || currentState == STATE_SLEEPING_PREWAKE) && (currentMs - lastDebugPrintMs > 3000)) {
    lastDebugPrintMs = currentMs;
    long timeSinceLastMotion = (long)(currentMs - lastPirMotionMs);
    const char* stateStr = "CLOCK";
    if (currentState == STATE_SLEEPING) stateStr = "SLEEPING";
    else if (currentState == STATE_SLEEPING_PREWAKE) stateStr = "PREWAKE";
    Serial.printf("[DEBUG] PIR Pin: %d | Motion Density: %d/30s | LDR: %d | Time since last motion: %ld ms | State: %s\n", 
                  pirState, motionSeconds, cachedLdr, timeSinceLastMotion, stateStr);
  }

  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastServerConnectAttemptMs > 10000) { // Try connecting every 10 seconds
      lastServerConnectAttemptMs = now;
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Attempting connection to companion server...");
        if (client.connect(SERVER_IP, SERVER_PORT)) {
          client.setNoDelay(true);
          Serial.println("Connected to server successfully!");
          setAppState(STATE_CLOCK);
        } else {
          Serial.println("Connection to server failed. Retrying in 10s...");
        }
      } else {
        Serial.println("WiFi not connected. Skipping server connection attempt.");
      }
    }
  }

  // Check Button State for manual wake up or timer pause/cancel (edge and hold detection)
  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  // 1. Detect Button Press (Edge LOW)
  if (buttonPressed && !lastButtonState) {
    buttonPressStartMs = millis();
    buttonHeldProcessed = false;
    
    // For normal flow, CMD:WOKE is sent immediately if not in timer states
    if (currentState != STATE_TIMER && currentState != STATE_TIMER_PAUSED && currentState != STATE_TIMER_FINISHED) {
      greetingMode = false;
      isRecording = true;
      if (client.connected()) {
        client.print("CMD:WOKE\n");
      }
      setAppState(STATE_WAVING_INTRO);
    }
  }
  
  // 2. Detect Button Hold (Active Timer, Paused Timer, or Finished Timer states only)
  if (buttonPressed && lastButtonState && !buttonHeldProcessed) {
    if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED) {
      if (millis() - buttonPressStartMs > 1000) {  // 1.0 second hold
        buttonHeldProcessed = true;
        
        // Long Press -> Cancel Timer
        ledcWriteTone(0, 0);
        buzzerActive = false;
        timerSecondsLeft = 0;
        
        // Notify Python server so timer_running gets set to False
        if (client.connected()) {
          client.print("TIMER_DONE\n"); 
        }
        
        setAppState(STATE_CLOCK);
        Serial.println("[TIMER] Long press: timer cancelled");
      }
    }
  }
  
  // 3. Detect Button Release (Edge HIGH)
  if (!buttonPressed && lastButtonState) {
    // Normal recording flow release
    if (isRecording) {
      isRecording = false;
      if (client.connected()) {
        client.print("___END___\n");
      }
    }
    // Timer state release (Short Press -> Toggle Pause/Resume or Dismiss Alarm)
    else if (!buttonHeldProcessed) {
      if (currentState == STATE_TIMER) {
        // Pause timer
        setAppState(STATE_TIMER_PAUSED);
        Serial.println("[TIMER] Short press: paused");
      }
      else if (currentState == STATE_TIMER_PAUSED) {
        // Resume timer
        lastTimerTickMs = millis(); // Reset tick timestamp to avoid instant decrement
        setAppState(STATE_TIMER);
        Serial.println("[TIMER] Short press: resumed");
      }
      else if (currentState == STATE_TIMER_FINISHED) {
        // Dismiss completed alarm
        ledcWriteTone(0, 0);
        buzzerActive = false;
        setAppState(STATE_CLOCK);
        Serial.println("[TIMER] Short press: completed alarm dismissed");
      }
    }
    buttonHeldProcessed = false;
  }
  lastButtonState = buttonPressed;

  // BOOT button: paginate text, dismiss timer/alarm, or clear when no more pages
  if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED) {
    // In timer states, BOOT button dismisses/cancels the timer
    bool bootPressed = (digitalRead(BOOT_BTN) == LOW);
    if (bootPressed && !lastBootBtnState) {
      ledcWriteTone(0, 0);
      buzzerActive = false;
      timerSecondsLeft = 0;
      
      // Notify Python server so timer_running gets set to False
      if (client.connected()) {
        client.print("TIMER_DONE\n");
      }
      
      setAppState(STATE_CLOCK);
    }
    lastBootBtnState = bootPressed;
  }
  else if (currentState == STATE_SPEAKING || currentState == STATE_ALARM || currentState == STATE_REMINDERS) {
    bool bootPressed = (digitalRead(BOOT_BTN) == LOW);
    if (bootPressed && !lastBootBtnState) {
      textPage++;
      int itemsPerPage = (currentState == STATE_REMINDERS) ? 10 : BUBBLE_LINES_PER_PAGE;
      int totalPages = (bubbleLineCount + itemsPerPage - 1) / itemsPerPage;
      if (totalPages < 1) totalPages = 1;
      
      if (textPage >= totalPages) {
        // No more pages — clear text and return to clock
        lastBubbleText = "";
        bubbleLineCount = 0;
        textPage = 0;
        setAppState(STATE_CLOCK);
      } else {
        lastBubbleText = "";  // Force redraw with new page
        needRedraw = true;
      }
    }
    lastBootBtnState = bootPressed;
  }

  // Stream Audio continuously when in clock, idle, listening, alarm, or timer states
  // Timer states need audio for voice-based cancel commands
  // We use non-blocking I2S reading (timeout 0) so animations remain smooth
  bool shouldStream = (currentState == STATE_CLOCK || currentState == STATE_IDLE || currentState == STATE_LISTENING || currentState == STATE_ALARM || currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED || currentState == STATE_SLEEPING || currentState == STATE_SLEEPING_PREWAKE);
  size_t bytes_read = 0;
  
  static uint16_t raw_accumulator[512]; 
  static int raw_accum_index = 0;
  
  if (shouldStream) {
    uint16_t temp_buffer[256];
    i2s_read(I2S_NUM_0, &temp_buffer, sizeof(temp_buffer), &bytes_read, 0);

    if (bytes_read > 0) {
      int samples_read = bytes_read / 2;
      for (int i = 0; i < samples_read; i++) {
        raw_accumulator[raw_accum_index++] = temp_buffer[i];
        
        // When accumulator is full (512 samples = 1024 bytes)
        if (raw_accum_index >= 512) {
          int16_t pcm_buffer[256]; 
          int pcm_index = 0;
          
          for (int j = 0; j < 512; j += 2) {
            uint16_t raw_sample = raw_accumulator[j] & 0x0FFF;
            
            float x = (float)raw_sample;
            dc_filter_y = x - dc_filter_x + 0.995 * dc_filter_y;
            dc_filter_x = x;
            
            float scaled_audio = dc_filter_y * 12.0;
            if (scaled_audio > 32767.0) scaled_audio = 32767.0;
            if (scaled_audio < -32768.0) scaled_audio = -32768.0;
            
            pcm_buffer[pcm_index++] = (int16_t)scaled_audio;
          }
          
          if (client.connected()) {
            client.write((const uint8_t*)pcm_buffer, pcm_index * 2);
          }
          raw_accum_index = 0;
        }
      }
    }
  } else {
    raw_accum_index = 0; // Reset index when not streaming to avoid stale data
  }

  // Yield to FreeRTOS if we didn't read any data to keep CPU usage low
  if (bytes_read == 0) {
    delay(1);
  }

  // Check for Server Commands and LLM responses
  if (client.available()) {
    String response = client.readStringUntil('\n');
    response.trim(); 
    
    if (response.length() > 0) {
      // --- TIMER ACTIVE GUARD ---
      // When timer is active, only accept TIMER_START, TIMER_CANCEL, TIMER_STOP, TIMER_PAUSE, TIMER_RESUME, and WEATHER commands
      bool timerActive = (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED);
      bool isTimerCmd = response.startsWith("TIMER_") || response.startsWith("WEATHER:");
      
      if (timerActive && !isTimerCmd) {
        Serial.printf("[TIMER GUARD] Rejected command during timer: %s\n", response.c_str());
        // Fall through to consume the command but don't act on it
      }
      else if (response.startsWith("CMD:WAKE") || response == "UI_STATE:LISTENING") {
        serverDuration = 0;
        setAppState(STATE_WAVING_INTRO);
      }
      else if (response == "UI_STATE:GREETING") {
        serverDuration = 0;
        greetingMode = true;
        setAppState(STATE_WAVING_INTRO);
      }
      else if (response.startsWith("CMD:THINKING") || response == "UI_STATE:THINKING") {
        serverDuration = 0;
        setAppState(STATE_THINKING);
      }
      else if (response == "UI_STATE:IDLE") {
        serverDuration = 0;
        // Guard: do NOT reset to clock if a timer is actively counting down, paused, or finished
        if (currentState != STATE_TIMER && currentState != STATE_TIMER_PAUSED && currentState != STATE_TIMER_FINISHED) {
          setAppState(STATE_CLOCK);
        }
      }
      else if (response == "CMD:START_SLEEP") {
        setAppState(STATE_SLEEPING);
        Serial.println("[CMD] Manual sleep command received from server.");
      }
      else if (response.startsWith("UI_SLEEP_SUMMARY:")) {
        // Format: UI_SLEEP_SUMMARY:type:duration:movements:avg_noise:avg_ldr:quality
        int firstColon = response.indexOf(':', 17);
        int secondColon = response.indexOf(':', firstColon + 1);
        int thirdColon = response.indexOf(':', secondColon + 1);
        int fourthColon = response.indexOf(':', thirdColon + 1);
        int fifthColon = response.indexOf(':', fourthColon + 1);
        
        if (firstColon != -1 && secondColon != -1 && thirdColon != -1 && fourthColon != -1 && fifthColon != -1) {
          sleepSummaryType = response.substring(17, firstColon);
          sleepSummaryDuration = response.substring(firstColon + 1, secondColon).toFloat();
          sleepSummaryMovements = response.substring(secondColon + 1, thirdColon).toInt();
          sleepSummaryAvgNoise = response.substring(thirdColon + 1, fourthColon).toFloat();
          sleepSummaryAvgLdr = response.substring(fourthColon + 1, fifthColon).toInt();
          sleepSummaryQuality = response.substring(fifthColon + 1);
          
          sleepSummaryType.trim();
          sleepSummaryQuality.trim();
          
          sleepSummaryStartMs = millis();
          setAppState(STATE_SLEEP_SUMMARY);
          Serial.println("[Sleep Monitor] Displaying sleep summary page.");
        }
      }
      else if (response.startsWith("TIMER_START:")) {
        timerSecondsLeft = response.substring(12).toInt();
        lastTimerTickMs = millis();
        Serial.printf("[TIMER] Starting countdown: %d seconds\n", timerSecondsLeft);
        setAppState(STATE_TIMER);
      }
      else if (response == "TIMER_PAUSE") {
        setAppState(STATE_TIMER_PAUSED);
        Serial.println("[TIMER] Paused via server command");
      }
      else if (response == "TIMER_RESUME") {
        lastTimerTickMs = millis();
        setAppState(STATE_TIMER);
        Serial.println("[TIMER] Resumed via server command");
      }
      else if (response == "TIMER_CANCEL" || response == "TIMER_STOP") {
        ledcWriteTone(0, 0);
        buzzerActive = false;
        setAppState(STATE_CLOCK);
      }
      else if (response.startsWith("WEATHER:")) {
        int firstColon = response.indexOf(':', 8);
        int secondColon = response.indexOf(':', firstColon + 1);
        if (firstColon != -1 && secondColon != -1) {
          weatherTemp = response.substring(8, firstColon).toInt();
          weatherDesc = response.substring(firstColon + 1, secondColon);
          weatherIconIdx = response.substring(secondColon + 1).toInt();
          hasWeather = true;
          needRedraw = true;
        }
      }
      else if (response.startsWith("UI_ALARM:")) {
        serverDuration = 0;
        String alarmName = response.substring(9);
        alarmName.trim();
        currentResponseText = "ALARM: " + alarmName;
        speakingStartMs = millis();
        speakingDuration = 999999UL;
        buzzerActive = true;
        buzzerStartMs = millis();
        setAppState(STATE_ALARM);
        ledcWriteTone(0, 1000); // Immediate feedback
        Serial.println("[BUZZER] Alarm received, buzzer activated on D13");
      }
      else if (response.startsWith("DURATION:")) {
        serverDuration = (unsigned long)(response.substring(9).toFloat() * 1000.0f);
      }
      else if (response.startsWith("UI_LIST:")) {
        serverDuration = 0;  // Clear any stale duration
        String listContent = response.substring(8);
        listContent.replace("|", "\n"); // replace pipe with newline for pagination
        currentResponseText = listContent;
        speakingStartMs = millis();
        speakingDuration = 20000UL; // Display reminders for 20 seconds
        setAppState(STATE_REMINDERS);
      }
      else {
        // Chat text response
        String cleanMsg = response;
        if (response.startsWith("UI_MSG:")) {
          cleanMsg = response.substring(7);
        }
        else if (response.startsWith("AI: ")) {
          cleanMsg = response.substring(4);
        }
        currentResponseText = cleanMsg;
        speakingStartMs = millis();
        speakingDuration = serverDuration > 0 ? serverDuration : max(5000UL, (unsigned long)(cleanMsg.length() * 100));
        serverDuration = 0;
        lastBubbleText = "";  // Force bubble redraw
        bubbleLineCount = 0;  // Reset pagination for new text
        textPage = 0;
        setAppState(STATE_SPEAKING);
      }
    }
  }
}
