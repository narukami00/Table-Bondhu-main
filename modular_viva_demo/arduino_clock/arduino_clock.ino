/*
 * Table-Bondhu Modular Demo Firmware (arduino_clock.ino)
 * Core entry point containing declarations, setup(), and loop()
 */

#include <WiFi.h>
#include <TFT_eSPI.h>
#include <driver/i2s.h>
#include <time.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <Preferences.h>
#include <WebServer.h>
#include <WiFiUdp.h>

#include "config.h"
#include "states.h"

// --- HARDWARE CONFIGURATION PINOUTS ---
#define BUTTON_PIN 14 // Tactile Button (GND + D14)
#define BOOT_BTN 0    // Built-in BOOT button for text pagination
#define LDR_PIN 34    // ADC1_CH6 - Light Dependent Resistor
#define BUZZER_PIN 13 // Active Buzzer (HIGH = sound)
#define PIR_PIN 27    // PIR Motion Sensor (digital OUT)
#define I2S_SAMPLE_RATE 16000

// Theme selection macros
#define THEME_GIRL 0
#define THEME_PIKACHU 1
#define ACTIVE_THEME THEME_PIKACHU

// Default color parameters
#define DEFAULT_BG 0x18E6
#define DEFAULT_ACCENT 0xFEE0
#define DEFAULT_BORDER 0xFEE0
#define DEFAULT_BUBBLE_BG TFT_BLACK
#define DEFAULT_TEXT TFT_WHITE
#define DEFAULT_STATUS TFT_RED
#define ASSET_BG 0x18E6

#include "images.h"

Preferences preferences;
WebServer webServer(80);
WiFiUDP udp;

// WiFi network state variables
String activeSsid = "";
String activePassword = "";
String activeServerIp = "";
bool isConfigMode = false;
bool shouldReboot = false;
unsigned long rebootTimerMs = 0;

// Runtime color variables (updated dynamically via theme switches)
uint16_t COLOR_BG = DEFAULT_BG;
uint16_t COLOR_ACCENT = DEFAULT_ACCENT;
uint16_t COLOR_BORDER = DEFAULT_BORDER;
uint16_t COLOR_BUBBLE_BG = DEFAULT_BUBBLE_BG;
uint16_t COLOR_TEXT = DEFAULT_TEXT;
uint16_t COLOR_STATUS = DEFAULT_STATUS;

// 4-level theme definitions
struct ThemePalette {
  uint16_t bg, accent, border, bubbleBg, text, status;
};

const ThemePalette THEMES[4] = {
  { 0x0000, 0xFFE0, 0xFFE0, 0x0000, 0xFFFF, 0xFFE0 },  // Night: black bg, yellow accent
  { 0x000F, 0x867D, 0x867D, 0x000A, 0xFFFF, 0x867D },  // Dusk: navy bg, light blue accent
  { 0xFD00, 0x3800, 0x3800, 0xFFFF, 0x0000, 0x3800 },  // Autumn: orange bg, brown accent
  { 0xFFFF, 0x001F, 0x001F, 0xFFFF, 0x001F, 0x001F }   // Bright: white bg, blue text
};

int activeTheme = 3;  // Start at Bright
unsigned long lastSwitchMs = 0;
unsigned long lastThemeLdrMs = 0;
int cachedLdr = 2048;

// Weather variables
int weatherTemp = 25;
String weatherDesc = "SUNNY";
int weatherIconIdx = 0;
bool hasWeather = false;

// Timer & alarm variables
int timerSecondsLeft = 0;
unsigned long lastTimerTickMs = 0;
unsigned long buttonPressStartMs = 0;
bool buttonHeldProcessed = false;
unsigned long lastServerConnectAttemptMs = 0;

// PIR motion variables
unsigned long lastPirMotionMs = 0;
const unsigned long SLEEP_TIMEOUT_MS = 120000; // 2 minutes

// Bedtime configuration hours
int sleepWindowStartHour = 22;   // 10 PM
int sleepWindowEndHour   = 10;   // 10 AM

// Sleep tracking variables
unsigned long clockStateEnteredMs = 0;
unsigned long preWakeEnteredMs = 0;
unsigned long lastSleepHeartbeatMs = 0;
int preWakeRisingEdges = 0;
unsigned long lastSleepEnteredMs = 0;
int sleepAnimState = 0;
unsigned long lastSleepAnimUpdateMs = 0;
bool sleepFrameToggle = false;
unsigned long sleepSmileStartMs = 0;
unsigned long nextSleepSmileTriggerMs = 0;
unsigned long lastSleepClockUpdateMs = 0;

