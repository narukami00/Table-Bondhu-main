# Table-Bondhu Intelligent Sleep Monitoring System (`SLEEP_SYSTEM.md`)

This document provides a low-level, technical breakdown of the hardware sensor algorithms, sliding analysis windows, acoustic noise monitoring, and sleep summary calculations used in the Table-Bondhu project.

---

## 1. NTP Time Sync & Sleep Window Gating

### A. The Challenge: Daytime Away-from-Home Triggers
A simple sleep trigger that only monitors darkness and inactivity will fail if you leave home during the day with the curtains closed. The room will be dark and quiet, causing the device to enter sleep mode incorrectly.

### B. The Solution: Sleep Window Gating
The ESP32 uses NTP (Network Time Protocol) to fetch the local time over Wi-Fi. The automatic sleep state machine is gated by a configurable sleep window (default: `10 PM - 10 AM`). Outside this window, auto-sleep transitions are ignored.

```cpp
// --- Sleep Window Check (gemini_LLM_btn.ino: Lines 94 - 108) ---
bool isWithinSleepWindow() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 50)) return true; // If NTP is down, allow sleep by default
  int h = timeinfo.tm_hour;
  
  if (sleepWindowStartHour > sleepWindowEndHour) {
    // Window wraps around midnight (e.g., 22:00 to 10:00)
    return (h >= sleepWindowStartHour || h < sleepWindowEndHour);
  }
  return (h >= sleepWindowStartHour && h < sleepWindowEndHour);
}
```

---

## 2. Automatic Sleep Detection & Motion Filtering

When the device is in `STATE_CLOCK`, it monitors both light levels and physical motion.

```
                  ┌────────────────────────────────────────┐
                  │              STATE_CLOCK               │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                      1. Continuous Time > 120s?
                      2. Light Level LDR < 500?
                      3. Motion Count <= 3s (Last 30s)?
                      4. Current Time inside Sleep Window?
                                      │
                                      ├──────────► NO: Remain in Clock Mode
                                      │
                                      ▼ YES
                  ┌────────────────────────────────────────┐
                  │             STATE_SLEEPING             │
                  │  • Turns screen black                  │
                  │  • Toggles breathing animation         │
                  │  • Streams audio to monitor room noise │
                  └────────────────────────────────────────┘
```

### A. LDR Light Filtering
We read the analog light level using a voltage divider on pin 34. A value below `500` indicates a dark room.

### B. PIR Inactivity Density Array
Rather than requiring absolute silence, we check the activity density. We maintain a 30-second sliding history array of PIR triggers. Every second, we shift the array and write a `1` if motion was detected, or a `0` if not.
We sum the values in the array to find the total seconds of motion during the last 30 seconds. If the sum is **3 seconds or less**, the user is considered "mostly motionless".

```cpp
// --- PIR Inactivity Filter (gemini_LLM_btn.ino: Lines 1740 - 1762) ---
if ((currentMs - clockStateEnteredMs > SLEEP_TIMEOUT_MS) && 
    (cachedLdr < 500) && 
    (motionSeconds <= 3) &&
    isWithinSleepWindow()) {
  setAppState(STATE_SLEEPING);
  Serial.println("PIR: In Clock state, dark, motionless, and within sleep window. Entering SLEEPING state.");
}
```

---

## 3. Acoustic Noise Analysis During Sleep

Once in `STATE_SLEEPING`, the ESP32 streams raw audio to the server. The server calculates the RMS (Root Mean Square) volume of each incoming audio chunk to monitor room noise:

$$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x_i^2}$$

```python
# --- Calculate Audio RMS (agentic_companion.py: Lines 1030 - 1050) ---
audio_data = np.frombuffer(chunk, dtype=np.int16)
mean_square = np.mean(audio_data ** 2)
rms = np.sqrt(mean_square)

# Track metrics
noise_levels.append(rms)
if rms > 600: // A value above 600 indicates a loud sound event
    noise_events += 1
```

---

## 4. Pre-Wake Standby (Double-Check Guard)

To prevent the display from waking up due to minor movements (like rolling over in bed), the firmware uses a two-phase wake-up engine:

