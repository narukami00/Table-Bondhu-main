# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Hardcoded model paths and server URLs | [agentic_companion.py:L107](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L107), [agentic_companion.py:L29](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L29) | The companion backend will fail immediately on other user systems if the ONNX model files are not installed at the exact absolute path under `C:\Users\Rafsan Riasat\`. | Move local model paths and LM Studio endpoints to a configurable location (e.g. `.env` or a config file). |
| High | Lack of authentication on TCP server port | [Python/server/tcp_server.py:L24](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/tcp_server.py#L24) | Anyone on the local Wi-Fi network can connect to port `8080` to stream audio to the server or view assistant outputs. | Implement a lightweight message authorization/token header or secure connection scheme. |
| Medium | Insecure file operations | [agentic_companion.py:L259-L300](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L259-L300) | `reminders.json` is read and written in full on every access without transaction safety, risking corruption during concurrent events. | Implement file locking or migrate scheduler storage to SQLite database. |
| Medium | Heavy CPU/ASR Blocking | [gemini_LLM.py:L56](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM.py#L56), [test_rates.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/test_rates.py) | Running transcription models like Whisper locally on standard CPUs incurs significant processing delay. | Offload transcription tasks to a pipeline worker or configure GPU acceleration when available. |

### 2) Technical Debt

List the most important debt items only.

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Monolithic Arduino sketch | Standardized code evolution merged multiple functions (graphics, audio streaming, Wi-Fi connectivity, LDR sensing, alarm logic) into one file. | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) | File grows hard to test or debug; changes to rendering logic can easily break critical networking routines. | Extract graphics, networking, and sensors into separate reusable files inside `Arduino/utils/`. |
| Monolithic Companion script | Built as a standalone companion proof of concept. | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py) | High maintenance complexity; mixes server management, model loading, TTS generation, scheduling, and local OS audio controls. | Restructure the companion code into a modular package format mirroring the standard `Python/` codebase. |
| Unused configuration imports | Variables from `settings.py` (like secondary WiFi parameters) are loaded but never referenced in active server scripts. | [Python/config/settings.py:L21-L31](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py#L21-L31) | Developer confusion about which credentials are used at runtime. | Clean up settings script to remove unused configuration declarations. |

### 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| Plaintext configuration secrets | A02:2021-Cryptographic Failures | [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h) | None. Credentials are committed to version control. | Wi-Fi passwords and server IP configs are visible in public files. Should be excluded from git using templates. |
| No network validation | A01:2021-Broken Access Control | [Python/server/tcp_server.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/tcp_server.py) | None. Port 8080 accepts any socket connections. | Missing authentication checks on incoming network packets. |

### 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| Sequential processing pipeline | [agentic_companion.py:L59-L100](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L59-L100) | Server handles audio transcription, LLM calls, and gTTS synthesis sequentially on a single client handler thread. | The user experiences significant latency between speaking and receiving screen updates. | Parallelize TTS prep or stream ASR segments incrementally. |
| High RAM allocation crash | [gemini_LLM_btn/gemini_LLM_btn.ino:L114](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L114) | Static RAM allocation of 32KB buffer causes device boot crash. | Microcontroller runs out of memory and bootloops. | Use heap malloc allocation inside `setup()` instead of static declarations (already partially applied). |

### 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `gemini_LLM_btn/gemini_LLM_btn.ino` | Main codebase file with mixed graphics, state logic, and socket operations. Highly complex layout rules. | 10 commits in last 90 days. | Ensure all modifications are fully tested locally. Keep state transition functions short and isolated. |
| `gemini_LLM_btn/images.h` | Contains large hex bitmap declarations that affect build size and compiler memory limits. | 2 commits in last 90 days. | Exclude unused image files from compiles using preprocessor directives (conditional compilation). |

### 6) `[ASK USER]` Questions

1. [ASK USER] Should we consolidate the two Python servers (`Python/main.py` and `agentic_companion.py`) into a single, modular package backend with command-line flags?
2. [ASK USER] Should we establish a secure key validation or device authentication handshake to restrict TCP access on port 8080?
3. [ASK USER] Do we need to package the ONNX ASR models inside the project repository (or download them dynamically at installation) rather than referencing an absolute path under `C:\Users\Rafsan Riasat`?

### 7) Evidence

- [.codebase-scan.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/codebase/.codebase-scan.txt)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [Arduino/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Arduino/config.h)
