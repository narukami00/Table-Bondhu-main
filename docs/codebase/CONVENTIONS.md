# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files (Python) | lowercase with underscores | `agentic_companion.py` | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py) |
| Files (Arduino) | camelCase | `gemini_LLM_btn.ino` | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| Functions (Python) | snake_case | `parse_timer_duration` | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L173) |
| Functions (Arduino) | camelCase | `updateAnimations` | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L642) |
| Classes (Python) | PascalCase | `LocalChatSession` | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L78) |
| Constants (Arduino) | UPPER_CASE | `SLEEP_TIMEOUT_MS` | [gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L88) |

### 2) Formatting and Linting

- Formatter: `[TODO]` None configured.
- Linter: `[TODO]` None configured.
- Most relevant enforced rules: `[TODO]` None configured.
- Run commands: `[TODO]` None.

### 3) Import and Module Conventions

- Import grouping/order: Python imports are organized with standard library modules first, followed by third-party packages.
- Alias vs relative import policy: Standard library and absolute imports only. No relative imports or aliases are utilized.
- Public exports/barrel policy: Not applicable (single-file scripting structure).

### 4) Error and Logging Conventions

- Error strategy by layer:
  - Python Server: Wrap processes (e.g. LLM completion, TCP socket writing, reminders IO) in `try...except` blocks, print exceptions to stdout/stderr, and send fallback messages/commands to the client.
  - ESP32 Firmware: Basic check statements (e.g. `client.connected()`, checking return codes of NTP sync) and safety state recovery timeouts (returning to clock screen if stuck in LISTENING/THINKING for 30s).
- Logging style and required context fields: Console output prints using custom formatting tags like `[*]`, `[TIMER]`, `[BUZZER]`, `[Error]`. Audio recordings and transcriptions are logged to local files under `recordings_analysis/` and `recordings_analysis/transcriptions.log`.
- Sensitive-data redaction rules: `[TODO]` None implemented (WiFi credentials stored in plaintext in `config.h`).

### 5) Testing Conventions

- Test file naming/location rule: `[TODO]` No tests exist.
- Mocking strategy norm: `[TODO]` No tests exist.
- Coverage expectation: `[TODO]` No tests exist.

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [docs/STRUCTURE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/STRUCTURE.md)
