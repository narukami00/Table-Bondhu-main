# Companion User Guide

## What is Table-Bondhu?

Table-Bondhu is a smart desk companion — a small ESP32-powered device with a color display that sits on your desk and responds to your voice. It's like having a tiny AI assistant that you can talk to by pressing a button.

## Getting Started

1. Plug in your ESP32 and ensure the Python server is running
2. Wait for the clock display to show "SYSTEM READY"
3. Press D14 button and speak!

## Voice Commands

### Basic Interaction
1. **Press and hold** the tactile button (D14)
2. **Speak** your command while holding
3. **Release** the button — companion responds

### What You Can Say

#### Greetings
- "Hi", "Hello", "Hey", "Yo"

#### Ask Questions
- "What time is it?", "How are you?", "Tell me a joke"
- Any question with what, how, why, can you, is, do, where, when, who

#### Set Reminders
- "Remind me at 3pm"
- "Set alarm for 8:30 AM"
- "Alarm in 5 minutes"
- "Remind me to buy milk in 2 hours"

#### Manage Reminders
- "What are my reminders?" — Lists all active
- "Delete the first reminder" — Removes specific one
- "Clear all reminders" — Removes everything

#### Start Timers
- "Timer for 25 minutes"
- "Countdown for 10 minutes"
- "Focus timer for 1 hour"

#### Control Timers
- Say "pause", "resume", "cancel" during timer
- Short press button to pause/resume
- Long press (1s+) to cancel
- BOOT button to cancel

#### Dismiss Alarms
- Say "stop", "dismiss", "cancel", "shut up"
- Or press any button

## Display Modes

### Clock Mode (Default)
Shows current time, date, weather icon, and connection status.

### Listening Mode
Avatar shows smile with "LISTENING..." indicator.

### Thinking Mode
"Thinking..." with animated dots while processing.

### Speaking Mode
Response text in speech bubble with animated avatar.

### Reminder List
Paginated full-screen list of active reminders.

### Timer Display
Large countdown with MM:SS or HH:MM:SS format.

### Alarm Mode
Flashing red background with alarm name. Buzzer sounds. Auto-dismisses after 30s.

### Sleeping Mode
Black screen with "Sleeping" text. Activates after 30 seconds of no PIR motion. Wakes on motion detection.

## Button Controls

| Button | Action |
|--------|--------|
| D14 (short press) | Start recording (clock/idle states) |
| D14 (short press) | Pause/Resume timer |
| D14 (long press, 1s+) | Cancel timer |
| D14 (short press) | Dismiss alarm |
| BOOT/D0 | Paginate text / Cancel timer |

## PIR Motion Sensor

The companion includes a PIR sensor (HC-SR501) on GPIO 27 for motion detection:

- **30 seconds of no motion** → Display enters sleeping mode
- **Motion detected** → Wakes back to clock mode
- **Purpose**: Calibrate PIR sensitivity knobs to get the right detection range

### PIR Sensor Knobs

- **Sensitivity** (left/top): Turn counter-clockwise to reduce false triggers
- **Time delay** (right/bottom): Turn to minimum (~3 seconds)

### PIR Positioning

- Mount upright with dome facing horizontally
- Avoid pointing at: air vents, windows, heaters, monitors
- Best detection: lateral movement across field of view

## Adaptive Display

Auto-adjusts color theme based on ambient light:
- **Night** (dark): Black/yellow
- **Dusk** (dim): Navy/light blue
- **Autumn** (moderate): Orange/dark red
- **Bright** (well-lit): White/dark blue

## Avatar Themes

Two visual themes (compile-time selection):
- **Pikachu**: Yellow Pikachu with various expressions
- **Girl**: Anime-style girl avatar

Change in `gemini_LLM_btn.ino`:
```cpp
#define ACTIVE_THEME THEME_PIKACHU    // or
#define ACTIVE_THEME THEME_GIRL
```

## Audio

- All responses use Pikachu voice effect (+40% pitch/speed)
- Laptop speakers for TTS output
- ESP32 buzzer for alarms and timer alerts
- Short two-tone beep on wake-up

## Troubleshooting

### "DISCONNECTED" on display
Check server is running and WiFi credentials are correct.

### No audio response
Ensure LM Studio is running with a model loaded.

### PIR keeps triggering / not triggering
Adjust sensitivity and time delay potentiometers on the PIR board.

## The Mobile Companion App

