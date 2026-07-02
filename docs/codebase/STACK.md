# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python (3.8+), C++ (Arduino) | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt), [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| Runtime + version | Python 3, ESP32 Core for Arduino (v2.x+) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py), [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |
| Package manager | pip (Python), Arduino Library Manager | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt), [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L3) |
| Module/build system | Standard Python Interpreter, Arduino Build System (GCC/G++) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py), [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `google-generativeai` | Not pinned | Google Gemini API Client SDK for cloud LLM response generation | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `python-dotenv` | Not pinned | Parses `.env` configuration file to load API keys | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `onnx-asr` | Not pinned | Local speech-to-text ASR transcriber | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `SpeechRecognition` | Not pinned | Google Web Speech Recognition API wrapper | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `numpy` | Not pinned | Processing raw audio sample byte arrays | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `sherpa-onnx` | Not pinned | Offline speech denoising and enhancement using GTCRN model | [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt) |
| `gTTS` | Not pinned | Google Text-to-Speech library used to synthesize responses | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L17) |
| `pydub` | Not pinned | Appends silence pads and shifts sample rates of audio files | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L18) |
| `TFT_eSPI` | Library Version | High-speed graphic driver library for ST7735 LCD displays | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L3) |
| `WiFi.h` | ESP32 Core | Standard library for Wi-Fi station connectivity | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L4) |
| `driver/i2s.h` | ESP32 Core | Driver for non-blocking I2S microphone audio sampling | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L6) |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| Arduino IDE / CLI | Compiling, verifying, and flashing firmware sketches | [.vscode/arduino.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/arduino.json) |
| VS Code Arduino Extension | Compiling and uploading sketches directly in VS Code | [.vscode/extensions.json](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.vscode/extensions.json) |

### 4) Key Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the agentic companion server
python agentic_companion.py
```

### 5) Environment and Config

- **Config sources**:
  - [.env](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.env): Stores Google Gemini API key.
  - [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h): WiFi credentials (`WIFI_SSID`, `WIFI_PASSWORD`) and companion server socket parameters (`SERVER_IP`, `SERVER_PORT`).
- **Required env vars**:
  - `GEMINI_API_KEY`: API Key to authenticate Generative AI completions.
- **Deployment/runtime constraints**:
  - Requires Windows OS (uses native `winsound` loop for alarm audio playback on laptop/desktop speakers).
  - ESP32 hardware requires INMP441 I2S microphone (ADC on GPIO 32) and ST7735 IPS display.

### 6) Evidence

- [requirements.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/requirements.txt)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
