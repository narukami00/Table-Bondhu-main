# Project Structure

```
Table-Bondhu-main/
├── agentic_companion.py          # Python TCP server (1291 lines)
├── gemini_LLM_btn/               # ESP32 Arduino firmware
│   ├── gemini_LLM_btn.ino        # Main sketch (1568 lines)
│   ├── config.h                  # WiFi & server config
│   └── images.h                  # Avatar bitmap data (~26K lines)
├── models/                       # AI model files
│   └── vits-piper-en_US-amy-low/ # VITS TTS model (offline)
│       ├── en_US-amy-low.onnx    # Model weights
│       ├── en_US-amy-low.onnx.json
│       ├── tokens.txt
│       └── espeak-ng-data/       # Phoneme data
├── assets/                       # Source artwork (for regeneration)
│   ├── Pikachu/                  # Pikachu avatar PNGs (14 files)
│   └── girl/                     # Girl avatar JPGs/PNGs (13 files)
├── docs/                         # Documentation
│   ├── README.md                 # Project overview
│   ├── STRUCTURE.md              # This file
│   ├── API.md                    # TCP protocol reference
│   └── codebase/                 # Implementation details
├── check_api.py                  # LM Studio diagnostic tool
├── requirements.txt              # Python dependencies
├── reminders.json                # Runtime reminder data (auto-created)
├── SETUP.md                      # Environment setup guide
├── COMPANION_GUIDE.md            # User usage guide
├── Table_Bondhu_Project_Guide.pdf
├── LICENSE
├── .gitignore
└── .vscode/                      # Arduino IDE config
```

## Entry Points

| Component | Entry File | How to Run |
|-----------|-----------|------------|
| Python server | `agentic_companion.py` | `python agentic_companion.py` |
| ESP32 firmware | `gemini_LLM_btn/gemini_LLM_btn.ino` | Flash via Arduino IDE |
| LM Studio check | `check_api.py` | `python check_api.py` |

## Module Map (agentic_companion.py)

| Section | Lines | Responsibility |
|---------|-------|---------------|
| Configuration | 24–38 | Server bind, LLM URL, command triggers, question words |
| System Instruction | 52–76 | LLM prompt engineering — defines `[CMD:...]` tag format |
| LocalChatSession | 78–126 | LM Studio API wrapper with history and dynamic context |
| ASR Model Loading | 128–133 | Parakeet TDT 0.6B initialization |
| TTS Model Loading | 140–161 | VITS offline TTS with Google TTS fallback |
| Audio Helpers | 168–276 | Wake-up sounds, alarm sounds, Pikachu voice synthesis |
| Reminders Store | 278–439 | JSON-backed CRUD with thread-safe locking |
| Weather API | 441–472 | Open-Meteo forecast fetcher |
| Alarm Scheduler | 501–565 | Background thread — polls reminders, fires alarms |
| VoiceAgentHandler | 568–1269 | TCP socket handler — calibration, keyword detection, button recording, LLM processing |

## Module Map (gemini_LLM_btn.ino)

| Section | Lines | Responsibility |
|---------|-------|---------------|
| Includes & Config | 1–62 | Libraries, pin definitions, theme palettes |
| State Machine | 97–111 | 13-state `AppState` enum |
| I2S Setup | 247–265 | ESP32 ADC I2S configuration (16kHz) |
| Avatar Rendering | 338–465 | Sprite-based animation, themed image push, cameo, waving |
| Clock Display | 467–586 | NTP time, weather icons, HUD borders, connection status |
| Animation Loop | 630–941 | Blink, mouth, shake, timer decrement, alarm flashing, safety timeouts |
| Text Pagination | 972–1056 | Word-wrap into display lines, page splitting |
| Speech Bubble | 1058–1100 | Anti-flicker text rendering with page indicator |
| Timer Page | 1141–1199 | Focus timer UI with MM:SS/HH:MM:SS |
| Setup | 1203–1263 | Hardware init, WiFi, NTP, I2S, TFT, sprite allocation |
| Main Loop | 1267–1568 | Server connection, button handling, audio streaming, command parsing |

## Naming Conventions

- **Python**: snake_case for functions/variables, PascalCase for classes
- **Arduino**: camelCase for functions/variables, UPPER_CASE for constants/pins
- **Commands**: `CMD:WOKE`, `___END___` (ESP32→Server); `UI_STATE:`, `UI_MSG:`, `WEATHER:` (Server→ESP32)
- **Files**: lowercase with underscores for Python, camelCase for Arduino

## Data Flow

```
User speaks
    ↓
ESP32 captures 16kHz PCM via I2S ADC
    ↓
DC filter + 12x gain applied
    ↓
Raw PCM streamed over TCP to Python server
    ↓
Server resamples to 16kHz, runs Parakeet ASR
    ↓
Transcribed text sent to LM Studio LLM
    ↓
LLM response parsed for [CMD:...] tags
    ↓
Response text + TTS audio duration sent to ESP32
    ↓
ESP32 displays text in speech bubble, plays avatar talking animation
    ↓
Laptop speakers play Pikachu-voiced audio (async)
```
