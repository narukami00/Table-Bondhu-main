# Table-Bondhu Codebase Structure (`STRUCTURE.md`)

This document describes the directory tree layout, critical source directories, entry points, and configuration files of the Table-Bondhu repository.

---

## 1. Project Directory Tree

Below is the directory tree containing the source files and configurations of the project:

```
Table-Bondhu-main/
├── agentic_companion.py           # Primary Python Server entry point (PC/Laptop)
├── agentic_companion_raspberrypi_4.py # Optimized Python Server entry point (Pi 4 CPU/RAM)
├── check_api.py                   # Diagnostic script to test LM Studio connection
├── requirements.txt               # Server-side Python dependency list
├── reminders.json                 # Persistent database for reminders and alarms
├── sleep_sessions.json            # Persistent database for sleep logs
├── sleep_status.json              # Persistent database for the active sleep state
├── COMPANION_GUIDE.md             # High-level system user guide
├── SETUP.md                       # Setup and installation instructions
│
├── gemini_LLM_btn/                # ESP32 Firmware Source Folder
│   ├── gemini_LLM_btn.ino         # Main Arduino sketch (entry point, loop, state logic)
│   ├── config.h                   # Wi-Fi SSID/Password and Server IP configurations
│   └── images.h                   # Raw RGB565 binary arrays for Pikachu/Girl avatars
│
├── table_bondhu_app/              # Flutter Mobile Application Source Folder
│   ├── pubspec.yaml               # Flutter package dependency and asset definitions
│   └── lib/
│       └── main.dart              # Main Flutter application (entry point, UI tabs, painters)
│
└── docs/                          # Project Documentation
    ├── README.md                  # High-level description and features list
    ├── TEACHER_QA_GUIDE.md        # Q&A guide for viva presentations
    └── codebase/                  # Technical codebase documentation (This folder)
```

---

## 2. Key Code Entry Points Tracing

### A. Python Server Core: `agentic_companion.py` (PC) & `agentic_companion_raspberrypi_4.py` (Pi 4)
*   **Startup Sequence:** The script starts by reading the `.env` file, initializing the speech/ASR engine (`onnx-asr` on PC; `faster_whisper` on Pi 4), loading the local VITS Piper voice model, and booting socket interfaces.
*   **Secondary Threads:**
    *   **TCP Listener Thread:** Starts on port `8080` to accept client connections and handle raw audio byte streaming.
    *   **REST HTTP Server Thread:** Starts on port `8888` to listen for HTTP REST API requests.
    *   **Alarm Scheduler Thread:** Runs a loop that checks `reminders.json` once a second to trigger alarms.
    *   **UDP Beacon Thread:** Broadcasts UDP packets on port `9999` to announce the server's IP address.
    *   **ASR Processing Thread:** Handles speech translations locally on standard CPU threads.

### B. ESP32 Client Core: `gemini_LLM_btn/gemini_LLM_btn.ino`
*   **`setup()` Routine:** Initializes the serial monitor, enables internal pull-ups for physical buttons, sets the buzzer pin as digital output, configures the LDR and PIR inputs, initializes the TFT display, and attempts to connect to Wi-Fi.
*   **`loop()` Routine:**
    1.  Maintains the socket connection to the server.
    2.  Reads the LDR sensor and schedules theme switching checks.
    3.  Monitors the tactile button for short/long presses.
    4.  Runs the I2S ADC controller to stream microphone audio when the button is held.
    5.  Processes incoming TCP server commands (e.g. `CMD:`, `WEATHER:`, `UI_ALARM:`, `SLEEP_WINDOW:`).
    6.  Runs the pre-wake and auto-sleep state machines.
    7.  Updates animations and redraws the display buffer.

### C. Android Companion App Core: `table_bondhu_app/lib/main.dart`
*   **`main()` Routine:** Launches the Flutter engine and starts the main application widget (`TableBondhuApp`).
*   **`MainNavigationScreen` State:** Manages the page router and sets up the active server ping loop and background UDP discovery listener.
*   **`SleepScreen` State:** Queries `/api/sleep/status` on start. If the clock is sleeping, it displays the full-screen pulsing sleep overlay and elapsed time counter.

---

## 3. Evidence Paths
*   Main python server file: [agentic_companion.py](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
*   Main firmware file: [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
*   Main Flutter app entry point: [table_bondhu_app/lib/main.dart](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart)
