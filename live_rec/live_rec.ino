#include <WiFi.h>
#include <TFT_eSPI.h>
#include <driver/i2s.h>
#include "config.h"

// Configuration is now loaded from config.h

#define I2S_SAMPLE_RATE 16000

TFT_eSPI tft = TFT_eSPI();
WiFiClient client;

// Audio Filter Variables
float dc_filter_y = 0;
float dc_filter_x = 0;

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

void setup() {
  Serial.begin(115200);

  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(0, 0);
  tft.println("Connecting WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  tft.fillScreen(TFT_BLACK);
  tft.setCursor(0, 0);
  tft.println("WiFi Connected!");
  tft.println("Live Streaming...");

  setupI2S();
}

void loop() {
  // Ensure connection to Python server
  if (!client.connected()) {
    if (!client.connect(SERVER_IP, SERVER_PORT)) {
      Serial.println("Connection failed. Retrying...");
      tft.fillScreen(TFT_BLACK);
      tft.setCursor(0, 0);
      tft.setTextColor(TFT_RED);
      tft.println("Disconnected.");
      delay(2000);
      return;
    }
    client.setNoDelay(true); 
    
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(0, 0);
    tft.setTextColor(TFT_GREEN);
    tft.println("Live Streaming...");
  }

  // --- 1. CONTINUOUSLY READ AND SEND AUDIO ---
  size_t bytes_read;
  uint16_t i2s_buffer[1024];
  int16_t pcm_buffer[512]; 

  i2s_read(I2S_NUM_0, &i2s_buffer, sizeof(i2s_buffer), &bytes_read, portMAX_DELAY);

  int total_samples = bytes_read / 2;
  int pcm_index = 0;

  for (int i = 0; i < total_samples; i += 2) {
    uint16_t raw_sample = i2s_buffer[i] & 0x0FFF; 
    
    float x = (float)raw_sample;
    dc_filter_y = x - dc_filter_x + 0.995 * dc_filter_y;
    dc_filter_x = x;

    float scaled_audio = dc_filter_y * 12.0;
    if (scaled_audio > 32767.0) scaled_audio = 32767.0;
    if (scaled_audio < -32768.0) scaled_audio = -32768.0;

    pcm_buffer[pcm_index++] = (int16_t)scaled_audio; 
  }

  // Send the live chunk
  client.write((const uint8_t*)pcm_buffer, pcm_index * 2);

  // --- 2. CHECK FOR INCOMING TRANSCRIPTIONS ---
  if (client.available()) {
    String response = client.readStringUntil('\n');
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(0, 0);
    
    tft.setTextColor(TFT_YELLOW);
    tft.println("Heard:");
    
    tft.setTextColor(TFT_WHITE);
    tft.setTextWrap(true);
    tft.println(response);
  }
}