The Table-Bondhu Android App is a Flutter-based control center that bridges communications between your phone, the ESP32 desk clock, and the Python LLM server.

### 1. Wi-Fi Provisioning Bridge (AP Mode Setup)
If the ESP32 cannot connect to your Wi-Fi or needs reconfiguring:
1. Hold the **BOOT** button on the ESP32 during boot to force AP Mode. The display will show `AP Mode Active: Table-Bondhu-Config`.
2. Connect your phone's Wi-Fi to the access point `Table-Bondhu-Config`.
3. Open the Android app's **Connection** tab, fill in target Wi-Fi SSID, Password, and your PC's IP, and tap **Provision ESP32 Device**.
4. The app pings a local endpoint on the ESP32 (`http://192.168.4.1/setup`) via a POST request. The ESP32 saves these credentials to non-volatile storage (NVS) and restarts automatically.

### 2. Auto-Discovery & Persistent Server Binding
* **Automatic Scanning:** The app runs a background UDP socket listener on port `9999` to intercept the Python server's broadcasts.
* **Persistent Cache:** Discovered IPs are saved locally in the phone's filesystem (`saved_server_ip.txt`). The app automatically reads this on boot.
* **Active Verification:** The app runs a background ping loop (every 4 seconds) to verify connection to the server REST API on port `8888` (`/api/ping`).
* **Navigation Lock:** If the companion server is offline, the app stays on the Connection tab and locks access to other tabs (Chat, Reminders, Timer, Sleep Logs) to prevent unusable states, unlocking them instantly when a connection is restored.

### 3. Messenger-Style Voice Chat (Push-to-Talk)
* **Low-latency Listener:** A raw pointer listener on the microphone icon detects instant touch-down and touch-up events (bypassing the standard 500ms `onLongPress` delay).
* **Base64 Audio Pipeline:** Finger touch records audio at `16000Hz` Mono PCM directly to a `.wav` file, converting it to Base64, and uploading it to `/api/voice_chat` on release.
* **Short-Hold Filter:** Holds under `800ms` are treated as accidental taps. The app cancels the upload and prompts: `Hold to talk, release to send (tap is too short)`.

### 4. Focus Timer Interceptor
* If you send a timer request via the Chat tab (e.g. *"timer for 5 minutes"*), the server parses the request before hitting the LLM, triggering the ESP32 countdown display directly (`TIMER_START:duration`) instead of registering it as an alarm reminder.

### 5. Sleep Monitoring, Window Protection, & Diagnostics
* **Configurable Sleep Window:** To prevent false sleep detection when you are away from home during the day (even if the room is dark), you can set a Sleep Detection Window from the app (default: 10 PM to 10 AM). The ESP32's automatic PIR sleep detection will only trigger during this window.
* **Refined PIR Sleep State Machine:**
  * **Sleep Timeout:** The clock now waits for **120 seconds (2 minutes)** of continuous motionlessness and dark ambient light before entering sleep mode.
  * **Pre-Wake Standby:** Waking up requires either **3 distinct motion pulses (waves)** within a 15-second window, or **4.0 seconds of continuous motion** (sustained presence). This prevents false wakeups from minor movements like tossing and turning in bed.
* **Manual Wake-Up & Persistence:**
  * When the system is in sleep mode, the mobile app locks into a full-screen night overlay showing a pulsing Pikachu and a live sleep duration counter. This state persists across app restarts.
  * Tapping the **Wake Up** button sends a manual wake command (`CMD:FORCE_WAKE`) to the ESP32 to wake up the screen, ends the sleep monitoring session, and immediately displays an inline session summary card.
* **Sleep Diagnostics Screen:**
  * Accessible via the **Detailed Analytics** button on the sleep tab.
  * **Overall Sleep Score Card:** Displays average sleep duration, average tosses per session, and total logged sessions.
  * **Sleep Duration Trend Chart:** A custom vector-drawn line graph showing duration changes over recent sessions.
  * **Quality Ratio Pie Chart:** A custom-drawn circular chart showing the percentage of Good, Fair, and Poor sleep quality sessions.
  * **Environmental Diagnostics:** Evaluates average ambient light (LDR) and noise levels (RMS) to diagnose your sleep hygiene quality.
  * **Bedtime Adherence Card:** Tracks target bedtime compliance, tardiness rates, and latency.
  * **Sleep Hygiene Insights:** Dynamically generated advice to improve your sleep environment (e.g. noise reduction, pitch darkness, or room temperature).

