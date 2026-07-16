/*
 * network.ino - Handles WiFi configuration, UDP beacons, and TCP client socket data streams
 */

unsigned long serverDuration = 0;

void handleSetup() {
  if (webServer.hasArg("ssid") && webServer.hasArg("password") && webServer.hasArg("server_ip")) {
    String newSsid = webServer.arg("ssid");
    String newPassword = webServer.arg("password");
    String newServerIp = webServer.arg("server_ip");

    preferences.begin("wifi-config", false);
    preferences.putString("ssid", newSsid);
    preferences.putString("password", newPassword);
    preferences.putString("serverIp", newServerIp);
    preferences.end();

    webServer.send(200, "text/plain", "SUCCESS: Configuration saved. Restarting...");
    
    Serial.printf("[Config] Saved new config - SSID: %s, Server IP: %s\n", newSsid.c_str(), newServerIp.c_str());

    shouldReboot = true;
    rebootTimerMs = millis();
  } else {
    webServer.send(400, "text/plain", "ERROR: Missing parameters");
  }
}

void handleStatus() {
  String statusJson = "{\"status\":\"ConfigMode\",\"ssid\":\"" + activeSsid + "\",\"server_ip\":\"" + activeServerIp + "\"}";
  webServer.send(200, "application/json", statusJson);
}

void startAPConfigMode() {
  isConfigMode = true;
  WiFi.disconnect(true);
  WiFi.mode(WIFI_AP);
  WiFi.softAP("Table-Bondhu-Config");
  
  Serial.println("[Config] softAP 'Table-Bondhu-Config' started.");

  tft.fillScreen(COLOR_BG);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  
  tft.fillRoundRect(5, 5, 118, 30, 4, COLOR_BUBBLE_BG);
  tft.drawRoundRect(5, 5, 118, 30, 4, COLOR_BORDER);
  tft.setTextSize(1);
  tft.setTextColor(COLOR_ACCENT, COLOR_BUBBLE_BG);
  tft.setCursor(18, 16);
  tft.print("CONFIG PORTAL");

  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(10, 45);
  tft.print("1. Connect to WiFi:");
  tft.setCursor(10, 60);
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.print("'Table-Bondhu-Config'");
  
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(10, 85);
  tft.print("2. Open Mobile App");
  tft.setCursor(10, 100);
  tft.print("   to configure.");

  tft.setCursor(10, 125);
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.print("AP IP: 192.168.4.1");

  webServer.on("/setup", HTTP_POST, handleSetup);
  webServer.on("/status", HTTP_GET, handleStatus);
  webServer.begin();
}

void discoverServerIp() {
  Serial.println("[Discovery] Listening for UDP beacon on port 9999...");
  udp.begin(UDP_PORT);
  unsigned long startSearchMs = millis();
  bool found = false;

  tft.fillScreen(COLOR_BG);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setTextSize(1);
  tft.setCursor(10, 20);
  tft.println("Syncing with");
  tft.setCursor(10, 35);
  tft.println("Companion Server...");
  tft.setCursor(10, 60);
  tft.setTextColor(COLOR_ACCENT, COLOR_BG);
  tft.println("Scanning network...");

  while (millis() - startSearchMs < 5000) { // Scan for max 5 seconds
    int packetSize = udp.parsePacket();
    if (packetSize) {
      char buffer[255];
      int len = udp.read(buffer, 255);
      if (len > 0) {
        buffer[len] = 0;
      }
      String msg = String(buffer);
      if (msg.indexOf("TABLE_BONDHU_BEACON") >= 0 || msg.indexOf("TABLE_BONDHU_SERVER:") >= 0) {
        // Extract server IP address
        if (msg.indexOf(":") >= 0) {
          activeServerIp = msg.substring(msg.indexOf(":") + 1);
        } else {
          activeServerIp = udp.remoteIP().toString();
        }
        Serial.printf("[Discovery] Found Server IP: %s\n", activeServerIp.c_str());
        found = true;
        break;
      }
    }
    delay(50);
  }

  udp.stop();
  if (!found) {
    Serial.printf("[Discovery] UDP scan timed out. Using fallback IP: %s\n", activeServerIp.c_str());
  }
}

void updateNetworkConnection() {
  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastServerConnectAttemptMs > 10000) { // Retry every 10 seconds
      lastServerConnectAttemptMs = now;
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("[TCP] Reconnecting to server...");
        if (client.connect(activeServerIp.c_str(), SERVER_PORT)) {
          client.setNoDelay(true);
          Serial.println("[TCP] Connected successfully!");
          setAppState(STATE_CLOCK);
        }
      }
    }
  }
}

