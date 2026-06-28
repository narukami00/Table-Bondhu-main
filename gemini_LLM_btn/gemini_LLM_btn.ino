 
#include <WiFi.h>
#include <TFT_eSPI.h>
#include <driver/i2s.h>
#include <driver/dac.h>
#include <time.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "config.h"
#include "images.h"

#define BUTTON_PIN 14 // Tactile Button (GND + D14)
#define BOOT_BTN 0    // Built-in BOOT button for text pagination
#define LDR_PIN 34   // ADC1_CH6 - Light Dependent Resistor
#define BUZZER_PIN 13 // Active Buzzer (HIGH = sound)
#define I2S_SAMPLE_RATE 16000

// Theme definitions
#define THEME_GIRL 0
#define THEME_PIKACHU 1

// SELECT YOUR ACTIVE THEME HERE
#define ACTIVE_THEME THEME_PIKACHU

// Default colors from compile-time theme (copied to runtime vars in setup)
#if ACTIVE_THEME == THEME_PIKACHU
  #define DEFAULT_BG 0x18E6
  #define DEFAULT_ACCENT 0xFEE0
  #define DEFAULT_BORDER 0xFEE0
  #define DEFAULT_BUBBLE_BG TFT_BLACK
  #define DEFAULT_TEXT TFT_WHITE
  #define DEFAULT_STATUS TFT_RED
  #define ASSET_BG 0x18E6
#else
  #define DEFAULT_BG 0x911C
  #define DEFAULT_ACCENT TFT_CYAN
  #define DEFAULT_BORDER TFT_CYAN
  #define DEFAULT_BUBBLE_BG TFT_BLACK
  #define DEFAULT_TEXT TFT_WHITE
  #define DEFAULT_STATUS TFT_GREEN
  #define ASSET_BG 0x911C
#endif

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
  { 0x0000, 0xF800, 0xF800, 0x0000, 0xFFFF, 0xF800 },  // Night: dark bg, red accent
  { 0x4100, 0xFBE0, 0xFBE0, 0x0000, 0xFFFF, 0xFDA0 },  // Autumn: dark orange bg, yellow
  { 0x0320, 0x07E0, 0x07E0, 0x0000, 0xFFFF, 0x07E0 },  // Spring: dark green bg, green
  { DEFAULT_BG, DEFAULT_ACCENT, DEFAULT_BORDER, DEFAULT_BUBBLE_BG, DEFAULT_TEXT, DEFAULT_STATUS }  // Bright: default
};

#define LDR_CONFIRM_READS 3
#define THEME_COOLDOWN_MS 60000

int activeTheme = 3;  // Start at default
int pendingTheme = -1;
int pendingCount = 0;
unsigned long lastSwitchMs = 0;
unsigned long lastThemeLdrMs = 0;
int cachedLdr = 2048;

int ldrToTheme(int ldr) {
  if (ldr < 300) return 0;       // Night
  if (ldr < 1000) return 1;      // Autumn
  if (ldr < 1700) return 2;      // Spring
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
  tft.fillScreen(COLOR_BG);
  Serial.printf("[THEME] Switched to theme %d (LDR=%d)\n", idx, cachedLdr);
}

// Buffer for pushThemedImage (sprite background replacement)
static uint16_t themedBuf[128 * 128];

// Sprite frame macros (reference images.h arrays, independent of runtime colors)
#if ACTIVE_THEME == THEME_PIKACHU
  #define CURRENT_IDLE pika_idle
  #define CURRENT_HALF_BLINK pika_half_blink
  #define CURRENT_SMILE_BLINK pika_smile_blink
  #define CURRENT_TALK_20 pika_talk_20
  #define CURRENT_TALK_60 pika_talk_60
  #define CURRENT_TALK_100 pika_talk_100
  #define CURRENT_TALK_BLINK pika_talk_blink
  #define CURRENT_SMILE pika_smile
  #define CAMEO_FRAME_COUNT 7
#else
  #define CURRENT_IDLE avatar_idle
  #define CURRENT_HALF_BLINK avatar_half_blink
  #define CURRENT_SMILE_BLINK avatar_smile_blink
  #define CURRENT_TALK_20 avatar_talk_20
  #define CURRENT_TALK_60 avatar_talk_60
  #define CURRENT_TALK_100 avatar_talk_100
  #define CURRENT_TALK_BLINK avatar_talk_blink
  #define CURRENT_SMILE avatar_smile
  #define CAMEO_FRAME_COUNT 5
#endif

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite faceSprite = TFT_eSprite(&tft);
TFT_eSprite cameoSprite = TFT_eSprite(&tft);
WiFiClient client;
bool isRecording = false;
bool alarmFlashState = false;

// Buzzer state
bool buzzerActive = false;
unsigned long buzzerStartMs = 0;

