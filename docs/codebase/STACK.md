# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python (3.8+), C++ (Arduino) | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt), [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| Runtime + version | Python 3, ESP32 Core for Arduino | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py), [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |
| Package manager | pip (Python) | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| Module/build system | Standard Python Interpreter, Arduino Build System | [Python/main.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/main.py), [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |

### 2) Production Frameworks and Dependencies

List only high-impact production dependencies (frameworks, data, transport, auth).

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `google-generativeai` | [TODO] (Not pinned) | SDK to interact with Google Gemini API | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `python-dotenv` | [TODO] (Not pinned) | Load environment variables from `.env` | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `onnx-asr` | [TODO] (Not pinned) | ONNX model based speech-to-text transcriber | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `SpeechRecognition` | [TODO] (Not pinned) | Google Speech Recognition wrapper | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `numpy` | [TODO] (Not pinned) | Array processing for audio buffers | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `gTTS` | [TODO] (Not in requirements) | Google Text-to-Speech library | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L17) |
| `pydub` | [TODO] (Not in requirements) | Audio file loading and resampling helper | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L18) |
| `faster-whisper` | [TODO] (Not in requirements) | Local ASR Whisper model runner | [gemini_LLM.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM.py#L3) |
| `TFT_eSPI` | [TODO] (Arduino Lib) | Screen driver library for display | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L3) |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| Arduino IDE / CLI | Coding, compiling, and flashing ESP32 sketches | [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |
| VS Code Arduino Extension | Integration of Arduino builds in IDE | [.vscode/extensions.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/extensions.json) |

### 4) Key Commands

```bash
# Install Python backend dependencies
pip install -r requirements.txt

# Run standard Python backend server
python Python/main.py

# Run hands-free agentic companion server
python agentic_companion.py

# Check LM Studio local models status
python check_api.py
```

### 5) Environment and Config

- Config sources: 
  - [.env](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.env) (Git-ignored env settings)
  - [Python/config/settings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py) (Loads configurations into memory)
  - [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h) (WiFi credentials and Server connection parameters for Arduino sketches)
- Required env vars: 
  - `GEMINI_API_KEY`: API key for Google Gemini model. [Evidence: [Python/config/settings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py#L11)]
  - `WIFI_SSID_1`, `WIFI_PASSWORD_1`, `SERVER_IP_1`, `WIFI_SSID_2`, `WIFI_PASSWORD_2`, `SERVER_IP_2`: Environment variables defined in `settings.py` but unused.
- Deployment/runtime constraints:
  - Requires ESP32 hardware with I2S microphone (e.g. INMP441) and ST7735/ILI9341 display configured.
  - Requires LM Studio running locally on port `1234` with `google/gemma-4-e4b` model loaded for local operations (`agentic_companion.py`, `gemini_LLM.py`, etc.).
  - Windows OS native `winsound` library is used for playing alarms on computer speaker.

### 6) Evidence

- [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt)
- [Python/config/settings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py)
- [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [SETUP.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/SETUP.md)
