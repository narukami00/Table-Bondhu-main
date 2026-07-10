# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python, C++ (Arduino sketch) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py), [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| Runtime + version | Python 3.8+, ESP32 Arduino Core | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt), [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |
| Package manager | pip (Python), Arduino Library Manager | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| Module/build system | Standard python runtime, Arduino CLI / IDE | [SETUP.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/SETUP.md) |

### 2) Production Frameworks and Dependencies

List only high-impact production dependencies (frameworks, data, transport, auth).

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `python-dotenv` | [TODO] Unpinned | Environment variable loader | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `onnx-asr` | [TODO] Unpinned | ONNX model wrapper for Parakeet ASR speech transcription | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `numpy` | [TODO] Unpinned | Array manipulation for audio preprocessing | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `sherpa-onnx` | [TODO] Unpinned | Offline TTS runtime using Piper models | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `gTTS` | [TODO] Unpinned | Fallback Google Text-to-Speech library | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `pydub` | [TODO] Unpinned | Audio manipulation and pitch adjustment | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `TFT_eSPI` | [TODO] Unpinned | Arduino TFT LCD driver library | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L2) |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| VS Code / Arduino IDE | Code editing and firmware compilation/uploading | [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |

### 4) Key Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the Python server
python agentic_companion.py

# Run diagnostic check for LM Studio LLM connection
python check_api.py
```

### 5) Environment and Config

- Config sources: `gemini_LLM_btn/config.h` (WiFi SSID, password, server IP, port, GMT offset) and `.env` (LLM, ASR model paths on server).
- Required env vars: `[TODO]` (No env template found in repo, but code indicates `.env` holds config for ASR/TTS paths if necessary; check `agentic_companion.py`).
- Deployment/runtime constraints: Python server requires Windows for `winsound` audio output. ESP32 client requires specific pin connections for SPI TFT (ST7735/ST7789), I2S Microphone (GPIO 32), active buzzer (GPIO 13), LDR sensor (GPIO 34), and PIR sensor (GPIO 27).

### 6) Evidence

- [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt)
- [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h)
- [SETUP.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/SETUP.md)
