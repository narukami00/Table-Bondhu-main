# Table-Bondhu Technical Concerns & Limitations (`CONCERNS.md`)

This document records the identified tech debt, hardware limitations, edge-case vulnerabilities, and performance bottlenecks in the Table-Bondhu project.

---

## 1. Hardware Power & Voltage Concerns

*   **ESP32 Power Rail Sagging:**
    *   *The Concern:* The ESP32 Dev Module uses a small onboard linear regulator (such as the AMS1117) to drop 5V USB input down to 3.3V.
    *   *The Risk:* When the ESP32 Wi-Fi module operates (drawing up to 250mA peak) while the TFT screen backlight, active buzzer, and PIR sensor are active, the total current draw can exceed the regulator's limit. This causes the 3.3V power rail to sag, which can lead to random resets, garbled microphone audio, or screen flicker.
    *   *Recommendation:* Use a high-quality USB power source supplying at least 1.5A. Connect a $100\mu\text{F}$ decoupling capacitor across the ESP32's 3.3V and GND pins to smooth out transient current spikes.

---

## 2. API & Network Dependencies

*   **Hardcoded Coordinates for Weather Forecasts:**
    *   *The Concern:* The Open-Meteo weather endpoint in `agentic_companion.py` uses hardcoded latitude and longitude coordinates for Khulna, Bangladesh (`latitude=22.8956&longitude=89.5011`).
    *   *The Risk:* If the device is moved to another city, the clock will continue to display weather data for Khulna.
    *   *Recommendation:* [ASK USER] Add IP-based geolocation lookup on the server to set coordinates dynamically on startup.
*   **LM Studio Connection Timeout:**
    *   *The Concern:* The OpenAI REST client in `agentic_companion.py` uses default timeout parameters when sending prompt queries to LM Studio.
    *   *The Risk:* If the laptop is running on battery power or performing heavy calculations, local LLM generation can stall. If generation takes longer than 10 seconds, the connection will drop, leaving the client stuck in `STATE_THINKING` until the socket is reset.
    *   *Recommendation:* Add a 30-second timeout limit to LLM completions.

---

## 3. Storage & Index Constraints

*   **List Index Deletion Vulnerability:**
    *   *The Concern:* The reminder deletion route `/api/reminders/delete` accepts a simple 1-based integer index corresponding to the active reminders list.
    *   *The Risk:* If the list of active reminders changes (e.g. a reminder triggers and is automatically deleted) between the time the user opens the app and the time they tap delete, the indices will shift. This can result in deleting the wrong reminder.
    *   *Recommendation:* Generate and use a unique ID (UUID) for each reminder, rather than relying on its index in the list.

---

## 4. Evidence Paths
*   Open-Meteo coordinates parameter: [agentic_companion.py#L588](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L588)
*   Index-based deletion handling: [agentic_companion.py#L1937](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1937)
*   Reminder model structure: [reminders.json](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/reminders.json)