void processIncomingData() {
  if (client.available()) {
    String response = client.readStringUntil('\n');
    response.trim();
    
    if (response.length() > 0) {
      // Alarm Timer Guard checks
      bool timerActive = (currentState == STATE_TIMER || currentState == STATE_TIMER_PAUSED || currentState == STATE_TIMER_FINISHED);
      bool isTimerCmd = response.startsWith("TIMER_") || response.startsWith("WEATHER:");
      
      if (timerActive && !isTimerCmd) {
        Serial.printf("[Guard] Rejected command during timer: %s\n", response.c_str());
        return;
      }

      if (response == "UI_STATE:LISTENING" || response.startsWith("CMD:WOKE")) {
        serverDuration = 0;
        setAppState(STATE_WAVING_INTRO);
      }
      else if (response == "UI_STATE:GREETING") {
        serverDuration = 0;
        setAppState(STATE_WAVING_INTRO);
      }
      else if (response == "UI_STATE:THINKING" || response.startsWith("CMD:THINKING")) {
        serverDuration = 0;
        setAppState(STATE_THINKING);
      }
      else if (response == "UI_STATE:IDLE") {
        serverDuration = 0;
        if (currentState != STATE_TIMER && currentState != STATE_TIMER_PAUSED && currentState != STATE_TIMER_FINISHED) {
          setAppState(STATE_CLOCK);
        }
      }
      else if (response == "CMD:START_SLEEP") {
        setAppState(STATE_SLEEPING);
      }
      else if (response == "CMD:FORCE_WAKE") {
        if (currentState == STATE_SLEEPING || currentState == STATE_SLEEPING_PREWAKE) {
          preWakeRisingEdges = 0;
          setAppState(STATE_CLOCK);
          if (client.connected()) {
            client.print("PIR:WAKE\n");
          }
        }
      }
      else if (response.startsWith("SLEEP_WINDOW:")) {
        // e.g. SLEEP_WINDOW:22:10
        int colon = response.indexOf(':', 13);
        if (colon != -1) {
          int start = response.substring(13, colon).toInt();
          int end = response.substring(colon + 1).toInt();
          if (start >= 0 && start <= 23 && end >= 0 && end <= 23) {
            sleepWindowStartHour = start;
            sleepWindowEndHour = end;
          }
        }
      }
      else if (response.startsWith("UI_SLEEP_SUMMARY:")) {
        // e.g. UI_SLEEP_SUMMARY:type:duration:movements:avg_noise:avg_ldr:quality
        int c1 = response.indexOf(':', 17);
        int c2 = response.indexOf(':', c1 + 1);
        int c3 = response.indexOf(':', c2 + 1);
        int c4 = response.indexOf(':', c3 + 1);
        int c5 = response.indexOf(':', c4 + 1);
        
        if (c1 != -1 && c2 != -1 && c3 != -1 && c4 != -1 && c5 != -1) {
          sleepSummaryType = response.substring(17, c1);
          sleepSummaryDuration = response.substring(c1 + 1, c2).toFloat();
          sleepSummaryMovements = response.substring(c2 + 1, c3).toInt();
          sleepSummaryAvgNoise = response.substring(c3 + 1, c4).toFloat();
          sleepSummaryAvgLdr = response.substring(c4 + 1, c5).toInt();
          sleepSummaryQuality = response.substring(c5 + 1);
          
          sleepSummaryType.trim();
          sleepSummaryQuality.trim();
          sleepSummaryStartMs = millis();
          setAppState(STATE_SLEEP_SUMMARY);
        }
      }
      else if (response.startsWith("TIMER_START:")) {
        timerSecondsLeft = response.substring(12).toInt();
        lastTimerTickMs = millis();
        setAppState(STATE_TIMER);
      }
      else if (response == "TIMER_PAUSE") {
        setAppState(STATE_TIMER_PAUSED);
      }
      else if (response == "TIMER_RESUME") {
        lastTimerTickMs = millis();
        setAppState(STATE_TIMER);
      }
      else if (response == "TIMER_CANCEL" || response == "TIMER_STOP") {
        ledcWriteTone(0, 0);
        setAppState(STATE_CLOCK);
      }
      else if (response.startsWith("WEATHER:")) {
        int c1 = response.indexOf(':', 8);
        int c2 = response.indexOf(':', c1 + 1);
        if (c1 != -1 && c2 != -1) {
          weatherTemp = response.substring(8, c1).toInt();
          weatherDesc = response.substring(c1 + 1, c2);
          weatherIconIdx = response.substring(c2 + 1).toInt();
          hasWeather = true;
          needRedraw = true;
        }
      }
      else if (response.startsWith("UI_ALARM:")) {
        serverDuration = 0;
        String alarmName = response.substring(9);
        alarmName.trim();
        // Setup speaker active buzzer alarm values
        setAppState(STATE_ALARM);
        // trigger buzzer driving in audio module
      }
    }
  }
}
