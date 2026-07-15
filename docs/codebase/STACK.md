# Table-Bondhu Technology Stack (`STACK.md`)

This document records the programming languages, software runtimes, dependencies, libraries, and frameworks used in the Table-Bondhu project.

---

## 1. Programming Languages & Runtimes

*   **ESP32 Firmware:**
    *   Language: C++ (Arduino dialect)
    *   Runtime/Framework: ESP32 Arduino Core (v2.x or v3.x)
    *   SDK: ESP-IDF (underlying core runtime)
*   **Companion Server:**
    *   Language: Python (v3.8+)
    *   Runtime: CPython Standard Interpreter
*   **Mobile Companion App:**
    *   Language: Dart (v3.x)
    *   Runtime: Flutter Framework Engine (v3.22+)

---

## 2. Server-Side Python Dependencies (`requirements.txt`)

| Dependency | Version | Production/Development | Purpose |
| :--- | :--- | :--- | :--- |
| `python-dotenv` | Any | Production | Loads system credentials and model path definitions from `.env` files |
| `numpy` | Any | Production | Handles real-time linear interpolation resampling and audio float32 array scaling |
| `sherpa-onnx` | Any | Production | Runs local end-to-end Text-to-Speech (TTS) using Piper voice models |
| `gTTS` | Any | Production | Generates spoken audio files using Google TTS as a network-fallback |
| `pydub` | Any | Production | Modulates pitch-shift speed variables to synthesize the Pikachu voice effect |
| `onnx-asr` | Custom | Production | Quantized local Speech-to-Text translation engine running Parakeet conformer models |

---

## 3. ESP32 Firmware Libraries (Arduino C++)

| Library | Version | Purpose |
| :--- | :--- | :--- |
| `WiFi.h` | Built-in | Manages WPA2 connections and handles Access Point (AP) mode provisioning |
| `WebServer.h`| Built-in | Runs a lightweight HTTP server on `192.168.4.1` to accept new credentials |
| `ESPmDNS.h` | Built-in | Maps IP hosts (multicast DNS name binding) |
| `driver/i2s.h`| Built-in | Direct I2S configuration for Analog microphone ADC DMA transfers |
| `TFT_eSPI` | ^2.5.0 | Handles graphics rendering on the ST7735 screen using double buffering |
| `ArduinoJson`| ^6.x or 7.x| Parses Wi-Fi setup payloads and sleep logs |

---

## 4. Flutter Mobile App Dependencies (`pubspec.yaml`)

| Package | Version | Purpose |
| :--- | :--- | :--- |
| `http` | ^1.6.0 | Sends HTTP REST requests (reminders, sleep status, chat logs) |
| `record` | ^5.2.1 | Captures raw voice bytes from the microphone for walkie-talkie chat uploads |
| `path_provider`| ^2.1.3 | Finds internal storage directories to write the server IP cache file |

---

## 5. External Tools & APIs

*   **LM Studio:** Local LLM hosting application running `qwen2.5-coder-1.5b-instruct` on port `1234`.
*   **Open-Meteo API:** A free, keyless REST service used to retrieve real-time weather logs for Khulna, Bangladesh.

---

## 6. Evidence Paths
*   Python dependency manifest: [requirements.txt](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/requirements.txt)
*   Arduino library configuration: [gemini_LLM_btn.ino#L14-L22](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L14-L22)
*   Flutter package manifest: [pubspec.yaml](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/pubspec.yaml)
