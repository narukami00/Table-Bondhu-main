# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

List only meaningful top-level directories and files.

| Path | Purpose | Evidence |
|------|---------|----------|
| `Python/` | Contains the modules for the standard, cloud-connected backend server | [docs/STRUCTURE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/STRUCTURE.md) |
| `Arduino/` | Legacy/modular directory for Arduino source code, utils, and image headers | [docs/STRUCTURE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/STRUCTURE.md) |
| `gemini_LLM_btn/` | Folder containing the main active button-triggered / LDR adaptive theme Arduino sketch | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino) |
| `live_rec/` | Folder containing the main active continuous streaming, hands-free live-recording Arduino sketch | [live_rec/live_rec.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/live_rec/live_rec.ino) |
| `assets/` | Animated sprite bitmaps in JPEG/PNG formats for characters (Pikachu and Girl) | [docs/STRUCTURE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/STRUCTURE.md) |
| `docs/` | Contains project documentation including codebase knowledge, API details, and structure descriptions | [docs/README.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/README.md) |
| `recordings/` | Directory where uploaded voice commands from standard backend are saved as WAV files | [Python/config/settings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/config/settings.py#L18) |
| `recordings_analysis/` | Directory where recorded audio clips from local companion are saved for transcription evaluation | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L32) |
| `agentic_companion.py` | Standalone entry point file for the wake-word-activated, hands-free agentic companion server | [COMPANION_GUIDE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/COMPANION_GUIDE.md) |

### 2) Entry Points

- Main runtime entry:
  - Python Cloud Backend: [Python/main.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/main.py)
  - Python Hands-free Local Companion: [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- Secondary entry points (worker/cli/jobs):
  - `check_api.py`: Check connection to LM Studio API models.
  - `test_rates.py`: Performance testing of speech recognition across varying audio sample rates.
  - `analyze_recordings.py`: Analyze existing WAV files to verify transcription accuracy.
- How entry is selected (script/config):
  - Run explicitly via shell commands.
  - Arduino chooses which server it points to by changing configuration in its `config.h`.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `Python/server/` | TCP Connection handling and routing requests | Business logic, ASR transcription, LLM client initialization |
| `Python/audio/` | Speech transcription and raw audio buffer wave compilation | Directly interacting with sockets, LLM calling |
| `Python/llm/` | Interacting with Gemini APIs, conversation history formatting | Handling audio files, socket connections |
| `Arduino/utils/` | Reusable drivers for peripheral setup (I2S microphone, ST7735 screen, WiFi link) | Animated layouts, alarm schedules, state-specific screens |

### 4) Naming and Organization Rules

- File naming pattern: 
  - Python: snake_case (e.g. `agentic_companion.py`, `tcp_server.py`)
  - Arduino Header Files: snake_case (e.g. `config.h`, `i2s_setup.h`) or simple lowercase (e.g. `display.h`)
  - Arduino Sketches: PascalCase or snake_case with folder match (e.g. `gemini_LLM_btn.ino` in `gemini_LLM_btn/`)
- Directory organization pattern: Layer-based and sketch-specific
  - Layer-based for standard Python backend (server, audio, llm, utils)
  - Sketch-specific directories in the root for active ESP32 firmware development (`live_rec/`, `gemini_LLM_btn/`)
- Import aliasing or path conventions: 
  - Standard relative imports in Python package modules (e.g. `from ..utils import logger` inside `Python/server/tcp_server.py`).
  - No custom path aliasing configured in Python.

### 5) Evidence

- [docs/STRUCTURE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/STRUCTURE.md)
- [Python/main.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/main.py)
- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [live_rec/live_rec.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/live_rec/live_rec.ino)
