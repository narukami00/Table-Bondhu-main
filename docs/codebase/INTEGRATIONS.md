# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| LM Studio | HTTP Local API | OpenAI-compatible chat completion service for Qwen LLM | None (localhost) | High | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L90-L98) |
| Open-Meteo | HTTP Web API | Fetches local temperature and weather descriptions | None (Free Tier API) | Medium | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L441-L472) |
| pool.ntp.org | NTP Protocol | Network Time Protocol calibration for clock display | None | High | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1257) |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| `reminders.json` | JSON-backed flat file database storing active and fired reminders | Standard Python `json` library with a thread-safe `db_lock` mutex | File corruption on concurrent writes, loss of data on server crash | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L278-L439) |

### 3) Secrets and Credentials Handling

- Credential sources: WiFi SSID and password credentials are stored in `gemini_LLM_btn/config.h`. Other config options (e.g. model paths) are loaded using Python `dotenv`.
- Hardcoding checks: WiFi credentials are committed directly as plaintext.
- Rotation or lifecycle notes: `[TODO]` No credential rotation mechanism exists.

### 4) Reliability and Failure Behavior

- Retry/backoff behavior:
  - ESP32 TCP Client: Retries connection to the Python server every 10 seconds if disconnected.
  - NTP Client: Retries time synchronization every 30 seconds if local time reads fail.
  - LLM / Weather Calls: No retry logic is implemented; exceptions are caught and printed.
- Timeout policy: Socket timeout set to 30 seconds on Python server.
- Circuit-breaker or fallback behavior: Python server falls back to Google TTS (`gTTS`) if offline TTS loader fails.

### 5) Observability for Integrations

- Logging around external calls: Stderr/stdout prints are printed around LLM calls, Open-Meteo queries, and reminder DB interactions.
- Metrics/tracing coverage: `[TODO]` None implemented.
- Missing visibility gaps: No structured log analysis or alert dashboard.

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
