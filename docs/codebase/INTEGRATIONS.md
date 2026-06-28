# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| Google Gemini API | API | Cloud LLM response provider | API Key (`GEMINI_API_KEY`) | High (Standard Backend) | [Python/llm/gemini_client.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/llm/gemini_client.py) |
| LM Studio API | API (Local) | Local LLM response provider for Gemma | No auth (Local network port `1234`) | High (Companion Backend) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L29) |
| Google Text-to-Speech (gTTS) | API | Text synthesis to speech PCM bytes | No auth (Public endpoint) | Medium | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L148) |
| Google Speech Recognition | API | Transcribing user audio to text | No auth (Public endpoint) | High (Standard Backend) | [Python/audio/transcriber.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/audio/transcriber.py#L26) |
| Local ASR ONNX Model | Library (Local) | Converts audio stream to text offline | No auth (Local file model) | High (Companion Backend) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L104) |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| `reminders.json` | Stores active alarm tasks, trigger times, and status checklists | File IO functions (`_load_reminders_internal`, `_save_reminders_internal`) | No transactions, file corruption under concurrent writes, or dirty reads. | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L259-L300) |

### 3) Secrets and Credentials Handling

- Credential sources:
  - Loaded via [Python/config/settings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py) from the git-ignored [.env](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/.env) file.
  - Stored inside compile-time constants in `config.h` for ESP32.
- Hardcoding checks: Source code files do not contain hardcoded Gemini API keys. However, default Wi-Fi passwords and server IPs are hardcoded in [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h).
- Rotation or lifecycle notes: [TODO] Rotation is manual by editing `.env` or `config.h`.

### 4) Reliability and Failure Behavior

- Retry/backoff behavior: The ESP32 client loops indefinitely to re-establish the connection if the server drops it, delaying 2 seconds between attempts.
- Timeout policy: `conn.settimeout(10)` is applied on incoming TCP client sockets in the standard backend. [Evidence: [Python/server/handlers.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/handlers.py#L16)]
- Circuit-breaker or fallback behavior: None.

### 5) Observability for Integrations

- Logging around external calls: Logger outputs status lines before sending raw text to LLMs, and outputs the returned string on success or prints stack trace on failure.
- Metrics/tracing coverage: None.
- Missing visibility gaps: No remote telemetry or APM tracing is configured. Failures are only traceable via local stdout console output.

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [Python/llm/gemini_client.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/llm/gemini_client.py)
- [Python/server/handlers.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/handlers.py)
- [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h)
- [SETUP.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/SETUP.md)
