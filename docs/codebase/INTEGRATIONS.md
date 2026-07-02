# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| Google Gemini API | API | Cloud LLM text response generator | API Key (`GEMINI_API_KEY`) | High | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L116) |
| Google Text-to-Speech (gTTS) | HTTPS API | Synthesizes response text into raw MP3 speech audio | No Auth | High | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L158) |
| Open-Meteo Weather API | HTTPS API | Fetches current weather temperature and conditions for local coordinates | No Auth | Medium | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L372) |
| Local ASR ONNX Model | Library | Offline speech-to-text transcriber using ONNX weights | No Auth | High | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L104) |
| winsound | OS Library | Plays Pikachu voice WAV files and loops system hand alarm sound on laptop speakers | No Auth | High | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L122) |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| `reminders.json` | Persistent store for active reminder lists, alarm tasks, and trigger times | JSON File I/O under thread lock (`db_lock`) | Dirty reads or file corruptions under simultaneous scheduled write events | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L204) |

### 3) Secrets and Credentials Handling

- **Credential sources**:
  - `GEMINI_API_KEY` is loaded from the environment `.env` file via `python-dotenv`.
  - Wi-Fi credentials (`WIFI_SSID`, `WIFI_PASSWORD`) and connection details are stored as plaintext preprocessor macros in `config.h` for the ESP32.
- **Hardcoding checks**: API Keys are excluded from commits. However, network configuration settings are committed as plaintext macros in [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h).
- **Rotation or lifecycle notes**: Password rotation is manual. Recompilation and flashing of the ESP32 is required to apply updated Wi-Fi or Server IP configs.

### 4) Reliability and Failure Behavior

- **Retry/backoff behavior**:
  - The ESP32 attempts connection to WiFi for up to 5 seconds. If it fails, it enters "Offline Mode".
  - In loop, if the TCP connection to the companion server drops, the ESP32 polls non-blockingly every 10 seconds to re-establish connection, skipping the attempt entirely if the Wi-Fi connection is down.
- **Timeout policy**:
  - Open-Meteo weather requests utilize a 5-second HTTP request timeout.
  - Winsound alarm sounds loop indefinitely until a dismiss action stops them or a 30-second server scheduler auto-dismiss/60-second local ESP32 buzzer timeout triggers.
- **Circuit-breaker or fallback behavior**:
  - If weather fetching fails or is offline, the ESP32 clock face displays the default banner `"HAVE A GOOD DAY!"` instead of blank slots.
  - If the socket connection to the server fails, the clock face and idle screens render a `"DISCONNECTED"` status bar, allowing local features (clock and local Focus Timer countdowns) to remain fully operational.

### 5) Observability for Integrations

- **Logging around external calls**:
  - Connection retries, weather data synchronization results, and API errors are logged to standard output (`Serial.print` on ESP32, `print` on Python).
- **Metrics/tracing coverage**:
  - No remote tracing (APM) or unified telemetry is integrated. Observability is limited to local debug logs.

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
