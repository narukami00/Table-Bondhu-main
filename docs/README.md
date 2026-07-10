# Table-Bondhu — AI Desk Companion

An ESP32-based desk companion with a 128x160 TFT display that responds to voice commands, displays animations, manages reminders/alarms/timers, and provides weather information — all powered by a local Python backend with offline AI capabilities.

## What It Is

A physical desk gadget that sits on your table. You press a button, speak to it, and it responds with animated avatars (Pikachu or Girl themes), spoken audio, and on-screen text. It can set reminders, run countdown timers, tell you the weather, and answer questions — all running locally without cloud dependencies for core functionality.

## Quick Start

### Prerequisites
- Python 3.8+ on your laptop/desktop
- ESP32 with a 128x160 TFT display (ST7735/ST7789)
- LM Studio running locally with `qwen2.5-coder-1.5b-instruct` model loaded
- Arduino IDE with TFT_eSPI library installed

### 1. Start the Python Server
```bash
pip install -r requirements.txt
# Ensure LM Studio is running on localhost:1234
python agentic_companion.py
```

### 2. Flash the ESP32
1. Open `gemini_LLM_btn/gemini_LLM_btn.ino` in Arduino IDE
2. Edit `gemini_LLM_btn/config.h` with your WiFi and server IP
3. Select board: ESP32 Dev Module, Partition Scheme: Huge APP
4. Upload

### 3. Use
- Press the tactile button (D14) to wake the companion
- Speak your command while holding the button
- Release to send
- Use BOOT button (D0) to paginate through long text responses

## System Architecture

```
┌─────────────────┐     TCP (port 8080)     ┌──────────────────────┐
│   ESP32 + TFT   │ ◄─────────────────────► │  Python Server       │
│                 │    PCM audio + commands  │                      │
│ • Button input  │                          │ • Parakeet ASR       │
│ • I2S mic       │                          │ • LM Studio LLM      │
│ • TFT display   │                          │ • VITS TTS (offline)  │
│ • Buzzer (D13)  │                          │ • Reminders/Alarms   │
│ • LDR sensor    │                          │ • Weather API        │
│ • PIR sensor    │                          │ • Timer management   │
│ • Animations    │                          │                      │
└─────────────────┘                          └──────────────────────┘
```

The ESP32 captures audio via its built-in ADC at 16kHz, streams raw PCM over TCP to the Python server. The server transcribes speech locally (Parakeet TDT 0.6B), queries a local LLM (qwen2.5-coder-1.5b via LM Studio), generates TTS audio (VITS offline or Google TTS fallback), and sends display commands back to the ESP32.

## Features

### Voice Interaction
- **Push-to-talk**: Press and hold D14 button, speak, release to send
- **Hands-free wake word**: Background keyword detection continuously monitors for voice activation
- **Local ASR**: Parakeet TDT 0.6B via onnx_asr — no internet needed for transcription
- **Local LLM**: qwen2.5-coder-1.5b via LM Studio — responses constrained to 15 words for display

### Reminders & Alarms
- Create reminders with natural language: "remind me at 3pm", "alarm in 5 minutes"
- Relative time support: 30s, 5m, 2h
- Absolute time support: 3:00 PM, 15:00, tomorrow 9am
- Persistent JSON storage (survives restarts)
- Auto-firing alarm with buzzer + laptop speaker sound
- Voice dismiss: say "stop", "dismiss", "cancel" to silence

### Focus Timer
- Start countdown: "timer for 25 minutes"
- Voice control: pause, resume, cancel
- Physical button control: short press = pause/resume, long press = cancel
- BOOT button also cancels timer
- Buzzer alarm when countdown completes

### PIR Motion Sensor
- Motion detection on GPIO 27
- 30-second inactivity timeout → sleeping mode (display shows "Sleeping")
- Motion detected → wake back to clock
- 5-second debounce between triggers
- 30-second warm-up after boot

### Weather
- Automatic weather fetch for Khulna, Bangladesh (KUET coordinates)
- Updates every 30 minutes
- Displayed as icon + temperature on the clock face
- Uses Open-Meteo API (free, no API key)

### Adaptive Display
- 4-level LDR-based theme switching: Night, Dusk, Autumn, Bright
- Two avatar themes: Pikachu and Girl (compile-time selection)
- Animations: idle blinking, talking mouth movement, shake/breathe effects, waving, cameo peeping
- Text bubble with word-wrap pagination
- Dissolve wipe transitions
- NTP-synced clock face

### Audio Output
- Pikachu voice effect: 40% pitch/speed increase via pydub
- Offline TTS via VITS (Piper voice) with Google TTS fallback
- Laptop speaker playback via winsound
- ESP32 buzzer for alarms and timer completion

## File Overview

| File | Purpose |
|------|---------|
| `agentic_companion.py` | Python TCP server — the brain |
| `gemini_LLM_btn/gemini_LLM_btn.ino` | ESP32 firmware — the face |
| `gemini_LLM_btn/config.h` | WiFi and server configuration |
| `gemini_LLM_btn/images.h` | Avatar bitmap data (RGB565) |
| `models/vits-piper-en_US-amy-low/` | Offline TTS model files |
| `assets/` | Source PNG artwork for avatar conversion |
| `requirements.txt` | Python dependencies |
| `check_api.py` | LM Studio connectivity diagnostic |

## Technical Details

- **Audio Pipeline**: ESP32 ADC → I2S (16kHz, 16-bit mono) → DC filter + 12x gain → TCP → numpy resample to 16kHz → Parakeet ASR
- **LLM Pipeline**: Transcribed text → LM Studio /v1/chat/completions → response parsing (extracts `[CMD:...]` tags) → TTS + display
- **Display Pipeline**: Commands from server → TFT_eSPI sprites → themed avatar rendering → speech bubble pagination
- **Protocol**: Binary TCP stream with embedded text commands (`CMD:WOKE`, `___END___`, `LDR:xxx`, `TIMER_DONE`, `PIR:MOTION` from ESP32; `UI_STATE:`, `UI_MSG:`, `WEATHER:`, `TIMER_*` from server)

## Hardware Requirements

- ESP32 Dev Board (any variant with ADC1)
- 128x160 TFT Display (ST7735/ST7789, SPI)
- Tactile button on D14 (push-to-talk)
- Active buzzer on D13
- LDR on D34 (ADC1_CH6)
- PIR sensor on D27 (HC-SR501 or similar)
- Internal ADC on GPIO32 (I2S microphone input)

## Known Limitations

- Audio quality depends on ESP32's 12-bit ADC — no external I2S microphone
- Parakeet model path is hardcoded to a specific Windows path
- Pikachu voice pitch-shift works on Windows only (winsound dependency)
- No multi-user support — single ESP32 connection at a time
- Weather data hardcoded to Khulna, Bangladesh coordinates
- Theme switching requires I2S ADC temporarily disabled (brief audio gap)

## Authors

- **Rafsan** — Python server, system integration
- **Utsa** — Arduino firmware, display & animations

KUET CSE22 — IoT Course Project, 2026