// Audio Filter Variables
float dc_filter_y = 0;
float dc_filter_x = 0;

enum AppState {
  STATE_CLOCK,
  STATE_CAMEO,
  STATE_WAVING_INTRO,
  STATE_IDLE,
  STATE_LISTENING,
  STATE_THINKING,
  STATE_SPEAKING,
  STATE_WAVING_OUTRO,
  STATE_ALARM
};

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
bool greetingMode = false;  // True when wave was triggered by greeting (skip LISTENING on finish)

// Redraw control
bool needRedraw = true;

// Timezone offset (Bangladesh Standard Time GMT+6 = 6 * 3600 seconds)
const long gmtOffset_sec = 6 * 3600;
const int daylightOffset_sec = 0;

void drawClockFace();
void drawIdleOverlay();
void drawListeningOverlay();
void drawThinkingOverlay();
void drawBubbleText(String text);
void drawCameoFrame();
void drawWaveFrame();
void dissolveWipe(uint16_t targetColor);

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
    
    // Stop buzzer when leaving alarm state
    if (oldState == STATE_ALARM) {
      ledcWriteTone(0, 0);
      buzzerActive = false;
    }
    
    // Dissolve only on button press (Clock → Waving Intro) — skip for greeting and routine transitions
    if (oldState == STATE_CLOCK && currentState == STATE_WAVING_INTRO && !greetingMode) {
      dissolveWipe(COLOR_BG);
    }
    
    // Clear screen or bottom overlay area depending on state
    if (currentState == STATE_CLOCK) {
      tft.fillScreen(COLOR_BG);
      drawClockFace();
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
    }
  }
}

