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
