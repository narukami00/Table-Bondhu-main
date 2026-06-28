# Table-Bondhu Agentic Companion Guide 🤖🎒

This guide explains how to run and test the new hands-free, wake-word-activated voice assistant backend (`agentic_companion.py`) with support for agentic reminders, alarms, and laptop speaker playback.

---

## 1. Features Implemented

*   **Hands-Free Wake Word Recognition:** Say *"wake up"* to activate Table-Bondhu. No hardware buttons or manual triggers are required.
*   **Dynamic VAD Silence Detection:** The server continuously measures audio energy (RMS) and automatically calibrates to your room's baseline noise floor. It stops recording and starts transcribing only when you finish speaking (silent for ~1.5 seconds).
*   **Agentic Reminders & Alarms:** Equipped the local LLM (`google/gemma-4-e4b` via LM Studio) with capabilities to:
    *   **Add Reminders/Alarms:** *"Set a reminder to study IoT at 3:00 PM"* (auto-converts to 24-hour format).
    *   **List Reminders:** *"What are my reminders?"*
    *   **Clear Reminders:** *"Delete all reminders."*
*   **Laptop Audio Integration:** Plays alarm buzzing sounds directly through your laptop speakers using Windows native `winsound` (no extra Python package installation required!).
*   **Alarm Dismissal:** Say *"stop"*, *"dismiss"*, or *"cancel"* to turn off the alarm buzzing.
*   **Visual Layouts on ESP32:** Updated the `live_rec.ino` screen renderer to support custom states:
    *   **`Ready!` (Idle)** screen.
    *   **`Listening...`** screen with guidance.
    *   **`Thinking...`** screen while the local LLM processes.
    *   **`Reminders:`** screen showing a checklist of all active tasks.
    *   **`ALARM!`** screen flashing red when an alarm is triggered.

---

## 2. Quick Start Setup

### Step 1: Flash the ESP32
1. Open the updated [live_rec.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/live_rec.ino) in the Arduino IDE.
2. Verify that your WiFi configurations match in your config files.
3. Flash the code to your ESP32.

### Step 2: Start LM Studio
1. Open **LM Studio**.
2. Load your `google/gemma-4-e4b` model.
3. Start the **Local Server** on port `1234` (ensure the Endpoint matches `http://127.0.0.1:1234/v1/chat/completions`).

### Step 3: Run the Python Server
Launch the new agentic companion server:
```bash
python agentic_companion.py
```
Upon startup, the server will load the Whisper model and wait for the ESP32 to connect.

---

## 3. Testing Your Desk Companion

1. **Boot the ESP32:** The screen should connect to your Wi-Fi and say **"Ready! Say 'Wake Up' to talk"**.
2. **Wake Word:** Say *"Wake Up"*. 
   * The laptop will emit a double-beep sound.
   * The ESP32 screen will transition to **"Listening..."**.
3. **Ask a Question:** Ask *"What is the capital of Bangladesh?"* or set a reminder:
   * *"Set a reminder to study IoT at 15:30"*
   * *"What are my reminders?"*
   * *"Clear all reminders"*
4. **Silence Trigger:** When you stop speaking for 1.8 seconds, the ESP32 screen changes to **"Thinking..."**.
5. **Alarm Firing:** When the system clock matches your scheduled reminder time, the laptop speakers will play an alarm sound and the ESP32 screen will flash a red **"ALARM!"** page.
6. **Dismiss Alarm:** Say *"stop"* or *"dismiss"* to quiet the alarm and return the companion to the Idle state.
