# Table-Bondhu Coding Conventions (`CONVENTIONS.md`)

This document records the coding style guidelines, naming rules, formatting standards, and error-handling patterns used in the Table-Bondhu project.

---

## 1. Naming & Case Style Conventions

### A. ESP32 Firmware (C++ / Arduino)
*   **Constant Definitions:** Defined in uppercase using `#define` (e.g. `#define BUTTON_PIN 14`, `#define THEME_GIRL 0`).
*   **Global Variables:** Written in camelCase (e.g. `currentState`, `timerSecondsRemaining`, `cachedLdr`).
*   **Functions:** Written in camelCase (e.g. `setAppState()`, `soundBuzzerAlarm()`, `formatBubbleText()`).
*   **State Enums:** Written in uppercase prefixed with `STATE_` (e.g. `STATE_CLOCK`, `STATE_LISTENING`, `STATE_THINKING`).

### B. Companion Server (Python)
*   **Global Variables:** Written in snake_case (e.g. `is_sleeping`, `scheduled_sleep_time`, `active_conn`).
*   **Functions:** Written in snake_case (e.g. `play_speech_on_laptop()`, `delete_reminder_by_index()`).
*   **Class Names:** Written in PascalCase (e.g. `CompanionRestHandler`).
*   **File Logs:** Written in snake_case (e.g. `sleep_sessions.log`, `transcriptions.log`).

### C. Companion App (Dart / Flutter)
*   **Class/Widget Names:** Written in PascalCase (e.g. `SleepAnalyticsScreen`, `PikaSleepingAnimation`).
*   **State Class Names:** Written with a leading underscore in PascalCase (e.g. `_SleepAnalyticsScreenState`).
*   **Variables/Methods:** Written in camelCase (e.g. `_fetchSleepLogs()`, `_saveSleepWindow()`). Private variables/methods are prefixed with a leading underscore (e.g. `_windowStart`, `_isLoading`).

---

## 2. Formatting & Structure Guidelines

*   **ESP32 C++ Indentation:** Uses 2-space indentation. Functions are grouped logically, keeping helper functions at the top of the file and the main `setup()` and `loop()` routines at the bottom.
*   **Python Indentation:** Uses standard PEP 8 compliant 4-space indentation.
*   **Flutter Dart Indentation:** Uses standard 2-space indentation with trailing commas to format nested widget trees correctly.

---

## 3. Error Handling Patterns

### A. ESP32 Firmware (C++)
*   **Socket Failures:** Managed by checking connection states (`client.connected()`). If a socket connection fails, the client prints an error to the serial monitor and retries connecting every 10 seconds, allowing the clock display to keep running locally without crashing.
*   **NTP Timeout:** If fetching the local time over NTP fails during startup, the client uses a fallback default time and allows sleep mode by default, preventing the initialization loop from blocking.

### B. Python Server (CPython)
*   **REST Server Exceptions:** Wrapped in standard try-except blocks. If a request fails, the server returns a structured JSON error response (e.g., `{"error": "Index must be an integer"}`) and an appropriate HTTP status code (such as `400` or `500`).
*   **ASR/TTS Loading Errors:** If local models fail to load during startup, the server logs the error to the console, falls back to alternative engines (such as Google TTS), and continues running rather than halting execution.

### C. Android App (Flutter)
*   **HTTP Route Exceptions:** REST requests are wrapped in `.timeout(const Duration(seconds: 5))` blocks. If a request fails or times out, the app catches the exception, logs it to the debug console, and displays a user-friendly error message in a `SnackBar` without crashing the app.

---

## 4. Evidence Paths
*   Firmware configuration defines: [gemini_LLM_btn.ino#L24-L35](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L24-L35)
*   Python server helper definitions: [agentic_companion.py#L182-L224](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L182-L224)
*   Flutter private state variables: [main.dart#L1316-L1330](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/table_bondhu_app/lib/main.dart#L1316-L1330)
