# Architecture

## Core Sections (Required)

### 1) Architectural Style

- **Primary style**: Layered Client-Server Architecture + State-Driven Firmware (FSM)
- **Why this classification**:
  - The Python companion server operates as a multi-threaded service coordinating TCP communication, voice transcription (ASR), local keyword parsing, Google TTS voice synthesis, and alarm scheduling.
  - The ESP32 firmware is a Finite State Machine (FSM) transitioning between states using a volatile `currentState` enum. Transitions are triggered either locally (via button interactions or timers) or remotely (via TCP command packets).
- **Primary constraints**:
  - **Microcontroller Memory Limitations**: The ESP32's static RAM is extremely limited. Image asset frames (sprites) are stored in program memory (PROGMEM) in `images.h`. High RAM allocations like the `themedBuf` (32KB) are dynamically allocated on the heap during `setup()` to prevent boot crashes. Preprocessor conditional directives are used to compile specific character assets and halve the binary size.
  - **Zero-Block Loop Requirement**: The main firmware loop must execute animation frames and check sensors at 60+ FPS. Any network transaction (such as Wi-Fi connection attempts or server socket connections) must be non-blocking to prevent UI and local countdown freezes.
  - **Thread-safe Server Transport**: The Python companion utilizes socket locks (`send_lock`) to serialize outgoing TCP writes, preventing socket stream corruption when background scheduler alarms fire while the main thread is sending TTS data.

### 2) System Flow

```text
[Online Flow]
User speech -> ESP32 Mic -> TCP Stream -> Python Server -> ASR (ONNX) -> Local Keyword / Gemini LLM -> TTS Modulator -> TCP Sync -> Laptop Speaker & ESP32 UI

[Focus Timer Flow]
Voice request -> Python Parser -> TIMER_START -> ESP32 STATE_TIMER (Local Decrement)
Short press (PTT) -> STATE_TIMER_PAUSED (Freeze Decrement)
Long press (PTT) / BOOT button -> TIMER_DONE -> Return to STATE_CLOCK
Countdown ends -> STATE_TIMER_FINISHED -> Buzzer + TCP TIMER_DONE -> Looping Laptop Alarm
```

#### Detailed Operations Flow:
1. **Audio Capture & Streaming**: When the user presses the PTT button, the ESP32 enters `STATE_WAVING_INTRO` and then `STATE_LISTENING`. It reads raw 16-bit 16kHz mono audio via the I2S microphone (e.g. INMP441) and streams it inside a `CMD:WOKE` / `___END___` wrapper over TCP port 8080.
2. **ASR, Context Injection & Keyword Interception**: The Python server saves the stream to a WAV file and transcribes it locally using an ONNX-based ASR engine. The text is passed to the keyword scanner first:
   * If it matches timer/alarm commands (e.g. *"Set a timer for 10 minutes"*), the Python server parses the duration and sends `TIMER_START:600` to the ESP32, bypassing the LLM.
   * Otherwise, the server queries the active reminders list from `reminders.json` and dynamically injects the active reminders list with their 1-based indices into the Gemini LLM's system prompt context. The user's query is then sent to the Google Gemini API.
   * If the LLM generates a deletion command (e.g. `[CMD:DELETE_REMINDER|index]` from the prompt context), the companion parses it and performs the deletion.
3. **Pikachu voice synthesis**: Gemini's text reply is sent to Google gTTS, resampled to 44.1kHz, shifted in pitch and speed (1.40x) for a cute Pikachu sound, padded with 1 second of silence, and played asynchronously via `winsound` on the laptop.
4. **Mouth Sync**: The Python server calculates the *original* duration of the speech (before adding silence) and sends it as `DURATION:x.x` to the ESP32. The ESP32 enters `STATE_SPEAKING` and runs the mouth animation for exactly `x.x` seconds, transitioning back to `STATE_IDLE` while the laptop speaker plays the trailing silence.
5. **Focus Timer Countdowns**:
   * **Running (`STATE_TIMER`)**: The ESP32 decrements the count locally once per second, redrawing only the inner digit box to prevent screen flickering. The digits scale dynamically: Size 2 (12px wide) for `HH:MM:SS` to prevent boundary clipping, and Size 3 (18px wide) for `MM:SS`.
   * **Paused (`STATE_TIMER_PAUSED`)**: Pressing the PTT button pauses the local decrement. The screen shows `** PAUSED **` and instructions.
   * **Completed (`STATE_TIMER_FINISHED`)**: When the timer reaches 0, the ESP32 starts its local buzzer, flashes the screen red, and sends `TIMER_DONE` to the laptop. The companion server receives `TIMER_DONE` and triggers the looped `"SystemHand"` alarm sound on the laptop.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `agentic_companion.py` | TCP socket server, ASR transcribing, local keyword routing, gTTS speech modulation, database operations, alarm scheduler. | Rendering graphics on LCD, reading LDR sensors, polling buttons. | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py) |
| `gemini_LLM_btn.ino` | FSM state transitions, LCD drawing/flicker management, button hold/click parsing, LDR-based theme switching, buzzer alerts, I2S recording. | Running language models, calculating absolute calendar triggers. | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| `images.h` | Pixel bitmap hex arrays for animations (`avatar_wave`, `peek`, `eyes_closed`). | Logic loops, pin configurations. | [gemini_LLM_btn/images.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/images.h) |

### 4) Reused Patterns

* **State-Driven Rendering**: The ESP32's `updateAnimations()` loop polls `currentState`. It uses conditional flags (`needRedraw`) to only rewrite modified sub-rectangles of the screen instead of executing full-screen clears, ensuring smooth 60 FPS rendering.
* **Edge-Triggered Hold-Timing**: The main button handler tracks the duration of button presses using `millis() - buttonPressStartMs`. If it exceeds 1000ms during active timer states, it triggers a long-press cancel. If it is released before that, it registers a short-press click (pause/resume).
* **Non-Blocking Network Handshakes**: WiFi and Server socket connection checks in `loop()` are non-blocking. If a connection is lost, it falls back to a offline UI banner (`DISCONNECTED` and `HAVE A GOOD DAY!`) and tries to reconnect every 10 seconds without stalling the main thread.

### 5) Known Architectural Risks

- **Local Network Dependence**: If the user's WiFi drops, the assistant loses time syncing (NTP) and LLM cloud access.
- **ASR Latency**: Transcription of WAV files is done on the laptop CPU. If CPU utilization is high, ASR will block the socket thread, delaying Pikachu's response.
- **Unencrypted TCP Socket**: Device commands and voice recordings are sent in raw bytes without TLS encryption, leaving them open to local network eavesdropping.

### 6) Evidence

- [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [images.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/images.h)
- [reminders.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/reminders.json)