// Sleep summary statistics
String sleepSummaryType = "Sleep";
float sleepSummaryDuration = 0.0f;
int sleepSummaryMovements = 0;
float sleepSummaryAvgNoise = 0.0f;
int sleepSummaryAvgLdr = 0;
String sleepSummaryQuality = "Good";
unsigned long sleepSummaryStartMs = 0;

// Render control
bool needRedraw = true;
static uint16_t *themedBuf = NULL;

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite faceSprite = TFT_eSprite(&tft);
TFT_eSprite cameoSprite = TFT_eSprite(&tft);
WiFiClient client;

AppState currentState = STATE_CLOCK;

// --- EXTERNAL COMPONENT DECLARATIONS (Implemented in Sub-Files) ---
void setupI2S();
void setupWebServer();
void discoverServerIp();
void startAPConfigMode();
void readSensors();
void updateNetworkConnection();
void processIncomingData();
void renderDisplay();
void soundBuzzer();
void setAppState(AppState newState);

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Disable brownout resets
  
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BOOT_BTN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT_PULLDOWN);
  digitalWrite(BUZZER_PIN, LOW);
  
  lastPirMotionMs = millis();
  
  // Audio alarm PWM setup
  ledcSetup(0, 1000, 8);
  ledcAttachPin(BUZZER_PIN, 0);
  ledcWriteTone(0, 0);

  tft.init();
  tft.setRotation(2); // Portrait 128x160
  tft.setSwapBytes(true);

  // Check if D14 is held to factory reset credentials
  if (digitalRead(BUTTON_PIN) == LOW) {
    tft.fillScreen(COLOR_BG);
    tft.setTextColor(COLOR_TEXT, COLOR_BG);
    tft.setCursor(10, 20);
    tft.print("Keep holding to");
    tft.setCursor(10, 35);
    tft.print("reset WiFi...");
    
    delay(2000);
    if (digitalRead(BUTTON_PIN) == LOW) {
      Serial.println("[Config] Clearing credentials.");
      preferences.begin("wifi-config", false);
      preferences.clear();
      preferences.end();
      startAPConfigMode();
      return;
    }
  }

  // Load WiFi configurations
  preferences.begin("wifi-config", true);
  activeSsid = preferences.getString("ssid", WIFI_SSID);
  activePassword = preferences.getString("password", WIFI_PASSWORD);
  activeServerIp = preferences.getString("serverIp", SERVER_IP);
  preferences.end();
  
  faceSprite.createSprite(128, 110);
  faceSprite.setSwapBytes(true);
  
  tft.fillScreen(COLOR_BG);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(10, 10);
  tft.println("Connecting...");

  themedBuf = (uint16_t *)malloc(128 * 160 * sizeof(uint16_t));
  if (!themedBuf) {
    Serial.println("[FATAL] themedBuf allocation failed");
    while(1) delay(1000);
  }

  WiFi.begin(activeSsid.c_str(), activePassword.c_str());
  int attempts = 0;
  tft.setCursor(10, 30);
  tft.printf("SSID: %s", activeSsid.c_str());
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] Connected! Local IP: ");
    Serial.println(WiFi.localIP());
    // Sync NTP clock time
    configTime(21600, 0, "pool.ntp.org", "time.google.com");
    discoverServerIp();
  } else {
    Serial.println("[WiFi] Connection failed. Booting AP configuration.");
    startAPConfigMode();
    return;
  }

  client.setTimeout(2);
  setupI2S();
  tft.fillScreen(COLOR_BG);
  setAppState(STATE_CLOCK);
}

void loop() {
  if (isConfigMode) {
    webServer.handleClient();
    if (shouldReboot && (millis() - rebootTimerMs > 2000)) {
      ESP.restart();
    }
    return; // config mode skips normal logic
  }

  // 1. Monitor sensors (LDR values, PIR motion transitions, Buttons)
  readSensors();

  // 2. Maintain TCP link connection to Python server
  updateNetworkConnection();

  // 3. Process commands received from Python server
  processIncomingData();

  // 4. Handle alarm buzzers or focus timers
  soundBuzzer();

  // 5. Update double buffers and push frames to screen
  renderDisplay();
}