```
                            ┌────────────────┐
                            │ STATE_SLEEPING │
                            └───────┬────────┘
                                    │
                                    ▼ Motion detected
                        ┌───────────────────────┐
                        │ STATE_SLEEPING_PREWAKE│
                        └───────────┬───────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
   3 distinct motion pulses?                       4 seconds of continuous motion?
            │                                               │
            ├───────────────────────┬───────────────────────┘
            ▼ YES                   ▼ NO (after 15 seconds)
      ┌─────────────┐        ┌──────────────┐
      │ STATE_CLOCK │        │STATE_SLEEPING│ (Go back to sleep)
      └─────────────┘        └──────────────┘
```

1.  **Transition to Pre-Wake Standby:** Detecting motion moves the state from `STATE_SLEEPING` to `STATE_SLEEPING_PREWAKE`. The screen remains black.
2.  **Validation:** The system watches the PIR sensor for 15 seconds:
    *   *Sustained Motion:* Wakes if continuous motion is detected for more than 4 seconds.
    *   *Repeated Pulses:* Wakes if it detects 3 or more distinct motion pulses (motion transitions from LOW to HIGH).
    *   *Timeout:* If neither condition is met within 15 seconds, the system transitions back to `STATE_SLEEPING`.

---

## 5. Sleep Session Classification & Quality Rules

When the user wakes up, the server saves the session data and evaluates the sleep quality:

```python
# --- Sleep Quality Assessment (agentic_companion.py: Lines 1240 - 1262) ---
duration_hours = (end_time - start_time).total_seconds() / 3600.0

# Classify session type
session_type = "actual_sleep" if (duration_hours >= 4.0 or start_hour >= 22 or start_hour < 6) else "nap"

# Evaluate sleep quality
movements_per_hour = movement_count / duration_hours
avg_noise = sum(noise_levels) / len(noise_levels)

if movements_per_hour < 2.0 and avg_noise < 200:
    quality = "Good"
elif movements_per_hour > 5.0 or avg_noise > 500:
    quality = "Poor"
else:
    quality = "Fair"
```

*   **Tardiness Check:** If the user goes to bed past their scheduled bedtime, the server logs the difference:
    $$\text{Tardiness} = \text{Actual Bedtime} - \text{Scheduled Bedtime}$$

---

## 6. Comprehensive Teacher Viva Q&A

### Q1: What is Root Mean Square (RMS) in audio processing, and why is it used to measure noise?
**Answer:** Audio signals alternate between positive and negative values around a center line. Taking a simple average would sum the positive and negative values, resulting in a value close to zero.
**RMS (Root Mean Square)** squares the values (making them all positive), calculates the mean of these squares, and takes the square root of the result. This measures the true power and intensity of the sound wave, regardless of phase.

### Q2: Why does the system ignore motion during the first 20 seconds of sleep?
**Answer:** When you first go to bed, you need time to get under the blankets, adjust your pillow, and settle down. 
If the system began monitoring immediately, these initial movements would trigger the pre-wake check and wake the clock back up. We implement a **20-second grace period** (`lastSleepEnteredMs`) to allow the user to settle in before motion detection becomes active.

### Q3: Why use a 30-second sliding history array instead of checking if the PIR is currently HIGH or LOW?
**Answer:** Checking the raw state of a PIR pin only tells you if there is motion at that exact millisecond. If a user is sleeping, they might move their hand for a split second. A simple check would read this as "active".
By using a **sliding history array**, we look at the activity density over time. This allows the system to remain in sleep mode if there are only minor, isolated movements, and only wake up if there is sustained activity.

### Q4: Why is the sleep window configuration saved on both the server and the ESP32?
**Answer:** The ESP32 needs the sleep window configurations locally to gate the automatic sleep state machine in its main loop. The server saves these configurations to disk so they survive server restarts, and serves them to the Android app via REST API so they can be adjusted in the UI.

---

## 7. Evidence Paths
*   Sleep window check definition: [gemini_LLM_btn.ino#L94-L108](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L94-L108)
*   Clock state sleep check: [gemini_LLM_btn.ino#L1751-L1770](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1751-L1770)
*   Grace period check: [gemini_LLM_btn.ino#L1784](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1784)
*   Pre-wake validation logic: [gemini_LLM_btn.ino#L1796-L1815](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1796-L1815)
*   Quality rating rules on server: [agentic_companion.py#L1121-L1155](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1121-L1155)
