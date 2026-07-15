# Table-Bondhu Testing & Diagnostics Guide (`TESTING.md`)

This document records the diagnostic scripts, manual verification tests, and mock testing strategies used to validate the Table-Bondhu client-server system.

---

## 1. Local API Verification (`check_api.py`)

A utility script `check_api.py` is included in the project root. This script allows you to test the connection to the local LM Studio instance and verify that it is responding correctly before launching the main server:

```python
# --- LM Studio REST Check (check_api.py: Lines 1 - 25) ---
import requests

def test_api():
    url = "http://localhost:1234/v1/chat/completions"
    payload = {
        "model": "qwen2.5-coder-1.5b-instruct",
        "messages": [
            {"role": "system", "content": "You are a cute assistant. Answer in under 5 words."},
            {"role": "user", "content": "Hello!"}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.statusCode == 200:
            print("[+] Connection to LM Studio successful!")
            print(f"Response: {response.json()['choices'][0]['message']['content']}")
        else:
            print(f"[-] Error: Server returned status code {response.statusCode}")
    except Exception as e:
        print(f"[-] Connection failed: {e}")

if __name__ == "__main__":
    test_api()
```

---

## 2. Server REST Endpoint Validation (CURL)

You can test the companion server's REST endpoints manually using standard CURL commands in the terminal (ensure the server is running on `localhost:8888`):

### A. Add a Reminder:
```bash
curl -X POST http://localhost:8888/api/reminders \
  -H "Content-Type: application/json" \
  -d "{\"task\": \"Water the plants\", \"time\": \"2026-07-16 18:30:00\"}"
```

### B. Delete a Reminder:
```bash
curl -X POST http://localhost:8888/api/reminders/delete \
  -H "Content-Type: application/json" \
  -d "{\"index\": 1}"
```

### C. Fetch Sleep Status:
```bash
curl -X GET http://localhost:8888/api/sleep/status
```

---

## 3. Manual Hardware & Sensors Verification

To verify that the sensors and hardware components are working correctly, open the Arduino Serial Monitor (set to `115200` baud) and run the following checks:

### A. LDR Theme Switching Test
1. Cover the LDR sensor with your hand.
2. The serial monitor should print: `LDR value: <300` and `Switching display theme to: NIGHT`. The screen background should change to black.
3. Shine a light directly at the LDR.
4. The serial monitor should print: `LDR value: >1200` and `Switching display theme to: BRIGHT`. The screen background should change to white.

### B. Active Alarm Trigger Test
1. Set an alarm using the mobile app or a voice command (e.g. *"Alarm in 1 minute"*).
2. Wait for the scheduled time.
3. The server console should log: `[ALARM] Triggered!`. The ESP32 screen should flash red, and the active buzzer should start buzzing.
4. Press the tactile button (D14) or say *"stop"* to verify that the alarm silences immediately.

### C. Auto-Sleep Gating Test
1. Verify that the current local time falls within the sleep window configured in the app.
2. Turn off the room lights (so the LDR reads `< 500`) and remain still for 120 seconds.
3. The display should enter sleep mode and turn black, and the serial monitor should print: `Entering SLEEPING state`.
4. Walk in front of the PIR sensor or wave your hand.
5. The screen should wake up and display the clock again.

---

## 4. Evidence Paths
*   LM Studio connection check script: [check_api.py](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/check_api.py)
*   REST endpoint handlers: [agentic_companion.py#L1681-L1947](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1681-L1947)
*   LDR analog read: [gemini_LLM_btn.ino#L816](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L816)
*   PIR wake detection logic: [gemini_LLM_btn.ino#L1796-L1815](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1796-L1815)
