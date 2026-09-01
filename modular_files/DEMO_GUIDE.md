# Modular Viva Demonstration Guide (`DEMO_GUIDE.md`)

This guide explains how to present the restructured, modularized versions of the Table-Bondhu Python Server and Arduino IDE firmware to your instructor. 

---

## 1. Directory Layout

All modular demo files are located under the [`modular_viva_demo/`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo) folder:

```
modular_viva_demo/
├── DEMO_GUIDE.md                  # This presentation guide
│
├── python_server/                 # Modular Python Server Demo
│   ├── main.py                    # Entry point (spawns TCP, REST, Scheduler, UDP threads)
│   ├── config.py                  # Globals, paths, locks, and system prompts
│   ├── audio.py                   # VITS TTS synthesis, alarm players, and silencing
│   ├── reminders.py               # Reminders database CRUD and time parsing
│   ├── weather.py                 # Open-Meteo REST queries and weather mapping
│   ├── sleep.py                   # Sleep analysis, logging, and metrics
│   ├── speech.py                  # ASR model initialization and tag command parsing
│   ├── server_tcp.py              # Raw socket streams and client thread loops
│   └── server_rest.py             # REST API HTTP handlers (/api/*)
│
└── arduino_clock/                 # Modular Arduino IDE Firmware Demo
    ├── arduino_clock.ino          # Entry sketch (setup, loop, global variables)
    ├── config.h                   # Pin registries, WiFi credentials
    ├── images.h                   # Massive raw RGB565 avatar arrays
    ├── states.h                   # enum definitions forcurrentState
    ├── audio.ino                  # I2S microphone driver and alarm buzzers
    ├── sensors.ino                # LDR light checks, PIR motion debounces, buttons
    ├── display.ino                # TFT animations, clock-faces, double buffers
    └── network.ino                # TCP link maintenance, command extraction, AP portal
```

---

## 2. Presenting to the Instructor

When presenting, you can highlight the **decoupled architecture** and walk through the following flow maps:

### A. Python Server: Decoupled Responsibility Map
Instructors often look for modular programming patterns. Explain the code using this module structure:
*   Show **[`main.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/python_server/main.py):** It serves purely as a thread bootloader. Highlight how it spawns three background services:
    1.  **REST Server** ([`server_rest.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/python_server/server_rest.py))
    2.  **TCP Server** ([`server_tcp.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/python_server/server_tcp.py))
    3.  **Alarm Scheduler** (in `main.py`)
*   Show **[`speech.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/python_server/speech.py):** Focus on `process_speech()` to show how speech-to-text operates locally and routes commands to `handle_llm_response()` which decodes tags.
*   Show **[`audio.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/python_server/audio.py):** Point out the `play_speech_on_laptop` synthesis pipeline. Explain that it wraps local VITS Piper synthesis and falls back gracefully to system `espeak` if CPU load is high.

### B. Arduino IDE: Multiple Ino File Compilation
*   **The Feature:** Explain that the Arduino IDE supports split compilation. By placing multiple `.ino` files in the same folder, the compiler concatenates them during build time. This keeps code organized without requiring complex `.h` header linkage.
*   Show **[`arduino_clock.ino`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/arduino_clock/arduino_clock.ino):** This file contains all global definitions and the clean `loop()` block:
    ```cpp
    void loop() {
      readSensors();               // In sensors.ino
      updateNetworkConnection();   // In network.ino
      processIncomingData();       // In network.ino
      soundBuzzer();               // In audio.ino
      renderDisplay();             // In display.ino
    }
    ```
*   This structured loop makes the firmware incredibly easy to read and trace.

---

## 3. How to Run the Modular Demos

### Running the Python Server:
Open a terminal in the folder `modular_viva_demo/python_server/` and execute:
```bash
python main.py
```

### Opening the Arduino Code:
Open the file **[`arduino_clock.ino`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/modular_viva_demo/arduino_clock/arduino_clock.ino)** in the Arduino IDE. The IDE will automatically load the other `.ino` tabs (`audio.ino`, `display.ino`, `network.ino`, `sensors.ino`) in parallel, allowing you to compile and upload the firmware directly.
