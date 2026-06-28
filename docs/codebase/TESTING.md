# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: None (no standard framework is integrated, such as `pytest` or `unittest`)
- Assertion/mocking tools: Manual execution checks and console printing only
- Commands:

```bash
# Evaluate transcription capabilities at different audio sample rates
python test_rates.py

# Batch transcribe wav recordings and print output accuracy compared to declared rates
python analyze_recordings.py
```

### 2) Test Layout

- Test file placement pattern: Root folder directories (`test_*.py`, `analyze_*.py`).
- Naming convention: Prepend scripts with `test_` or `analyze_`.
- Setup files and where they run: N/A.

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | No | None | No unit tests exist in the project |
| Integration | Partial (Manual) | Speech Recognition, LLM completion, TCP connections | Verification is performed manually by running the server, flashing the ESP32, and executing voice checks |
| E2E | Partial (Manual) | Whole system activation, wake-phrase trigger, alarm scheduler | Handled manually with the desk assistant setup and LM Studio integration |

### 4) Mocking and Isolation Strategy

- Main mocking approach: No mocking framework or setup is defined.
- Isolation guarantees: No isolated test environments. Testing directly mutates local recording directories (`recordings_analysis/` and `recordings/`).
- Common failure mode in tests: Running tests offline results in errors for components that require active internet (gTTS, Google Speech recognition, Gemini API). For offline models, errors occur if the model directories are missing on the local machine path.

### 5) Coverage and Quality Signals

- Coverage tool + threshold: None.
- Current reported coverage: None.
- Known gaps/flaky areas: Audio sample mismatch testing relies on a hardcoded file path (`recordings_analysis/rec_20260627_093341.wav`). If this file is missing or renamed, `test_rates.py` will fail with a FileNotFoundError.

### 6) Evidence

- [test_rates.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/test_rates.py)
- [analyze_recordings.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/analyze_recordings.py)
- [COMPANION_GUIDE.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/COMPANION_GUIDE.md)
