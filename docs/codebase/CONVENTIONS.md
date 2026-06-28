# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | Python: `snake_case`, Arduino: `PascalCase` or `snake_case` | `agentic_companion.py`, `gemini_LLM_btn.ino` | [.codebase-scan.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/codebase/.codebase-scan.txt) |
| Functions/methods | Python: `snake_case`, Arduino: `camelCase` | `def start_server():`, `void switchTheme(int idx)` | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L107), [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L101) |
| Types/Classes | Python: `PascalCase` | `class ClientHandler:` | [Python/server/handlers.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/handlers.py#L10) |
| Constants/env vars | Python/Arduino: `UPPER_CASE` | `LM_STUDIO_URL`, `BUTTON_PIN` | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L29), [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L11) |

- Private methods: Python private helper methods are prefixed with a single underscore (e.g. `_load_reminders_internal()`). [Evidence: [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L259)]

### 2) Formatting and Linting

- Formatter: No automated formatter config found. [Evidence: [.codebase-scan.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/codebase/.codebase-scan.txt)]
- Linter: No automated linter config found. [Evidence: [.codebase-scan.txt](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/codebase/.codebase-scan.txt)]
- Most relevant enforced rules: Coding style relies on manual python PEP-8 practices.
- Run commands: None.

### 3) Import and Module Conventions

- Import grouping/order:
  - Standard library imports first (e.g. `socket`, `threading`, `time`).
  - Third-party package imports second (e.g. `numpy`, `onnx_asr`, `dotenv`).
  - Local workspace modules third (e.g. `from config import settings`).
- Alias vs relative import policy: Relative imports are used for Python files inside subpackages (`from ..utils import logger`), whereas top-level scripts use direct module imports.
- Public exports/barrel policy: Empty package descriptors (`__init__.py` files) exist inside `Python/` subfolders (`audio/`, `config/`, `llm/`, `server/`, `utils/`) but do not export specific lists.

### 4) Error and Logging Conventions

- Error strategy by layer:
  - Python scripts wrap runtime tasks in `try...except` loops to prevent server crashes. Missing variables raise clear `ValueError` instances or print warning notices.
  - Arduino handles socket link failures gracefully by printing "Disconnected" status to the screen and re-entering the connection loop after a delay.
- Logging style and required context fields:
  - Standard backend uses the standard library `logging` wrapper configured in [Python/utils/logger.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/utils/logger.py). Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
  - Companion script uses direct `print()` statements for logs with prefixes like `[Alarm]`, `[TTS]`, `[TTS Error]`.
- Sensitive-data redaction rules: [TODO] No explicit redaction filters exist in logs.

### 5) Testing Conventions

- Test file naming/location rule: Custom scripts are placed directly in the project root folder starting with `test_` or `analyze_` prefix (e.g. `test_rates.py`, `analyze_recordings.py`).
- Mocking strategy norm: No mock libraries used. Testing relies on playing back local WAV file recordings (e.g. `recordings_analysis/rec_20260627_093341.wav`).
- Coverage expectation: No automated coverage tracking is present.

### 6) Evidence

- [Python/utils/logger.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/utils/logger.py)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [test_rates.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/test_rates.py)
