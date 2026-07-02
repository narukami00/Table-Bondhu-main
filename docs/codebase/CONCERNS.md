# Codebase Concerns

## Core Sections (Required)

### 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Plaintext credentials in code | [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h) | Committing plaintext Wi-Fi credentials and IP addresses to version control exposes local network details. | Extract credentials to a git-ignored header file or template. |
| High | Unauthenticated TCP socket listener | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L499) | Anyone on the local network can connect to TCP port 8080 to stream audio, inject state commands, or hijack the assistant. | Implement a simple validation header handshake or signature verification. |
| Medium | JSON database transaction safety | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L204) | Concurrent file writes to `reminders.json` from different threads (ASR parser vs. scheduler loop) can corrupt the reminders data. | Migrate reminders storage to a thread-safe SQLite database. |
| Medium | Monolithic sketch complexity | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) | Combining sensor polling, FSM state updates, graphic drawing, TCP sockets, and I2S stream operations in a single file makes validation difficult. | modularize drawing routines and network setup into separate header files. |

---

## 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Hardcoded local paths | Absolute paths under C:\Users\Rafsan Riasat\ are hardcoded for ONNX models | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L107) | Companion server will fail to start on other machines if ASR files are not in the exact folder path. | Convert paths to relative or configurable variables in `.env`. |
| Legacy Python Modules | Duplicate scripts and outdated structures exist in folders | `Python/`, `gemini_LLM.py`, `gemini_LLM2.py` | Confusion about which files are currently active and maintained. | Archive or clean up unused legacy scripts and subdirectory templates. |

---

## 3) Security Concerns

| Risk | OWASP category (if applicable) | Evidence | Current mitigation | Gap |
|------|--------------------------------|----------|--------------------|-----|
| No network validation | A01:2021-Broken Access Control | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py) | None. Sockets are open to any IP address. | Missing validation handshakes. |
| Plains secrets committed | A02:2021-Cryptographic Failures | [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h) | Plaintext credentials in code. | Exclude configuration parameters from version control. |

---

## 4) Performance and Scaling Concerns

* **ASR Model Size & CPU Load**: Running speech-to-text transcription locally is resource-intensive. If hosted on a low-spec CPU, voice interactions will experience significant latency.
* **Heap Fragmentation**: Dynamically allocating the `themedBuf` (32KB) and string manipulation on the ESP32 can lead to heap fragmentation and runtime crashes over extended operational periods.

---

## 5) Fragile/High-Churn Areas

* **`gemini_LLM_btn/gemini_LLM_btn.ino`**: Active FSM controller sketch. Changes to state code blocks can cause compile-time dependencies or state locks.
* **`agentic_companion.py`**: Active companion script. Serves as the central integration layer connecting ASR, local rules, Gemini LLM, and winsound playback.

---

## 6) `[ASK USER]` Questions

1. **[ASK USER]** Should we migrate local credentials from `config.h` to an ESP32 EEPROM/Preferences configuration interface to prevent committing plaintext credentials?
2. **[ASK USER]** Should we compile the duplicate ASR transcriber utilities and main loop entry points inside the `Python/` directory into a unified, modular CLI application?
3. **[ASK USER]** Do we want to support multiple concurrent ESP32 clients connecting to the companion server, or should the server remain restricted to a single connection?

---

## 7) Evidence

- [gemini_LLM_btn/config.h](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/config.h)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
