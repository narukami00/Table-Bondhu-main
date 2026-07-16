/*
 * sensors.ino - Handles reading physical sensors (LDR, PIR, Buttons)
 */

bool lastButtonState = false;
bool lastBootBtnState = false;

void readSensors() {
  unsigned long now = millis();

  // 1. Read LDR (Light Dependent Resistor) & trigger theme transition
  // We only run this in STATE_CLOCK to avoid disrupting active mic streaming
  if (currentState == STATE_CLOCK) {
    if (now - lastThemeLdrMs > 1500) {
      lastThemeLdrMs = now;
      
      // Stop I2S ADC DMA controller temporarily during analogRead to prevent noise/clashes
      i2s_stop(I2S_NUM_0);
      i2s_adc_disable(I2S_NUM_0);
      cachedLdr = analogRead(LDR_PIN);
      i2s_adc_enable(I2S_NUM_0);
      i2s_start(I2S_NUM_0);
      
      if (client.connected()) {
        client.print("LDR:" + String(cachedLdr) + "\n");
      }
      
      int targetTheme = ldrToTheme(cachedLdr);
      if (targetTheme != activeTheme && (now - lastSwitchMs > THEME_COOLDOWN_MS)) {
        switchTheme(targetTheme);
        lastSwitchMs = now;
      }
    }
  }

  // 2. Read PIR Motion Sensor with software debouncing/RF noise filtering
  bool pirRaw = (digitalRead(PIR_PIN) == HIGH);
  static unsigned long pirHighStartMs = 0;
  bool pirDebounced = false;

  if (pirRaw) {
    if (pirHighStartMs == 0) {
      pirHighStartMs = now;
    } else if (now - pirHighStartMs >= 200) { // must hold for 200ms
      pirDebounced = true;
    }
  } else {
    pirHighStartMs = 0;
    pirDebounced = false;
  }

  if (pirDebounced) {
    lastPirMotionMs = now;
  }

  // 3. Read D14 Tactile Button (GND + D14 -> Active Low)
  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  // Trigger wake-up or recording start on button down edge
  if (buttonPressed && !lastButtonState) {
    buttonPressStartMs = now;
    buttonHeldProcessed = false;

    if (currentState != STATE_TIMER && currentState != STATE_TIMER_PAUSED && currentState != STATE_TIMER_FINISHED) {
      if (client.connected()) {
        client.print("CMD:WOKE\n");
      }
      setAppState(STATE_WAVING_INTRO);
    }
  }

  // Handle button hold events for timer cancellation
  if (buttonPressed && lastButtonState && !buttonHeldProcessed) {
    if (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED) {
      if (now - buttonPressStartMs > 1000) { // 1.0 second hold
        buttonHeldProcessed = true;
        
        ledcWriteTone(0, 0); // Silence local buzzer
        timerSecondsLeft = 0;
        
        if (client.connected()) {
          client.print("TIMER_DONE\n");
        }
        setAppState(STATE_CLOCK);
        Serial.println("[TIMER] Button held: timer cancelled.");
      }
    }
  }

  // Handle button release events
  if (!buttonPressed && lastButtonState) {
    if (currentState == STATE_WAVING_INTRO || currentState == STATE_LISTENING) {
      // Finished speaking, send trailing boundary marker to tell server to process ASR
      if (client.connected()) {
        client.print("___END___\n");
      }
    } else if (!buttonHeldProcessed) {
      // Short press toggles or dismisses timer
      if (currentState == STATE_TIMER) {
        setAppState(STATE_TIMER_PAUSED);
      } else if (currentState == STATE_TIMER_PAUSED) {
        lastTimerTickMs = millis();
        setAppState(STATE_TIMER);
      } else if (currentState == STATE_TIMER_FINISHED) {
        ledcWriteTone(0, 0);
        setAppState(STATE_CLOCK);
      }
    }
    buttonHeldProcessed = false;
  }
  lastButtonState = buttonPressed;

  // 4. Read BOOT button (GPIO 0) for text bubble paging
  bool bootPressed = (digitalRead(BOOT_BTN) == LOW);
  if (bootPressed && !lastBootBtnState) {
    if (currentState == STATE_SPEAKING || currentState == STATE_REMINDERS) {
      // trigger page navigation inside rendering module
      textPage++;
      needRedraw = true;
    }
  }
  lastBootBtnState = bootPressed;
}
