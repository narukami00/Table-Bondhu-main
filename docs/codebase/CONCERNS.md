# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Plaintext WiFi Credentials committed to repo | [config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h) | Exposure of private network credentials | Move credentials out of the sketch file into an offline config or local AP portal |
| High | Hardcoded model paths | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L129) | Model loading breaks on any machine except the developer's laptop | Load paths dynamically using environment variables (`.env`) |
| Medium | Single connection limit | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L568) | Multiple client connections will overwrite the active socket reference, dropping existing clients | Refactor connection routing to handle multiple connection descriptors concurrently |

### 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Single-file monolithic server | Rapid initial prototyping | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py) | High complexity, difficult to maintain, easy to introduce regression bugs | Break into modules: TCP Server, Audio Pipeline, Agent Handler, Reminder Store |
| Single-file monolithic firmware | Rapid initial prototyping | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) | Hard to manage state machines, high chances of stack overflow/RAM limits | Modularize sketches into separate utility headers (.h) and source files (.cpp) |
| LDR theme-switching audio gap | Shared hardware ADC channels on ESP32 | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L649-L653) | Brief audio streaming drops every 1.5 seconds | Implement non-blocking asynchronous reading or shift LDR to a separate ADC controller |
| Standby connection timeout | Server socket times out in 30s when client stops audio stream | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L919) and [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1349) | Client disconnects and reconnects repeatedly during sleep | Mitigated: Client sends periodic heartbeat (`PIR:SLEEP`) every 15s to keep socket alive |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| Plaintext credentials in code | A02:2021-Cryptographic Failures | [config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h) | None | Credentials committed to repository |
| No API validation or auth | A01:2021-Broken Access Control | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L886) | None | Unauthenticated client can trigger alarms, update reminders, or flood the LLM |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Linear audio resampling | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L225) | Audible aliasing artifacts | Speech transcription accuracy degrades | Employ higher-quality interpolation/resampling library |
| Sequential LLM processing | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1194) | UI blocks during inference | Slow response times | Run chat inference asynchronously |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `gemini_LLM_btn.ino` | Manages multiple async states (I2S DMA, display, button edge, PIR, timer) | 17 commits in 90 days | Build comprehensive unit mocks for sensors before updating |
| `agentic_companion.py` | Handles binary framing, speech buffer, audio fallback, LLM completions | 15 commits in 90 days | Use automated diagnostic scripts to test packet parsing |

### 6) `[ASK USER]` Questions

1. [ASK USER] Should we secure raw TCP communication using TLS?
2. [ASK USER] Is there a preference for replacing `winsound` with `pyaudio` or `sounddevice` for cross-platform compatibility?
3. [ASK USER] Should we pin dependencies in `requirements.txt`?

### 7) Evidence

- [docs/codebase/.codebase-scan.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/codebase/.codebase-scan.txt)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
