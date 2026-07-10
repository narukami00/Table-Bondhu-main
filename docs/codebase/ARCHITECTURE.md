# System Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: Client-Server / Thin-Client (Hardware) + Thick-Server (Python backend).
- Why this classification: The ESP32 client functions as a thin sensor-and-display node that streams raw PCM audio and LDR/PIR status updates over TCP, while the Python server handles intensive operations (ASR transcription, LLM processing, TTS synthesis, scheduling, and local audio output).
- Primary constraints:
  1. Network dependency: The system cannot transcribe speech or process LLM queries without a stable TCP connection to the Python server.
  2. Hardware memory limitations: The ESP32's internal RAM requires moving large buffers (such as the 32KB themed buffer) to the heap to prevent boot crashes.
  3. Operating system limits: The Python server uses `winsound` for audio playback, restricting the server runtime to Windows environments.

### 2) System Flow

```text
[ESP32 Mic Capture] -> [TCP streaming to Server] -> [Parakeet ASR & LLM Processing] -> [TTS Synthesis] -> [Laptop Speaker & ESP32 screen update]
```

1. **Input**: User presses the button (GPIO 14) or the PIR motion sensor triggers a wake-up. The ESP32 captures 16kHz PCM audio via its internal ADC on GPIO 32.
2. **Transport**: The ESP32 streams the raw audio PCM bytes over a raw TCP socket connection on port 8080.
3. **Transcription & Coordination**: The Python server's `VoiceAgentHandler` receives the stream, resamples it, runs Parakeet ASR, sends the text to the LLM (LM Studio), and parses any generated `[CMD:...]` tags.
4. **Action & Output**: The server triggers local audio playback (via winsound TTS) and sends display commands (`UI_MSG:...`, `UI_STATE:...`) back to the ESP32 over TCP.
5. **Display**: The ESP32 updates its TFT display using sprites (faceSprite, cameoSprite) based on state changes.

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `VoiceAgentHandler` | TCP framing, keyword detection, speech buffer processing, and command routing | Low-level SPI display control, TFT rendering | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L568) |
| `LocalChatSession` | LLM communication, conversation history buffer management, and system instruction updates | Audio playbacks, TCP socket bindings | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L78) |
| `Alarm Scheduler` | Periodic scanning of `reminders.json` and firing active alarms/alerts | Direct microphone stream ingestion | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L501) |
| ESP32 App Loop | Local state machine transitions, I2S ADC reading, TFT SPI display rendering, and sensor polling | LLM context construction, ASR model execution | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1288) |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| State Machine | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L102-L117) | Coordinates 14 UI and sensor states (CLOCK, CAMEO, SLEEPING, SPEAKING, etc.) cleanly. |
| Singleton/Global Instance | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L78) | Wraps the LLM session to preserve active chat history context throughout the runtime. |
| Double Buffering/Sprites | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L98-L99) | Employs TFT_eSPI sprites for the avatar face and cameos to prevent screen flickering. |

### 5) Known Architectural Risks

- **TCP Blocking**: A drop in network connectivity causes connection retries that block state handling on the ESP32.
- **Monolithic Layout**: Both client and server codes are monolithic single-file structures, increasing the risk of unintended state interference during updates.
- **Platform Incompatibility**: Using `winsound` locks server-side execution to Windows environments.

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [docs/API.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/API.md)

---

## Extended Sections (Optional)

### System State Machine (ESP32)

```
                    ┌─────────────┐
         ┌─────────│   CLOCK     │◄────────────────────┐
         │         └──────┬──────┘                     │
         │                │ button press / cameo timer  │
         │         ┌──────▼──────┐                     │
         │         │   CAMEO     │                     │
         │         └──────┬──────┘                     │
         │                │ complete                    │
         │         ┌──────▼──────┐                     │
         │         │   WAVING    │                     │
         │         │   _INTRO    │                     │
         │         └──────┬──────┘                     │
         │                │ wave complete               │
         │         ┌──────▼──────┐                     │
         │         │    IDLE     │──timeout 20s─────────┘
         │         └──────┬──────┘
         │                │ server: LISTENING
         │         ┌──────▼──────┐
         │         │  LISTENING  │──30s timeout──→ CLOCK
         │         └──────┬──────┘
         │                │ server: THINKING
         │         ┌──────▼──────┐
         │         │  THINKING   │──30s timeout──→ CLOCK
         │         └──────┬──────┘
         │                │ server: UI_MSG
         │         ┌──────▼──────┐
         │         │  SPEAKING   │──duration──→ IDLE
         │         └──────┬──────┘
         │                │ alarm
         │         ┌──────▼──────┐
         │         │    ALARM    │──30s / dismiss──→ CLOCK
         │         └─────────────┘
         │
         │         ┌─────────────┐
         │         │   TIMER     │◄── TIMER_START
         │         └──────┬──────┘
         │                │
         │         ┌──────▼──────┐
         │         │ TIMER_      │
         │         │ PAUSED      │──resume──→ TIMER
         │         └──────┬──────┘
         │                │ cancel
         │         ┌──────▼──────┐
         │         │ TIMER_      │
         │         │ FINISHED    │──dismiss──→ CLOCK
         │         └─────────────┘
         │
          │         ┌─────────────┐
          │         │  SLEEPING   │◄── no PIR motion, LDR < 500 & clock 30s
          │         └──────┬──────┘
          │                │ PIR motion / rising edge
          │         ┌──────▼──────┐
          │         │  SLEEPING_  │──10s timeout without confirmation──→ SLEEPING
          │         │  PREWAKE    │
          │         └──────┬──────┘
          │                │ confirmed (held / 2 waves / button / server cmd)
          │         ┌──────▼──────┐
          │         │    SLEEP    │
          │         │   SUMMARY   │──15s timeout / button press──→ CLOCK
          └─────────└─────────────┘
```
