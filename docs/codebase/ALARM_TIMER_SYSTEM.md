# Table-Bondhu Alarm, Reminder & Focus Timer System (`ALARM_TIMER_SYSTEM.md`)

This document provides a low-level, technical breakdown of the scheduling daemon, database locks, time parsing engines, and firmware countdown states used in the Table-Bondhu project.

---

## 1. Alarms vs. Reminders: Conceptual Distinction

*   **Reminders:** Passive calendar events. They are saved in `reminders.json` with a description and target timestamp. The client can view active reminders as a paginated list on the TFT screen (`STATE_REMINDERS`) or in the Android App's Reminders tab.
*   **Alarms:** Active events. The background thread monitors active reminders. When a reminder's time is reached, it is marked as `fired = true` and converted into an alarm. The server sends a command to the ESP32 client (`UI_ALARM:taskName`), which triggers the buzzer and plays a sound over the laptop speaker.

---

## 2. Server-Side Scheduler & Thread Safety

All reminders are saved in `reminders.json`. Since multiple threads can read or write to this file simultaneously (e.g. the REST API thread, the TCP server connection handler, and the background scheduler thread), we implement a **thread-safety lock** (`db_lock`) to prevent file corruption.

```
                  ┌──────────────────────┐
                  │   REST API thread    │
                  └──────────┬───────────┘
                             │ Acquires db_lock
                             ▼
┌──────────────┐       ┌──────────┐       ┌──────────────────────┐
│ reminders.json │ ◄───┤  db_lock ├───► │   TCP Server Thread  │
└──────────────┘       └──────────┘       └──────────────────────┘
                             ▲
                             │ Acquires db_lock
                             │
                  ┌──────────┴───────────┐
                  │  Scheduler Thread    │
                  └──────────────────────┘
```

The background thread `alarm_scheduler` runs a loop checking for reminders that need to be triggered:

```python
# --- Alarm Polling Loop (agentic_companion.py: Lines 702 - 729) ---
def alarm_scheduler():
    global active_alarm_active, active_alarm_name, active_conn, alarm_fired_at
    while True:
        try:
            now = datetime.datetime.now()
            with db_lock:
                reminders = _load_reminders_internal()
                updated = False
                for r in reminders:
                    if r.get("fired", False):
                        continue
                    trigger_dt = datetime.datetime.fromisoformat(r["trigger_time"])
                    
                    if now >= trigger_dt:
                        r["fired"] = True // Mark as fired so it doesn't trigger again
                        updated = True
                        active_alarm_active = True
                        active_alarm_name = r.get("task", "Alarm")
                        alarm_fired_at = now
                        
                if updated:
                    _save_reminders_internal(reminders)
            # ... Play alarm sounds and notify the ESP32 over TCP ...
            time.sleep(1.0)
```

---

## 3. Natural Language Time Parsing

The Python server uses a time parsing engine to extract dates and times from user voice transcriptions:

```python
# --- Parse Time from Transcript (agentic_companion.py: Lines 228 - 256) ---
def parse_time_expression(phrase: str) -> datetime.datetime:
    now = datetime.datetime.now()
    phrase = phrase.lower()
    
    # 1. Handle Relative Phrases (e.g., "in 5 minutes")
    match = re.search(r'in\s+(\d+)\s+min', phrase)
    if match:
        return now + datetime.timedelta(minutes=int(match.group(1)))
        
    match = re.search(r'in\s+(\d+)\s+hour', phrase)
    if match:
        return now + datetime.timedelta(hours=int(match.group(1)))
        
    # 2. Handle Absolute Clock Times (e.g., "at 3:30 pm")
    match = re.search(r'at\s+(\d{1,2}):(\d{2})\s*(am|pm)?', phrase)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        meridiem = match.group(3)
        if meridiem == 'pm' and h < 12: h += 12
        elif meridiem == 'am' and h == 12: h = 0
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1) // Schedule for tomorrow
        return target
        
    return None
```

---

## 4. ESP32 Focus Timer State Machine

When a timer command is received (e.g., `TIMER_START:1500` for a 25-minute timer), the ESP32 switches to `STATE_TIMER` and runs a local countdown state machine.