void drawAvatar() {
  const uint16_t* frameData = CURRENT_IDLE;
  
  if (currentState == STATE_SPEAKING || currentState == STATE_ALARM) {
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
  uint16_t bgCol = (currentState == STATE_ALARM && alarmFlashState) ? TFT_RED : COLOR_BG;
  faceSprite.fillSprite(bgCol);
  faceSprite.pushImage(0, 0, 128, 128, frameData);
  faceSprite.pushSprite(shakeX, shakeY);
}

void drawCameoFrame() {
  const uint16_t* frameData = NULL;
  int w = 128;
  int h = 0;
  int yPos = 0;

#if ACTIVE_THEME == THEME_PIKACHU
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
#else
  // Cameo frames for Girl: head 1->2->3->2->1 (frame indices 1 to 5)
  if (cameoFrame == 1 || cameoFrame == 5) {
    frameData = avatar_cameo_1;
    h = 57;
    yPos = 103;
  } else if (cameoFrame == 2 || cameoFrame == 4) {
    frameData = avatar_cameo_2;
    h = 89;
    yPos = 71;
  } else if (cameoFrame == 3) {
    frameData = avatar_cameo_3;
    h = 119;
    yPos = 41;
  }
#endif

  if (frameData != NULL) {
    // Clear the vertical region occupied by the cameo
    tft.fillRect(0, 32, 128, 128, COLOR_BG);
    
    cameoSprite.createSprite(w, h);
    cameoSprite.setSwapBytes(true);
    cameoSprite.fillSprite(COLOR_BG);
    cameoSprite.pushImage(0, 0, w, h, frameData);
    cameoSprite.pushSprite(0, yPos);
    cameoSprite.deleteSprite();
  }
}

void drawWaveFrame() {
  const uint16_t* frameData = NULL;
#if ACTIVE_THEME == THEME_PIKACHU
  // wave 1->2->3->2->3->1 (indices 0 to 5)
  if (waveFrame == 0 || waveFrame == 5) frameData = pika_wave_1;
  else if (waveFrame == 1 || waveFrame == 3) frameData = pika_wave_2;
  else frameData = pika_wave_3;
#else
  frameData = (waveFrame % 2 == 0) ? avatar_wave_1 : avatar_wave_2;
#endif

  if (frameData != NULL) {
    faceSprite.fillSprite(COLOR_BG);
    faceSprite.pushImage(0, 0, 128, 128, frameData);
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
    // Retry NTP periodically
    unsigned long now = millis();
    if (now - lastNtpRetryMs > NTP_RETRY_INTERVAL_MS) {
      configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.google.com", "time.nist.gov");
      lastNtpRetryMs = now;
      Serial.println("[NTP] Retrying time sync...");
    }

    // Custom HUD Border Outline
    tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
    tft.drawRect(4, 4, 120, 152, COLOR_BG);

    tft.setTextColor(TFT_WHITE, COLOR_BG);
    tft.setTextSize(1);
    tft.setCursor(24, 55);
    tft.println("Syncing Time...");

    tft.drawRoundRect(10, 115, 108, 30, 4, COLOR_BORDER);
    tft.setTextColor(COLOR_STATUS, COLOR_BG);
    tft.setTextSize(1);
    tft.setCursor(20, 126);
    tft.println("SYSTEM READY");
    return;
  }
  
  ntpSynced = true;
  
  // Custom HUD Border Outline
  tft.drawRect(2, 2, 124, 156, COLOR_BORDER);
  tft.drawRect(4, 4, 120, 152, COLOR_BG);
  
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
  
  tft.setTextColor(TFT_WHITE, COLOR_BG);
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
  tft.setCursor(20, 126);
  tft.println("SYSTEM READY");
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
  tft.setCursor(26, 138);
  tft.print("SYSTEM READY");
}

void updateAnimations() {
  unsigned long now = millis();
  
  // 1. CLOCK FACE STATE Updates
  if (currentState == STATE_CLOCK) {
    if (now - lastClockUpdateMs > 1000) {
      drawClockFace();
      lastClockUpdateMs = now;
    }
    
    // LDR-based theme switching (disable I2S ADC temporarily for analogRead)
    if (now - lastThemeLdrMs > 3000) {
      lastThemeLdrMs = now;
      i2s_adc_disable(I2S_NUM_0);
      cachedLdr = analogRead(LDR_PIN);
      i2s_adc_enable(I2S_NUM_0);
      
      int detectedTheme = ldrToTheme(cachedLdr);
      if (detectedTheme == pendingTheme) {
        pendingCount++;
      } else {
        pendingTheme = detectedTheme;
        pendingCount = 1;
      }
      if (pendingCount >= LDR_CONFIRM_READS
          && detectedTheme != activeTheme
          && (now - lastSwitchMs > THEME_COOLDOWN_MS)) {
        switchTheme(detectedTheme);
        lastSwitchMs = now;
        needRedraw = true;
      }
    }
    
    if (now > nextCameoTriggerMs) {
      setAppState(STATE_CAMEO);
      nextCameoTriggerMs = now + random(45000, 90000);
    }
    return;
  }
  
  // 2. CAMEO PEAKING Animation
  if (currentState == STATE_CAMEO) {
    unsigned long elapsed = now - cameoFrameStartMs;
    
    if (elapsed > 150) {
      // Pause at full-peek for 1 second
#if ACTIVE_THEME == THEME_PIKACHU
      if (cameoFrame == 4 && elapsed < 1000) return;
#else
      if (cameoFrame == 3 && elapsed < 1000) return;
#endif
      
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
      waveFrame = (waveFrame == 0) ? 1 : 0;
      
#if ACTIVE_THEME == THEME_PIKACHU
      // Advance wave frame index: 0->1->2->3->4->5 (wave cycle mapping)
      waveFrame = (waveCycleCount + 1) % 6;
#endif
      
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
    }
    
    needRedraw = false;
  }

  // 11. Alarm flashing state update
  static unsigned long lastAlarmFlashMs = 0;
  if (currentState == STATE_ALARM) {
    if (now - lastAlarmFlashMs > 250) {
      alarmFlashState = !alarmFlashState;
      lastAlarmFlashMs = now;
      needRedraw = true;
    }
    
    // Aggressive buzzer: 100ms toggle (5Hz) for 10 seconds
    if (buzzerActive) {
      unsigned long elapsed = now - buzzerStartMs;
      if (elapsed < 10000) {
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
        Serial.println("[BUZZER] Buzzer stopped after 10 seconds");
        setAppState(STATE_CLOCK);  // Auto-dismiss alarm after buzzer stops
        return;
      }
    }
    
    // Hard 30-second timeout as backup
    if (now - stateTimerMs > 30000) {
      Serial.println("[ALARM] Auto-dismissed after 30s timeout");
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
#define BUBBLE_LINES_MAX 20
#define BUBBLE_LINES_PER_PAGE 5
String bubbleLines[BUBBLE_LINES_MAX];
int bubbleLineCount = 0;

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
  lastBubbleText = text;
  
  // Paginate if needed
  if (bubbleLineCount == 0) {
    paginateText(text);
  }
  
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

// Forward declarations for audio timer (defined after setup)
static hw_timer_t *audioTimer = NULL;
void IRAM_ATTR audioTimerISR();

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Disable brownout detector
  
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BOOT_BTN, INPUT_PULLUP);  // BOOT button for text pagination
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  
  // Setup LEDC channel 0 for buzzer/speaker
  ledcSetup(0, 1000, 8);  // channel 0, 1kHz base, 8-bit resolution
  ledcAttachPin(BUZZER_PIN, 0);
  ledcWriteTone(0, 0);    // Silent by default

  tft.init();
  tft.setRotation(2); // Rotate to Portrait 128x160
  tft.setSwapBytes(true);
  
  // Create 128x110 Sprite
  faceSprite.createSprite(128, 110);
  faceSprite.setSwapBytes(true);
  
  tft.fillScreen(COLOR_BG);
  tft.setTextColor(TFT_WHITE, COLOR_BG);
  tft.setTextSize(1);
  tft.setCursor(10, 10);
  tft.println("Connecting...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("WiFi Connected! IP Address: ");
  Serial.println(WiFi.localIP());

  configTime(gmtOffset_sec, daylightOffset_sec, "pool.ntp.org", "time.google.com", "time.nist.gov");

  client.setTimeout(2);
  setupI2S();

  // Create audio timer once — never destroy/recreate it
  audioTimer = timerBegin(1, 80, true);
  timerAttachInterrupt(audioTimer, &audioTimerISR, true);
  timerAlarmWrite(audioTimer, 125, true);  // 1MHz/125 = 8kHz

  tft.fillScreen(COLOR_BG);
  setAppState(STATE_CLOCK);
}

// --- Non-blocking audio playback via hardware timer + DAC (GPIO 25) ---
static uint8_t *audioBuf = NULL;
static volatile uint32_t audioPlayLen = 0;
static volatile uint32_t audioPlayIdx = 0;
static volatile bool audioPlaying = false;

void IRAM_ATTR audioTimerISR() {
  if (!audioPlaying || audioPlayIdx >= audioPlayLen) {
    audioPlaying = false;
    return;
  }
  uint8_t raw = audioBuf[audioPlayIdx++];
  // Software gain: center at 128, amplify 3x, clamp
  int16_t boosted = ((int16_t)raw - 128) * 3 + 128;
  if (boosted > 255) boosted = 255;
  if (boosted < 0) boosted = 0;
  dac_output_voltage(DAC_CHANNEL_1, (uint8_t)boosted);
}

void playAudioStart(const uint8_t* buf, uint32_t len) {
  playAudioStop();
  audioBuf = (uint8_t *)malloc(len);
  if (!audioBuf) return;
  memcpy(audioBuf, buf, len);

  audioPlayLen = len;
  audioPlayIdx = 0;
  audioPlaying = true;

  dac_output_enable(DAC_CHANNEL_1);
  timerAlarmEnable(audioTimer);
  Serial.printf("[AUDIO] Playing %u bytes at 8kHz\n", len);
}

void playAudioStop() {
  audioPlaying = false;
  timerAlarmDisable(audioTimer);
  if (audioBuf) {
    free(audioBuf);
    audioBuf = NULL;
  }
  dac_output_disable(DAC_CHANNEL_1);
}

void loop() {
  updateAnimations();

  if (!client.connected()) {
    if (!client.connect(SERVER_IP, SERVER_PORT)) {
      Serial.println("Connection failed...");
      delay(2000);
      return;
    }
    client.setNoDelay(true); 
    setAppState(STATE_CLOCK);
  }

  // Check Button State for manual wake up
  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  if (buttonPressed && !isRecording) {
    isRecording = true;
    client.print("CMD:WOKE\n");
    setAppState(STATE_WAVING_INTRO);
    delay(50); // Debounce
  } 
  else if (!buttonPressed && isRecording) {
    isRecording = false;
    client.print("___END___");
    delay(50); // Debounce
  }

  // BOOT button: paginate text or clear when no more pages
  if (currentState == STATE_SPEAKING || currentState == STATE_ALARM) {
    bool bootPressed = (digitalRead(BOOT_BTN) == LOW);
    if (bootPressed && !lastBootBtnState) {
      textPage++;
      if (textPage >= textTotalPages) {
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

  // Stream Audio continuously when in clock, idle, listening, or alarm states
  // We use non-blocking I2S reading (timeout 0) so animations remain smooth
  bool shouldStream = (currentState == STATE_CLOCK || currentState == STATE_IDLE || currentState == STATE_LISTENING || currentState == STATE_ALARM);
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
          
          client.write((const uint8_t*)pcm_buffer, pcm_index * 2);
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
      if (response.startsWith("AUDIO:")) {
        uint32_t audioLen = response.substring(6).toInt();
        if (audioLen > 0 && audioLen < 200000) {
          uint8_t* tmpBuf = (uint8_t*)malloc(audioLen);
          if (tmpBuf) {
            uint32_t bytesRead = 0;
            unsigned long timeout = millis() + 10000;
            while (bytesRead < audioLen && millis() < timeout) {
              int n = client.read(tmpBuf + bytesRead, audioLen - bytesRead);
              if (n > 0) bytesRead += n;
              else delay(1);
            }
            playAudioStart(tmpBuf, bytesRead);
            free(tmpBuf);
          }
        }
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
        setAppState(STATE_CLOCK);
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
        String listContent = response.substring(8);
        listContent.replace("|", " "); // replace pipe with space for wrapping
        currentResponseText = listContent;
        speakingStartMs = millis();
        speakingDuration = 12000UL; // Display reminders for 12 seconds
        setAppState(STATE_SPEAKING);
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
