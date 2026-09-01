/*
 * audio.ino - Handles installation of I2S microphone driver and driving buzzer alarms
 */

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

void soundBuzzer() {
  unsigned long now = millis();

  if (currentState == STATE_ALARM || currentState == STATE_TIMER_FINISHED) {
    if (buzzerActive) {
      unsigned long elapsed = now - buzzerStartMs;
      // Timer finished buzzes for 60s; reminders alarm buzzes for 10s on desktop speaker backup
      unsigned long maxBuzzTime = (currentState == STATE_TIMER_FINISHED) ? 60000 : 10000;
      
      if (elapsed < maxBuzzTime) {
        // Toggle tone at 100ms interval (5Hz pulsing frequency)
        bool on = (elapsed / 100) % 2 == 0;
        ledcWriteTone(0, on ? 1000 : 0);
      } else {
        ledcWriteTone(0, 0);
        buzzerActive = false;
        setAppState(STATE_CLOCK); // auto-dismiss
      }
    }
  }
}