```cpp
// --- Timer Countdown Loop (gemini_LLM_btn.ino: Lines 1445 - 1475) ---
if (currentState == STATE_TIMER) {
  if (!timerPaused) {
    unsigned long currentMs = millis();
    if (currentMs - lastTimerTickMs >= 1000) {
      lastTimerTickMs = currentMs;
      if (timerSecondsRemaining > 0) {
        timerSecondsRemaining--;
      } else {
        // Timer completed! Sound the buzzer and notify the server
        setAppState(STATE_CLOCK);
        digitalWrite(BUZZER_PIN, HIGH); // sound alarm
        delay(2000);
        digitalWrite(BUZZER_PIN, LOW);
      }
    }
  }
}
```

### Physical Button Control Flow:
*   **Tactile Button (D14) - Short Press:** Toggles the `timerPaused` state.
*   **Tactile Button (D14) - Long Press (1s+):** Aborts the timer and returns to the clock display.
*   **BOOT Button (D0):** Also aborts the active timer.

---

## 5. Active Buzzer Drive Logic

The ESP32 uses high-speed digital output to drive the buzzer. When an alarm triggers, the firmware toggles GPIO 13 to create an oscillating alarm tone:

```cpp
// --- Trigger Alarm Sound (gemini_LLM_btn.ino: Lines 1622 - 1635) ---
void soundBuzzerAlarm() {
  for (int i = 0; i < 3; i++) {
    // Generate a dual-frequency alarm tone
    digitalWrite(BUZZER_PIN, HIGH);
    delay(150);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(300);
    digitalWrite(BUZZER_PIN, LOW);
    delay(400);
  }
}
```

---

## 6. Comprehensive Teacher Viva Q&A

### Q1: Why is thread safety necessary when reading and writing `reminders.json`?
**Answer:** In modern systems, threads run concurrently. The API thread writes a new reminder to `reminders.json` when the user sets one via the app. At the same time, the background polling thread reads the file to check if any alarms need to be triggered. 
If both threads access the file at the exact same millisecond, it can lead to a write conflict, resulting in a corrupted JSON file. We use a **threading lock** (`db_lock = threading.Lock()`) to ensure only one thread can access the file at a time.

### Q2: What happens to past reminders that have already triggered? How do you prevent them from triggering again?
**Answer:** When a reminder triggers, the scheduler set its `fired` parameter to `true` and saves the updated list back to the file.
During the next check, the scheduler loops through the reminders list and ignores any elements where `fired` is `true`. This prevents the alarm from triggering repeatedly.

### Q3: Why does the focus timer countdown locally on the ESP32 instead of on the server?
**Answer:** Counting down on the server and sending updates over Wi-Fi every second would consume unnecessary network bandwidth. Any network jitter or packet loss would cause the displayed time to stutter or jump.
By counting down locally on the ESP32 using the hardware timer (`millis()`), the countdown remains accurate and smooth. The server only needs to send the start command (`TIMER_START:seconds`) and is notified once the timer completes.

### Q4: How is a long press distinguished from a short press on the physical button?
**Answer:** We measure the duration that the button pin is held LOW.
1.  When the button pin changes from HIGH to LOW, we record the starting timestamp (`buttonPressStartMs = millis()`).
2.  When the pin changes back to HIGH (button released), we calculate the duration: `duration = millis() - buttonPressStartMs`.
    *   If `duration < 50ms`, it is ignored (debounced noise).
    *   If `duration < 1000ms` (1 second), it is registered as a **short press**.
    *   If `duration >= 1000ms`, it is registered as a **long press**.

---

## 7. Evidence Paths
*   Reminder storage file name: [agentic_companion.py#L40](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L40)
*   Lock initialization: [agentic_companion.py#L41](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L41)
*   Alarm checking loop thread: [agentic_companion.py#L645-L768](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L645-L768)
*   Timer state rendering: [gemini_LLM_btn.ino#L1430-L1480](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1430-L1480)
*   Physical button press checking: [gemini_LLM_btn.ino#L1882-L1910](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1882-L1910)
