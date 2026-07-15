# Table-Bondhu Communication & Framing Protocol (`COMMUNICATION.md`)

This document provides a low-level, technical breakdown of the network architecture, bidirectional framing protocols, REST API endpoints, and automatic discovery services used in the Table-Bondhu project.

---

## 1. Network Architecture Overview

Table-Bondhu uses a two-channel communication system over Wi-Fi (IP/TCP and IP/UDP):

```
                     ┌──────────────────────────────────────────────┐
                     │            Flutter Android App               │
                     │  • Connects via HTTP REST to Python Server   │
                     │  • Discovers Server IP via UDP Broadcast     │
                     └──────────────┬───────────────────────────────┘
                                    │
                                    │ HTTP REST (Port 8888)
                                    ▼
┌──────────────┐    TCP Socket      ┌───────────────────────────────┐
│ ESP32 Client │ ◄────────────────► │         Python Server         │
│  (Port 8080) │    Raw PCM + Cmds  │  • Broadcasts UDP Beacon      │
└──────────────┘                    └───────────────────────────────┘
```

1.  **Primary Channel (ESP32 <-> Server):** A persistent, raw bidirectional TCP socket connection on port `8080`. Used to stream voice bytes to the server and receive display commands.
2.  **Companion Channel (App <-> Server):** Stateless HTTP REST API endpoints on port `8888` for UI chat, configuration adjustments, and sleep logs.
3.  **Discovery Channel (App <-> Server):** UDP broadcast packets on port `9999` sent by the server to announce its IP address to the mobile app.

---

## 2. Bidirectional Mixed Framing Protocol (TCP)

### A. The Challenge: Audio Streaming vs. Control Commands
We need to stream raw 16-bit analog audio samples ($16000\text{Hz}$, mono, 2 bytes per sample) from the ESP32 to the server. At the same time, the ESP32 needs to send status updates (e.g., LDR values, PIR motion, button triggers), and the server needs to send UI state changes (e.g., speech bubble text, weather updates, sleep commands).
*   *Why we cannot use standard HTTP/WebSockets:* HTTP has high header overhead. WebSockets require complex parsing libraries on the microcontroller, which increases CPU load and memory usage.
*   *The Solution:* A custom **mixed binary/ASCII TCP stream**.

### B. Frame Format
*   **Audio Data:** Raw binary bytes. No prefix, no suffix, no length indicators. It is streamed continuously.
*   **Control Commands:** Newline-terminated (`\n`) ASCII strings prefixed with specific marker tags (e.g., `CMD:`, `PIR:`, `LDR:`).

### C. Server-Side Extraction Algorithm
If the server split incoming packets by newlines (`\n`, which is ASCII `0x0A`), the binary audio data would get corrupted. Raw digitized audio samples can randomly contain `0x0A` bytes, leading to false command splits.
To prevent this, the Python server runs a **Marker-Based Buffer Scan**:

```python
# --- Extract Command from Recv Buffer (agentic_companion.py: Lines 777 - 795) ---
def _extract_command(self, buffer: bytearray, marker: bytes) -> tuple:
    """
    Scans the buffer for a command marker.
    If found, returns (bytes_before_marker, command_bytes, bytes_after_command).
    Otherwise, returns None.
    """
    idx = buffer.find(marker)
    if idx == -1:
        return None
        
    # Commands are terminated by a newline character (\n)
    end_idx = buffer.find(b'\n', idx)
    if end_idx == -1:
        return None  # Command is incomplete, wait for more TCP packets
        
    before = buffer[:idx]
    cmd = buffer[idx:end_idx]
    after = buffer[end_idx + 1:]
    return before, cmd, after
```

#### How the Extraction Loop Works:
1.  The socket receives raw bytes and appends them to a dynamic `recv_buffer` byte array.
2.  The server scans `recv_buffer` for known command prefixes (e.g., `b"CMD:"`, `b"PIR:"`, `b"LDR:"`, `b"TIMER_DONE"`).
3.  If a prefix is found:
    *   It checks for a terminating `\n`.
    *   If a newline is found, it extracts all bytes between the start of the buffer and the prefix, labeling them as **raw audio bytes** (audio chunk).
    *   It extracts the command string (e.g., `PIR:MOTION`), parses and executes it, then discards the command bytes from the buffer.
    *   It keeps the remaining bytes in `recv_buffer` to process next.
4.  If no prefix is found, everything in the buffer is treated as raw audio data.

---

## 3. ESP32 Client Socket Engine (Firmware)

The ESP32 firmware manages the socket state using a state loop in `loop()`:

```cpp
// --- Check and Maintain Server Connection (gemini_LLM_btn.ino: Lines 1831 - 1848) ---
if (!client.connected()) {
  unsigned long now = millis();
  if (now - lastServerConnectAttemptMs > 10000) { // Retry connection every 10 seconds
    lastServerConnectAttemptMs = now;
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("Attempting connection to companion server...");
      if (client.connect(activeServerIp.c_str(), SERVER_PORT)) {
        client.setNoDelay(true); // Disable Nagle's algorithm for zero lag
        Serial.println("Connected to server successfully!");
        setAppState(STATE_CLOCK);
      } else {
        Serial.println("Connection to server failed. Retrying in 10s...");
      }
    }
  }
}
```

---

## 4. Server REST API Specification

The Python server runs an HTTP REST server on port `8888`. Below is the complete API endpoint registry:

### 1. `GET /api/reminders`
*   **Description:** Returns all active, unfired reminders.
*   **Response Payload:**
    ```json
    [
      {
        "task": "Buy milk",
        "trigger_time": "2026-07-16T15:00:00",
        "display_time": "03:00 PM",
        "fired": false
      }
    ]
    ```

### 2. `POST /api/reminders`
*   **Description:** Adds a new reminder.
*   **Request Payload:**
    ```json
    {
      "task": "Water plants",
      "time": "2026-07-16 18:30:00"
    }
    ```
*   **Response Payload:** `{"status": "SUCCESS"}`

### 3. `POST /api/reminders/delete`
*   **Description:** Marks a reminder as deleted (sets `fired = true`).
*   **Request Payload:** `{"index": 1}`
*   **Response Payload:** `{"status": "SUCCESS", "deleted": "Water plants"}`

### 4. `POST /api/reminders/clear`
*   **Description:** Clears all reminders.
*   **Response Payload:** `{"status": "SUCCESS"}`

### 5. `GET /api/sleep/status`
*   **Description:** Returns the current sleep status and start timestamp.
*   **Response Payload:**
    ```json
    {
      "is_sleeping": true,
      "start_time": "2026-07-15T22:30:00"
    }
    ```

### 6. `POST /api/sleep/start`
*   **Description:** Forcibly starts sleep mode.
*   **Request Payload:** `{"type": "sleep"}` (or `"type": "nap"`)
*   **Response Payload:** `{"status": "SUCCESS"}`

### 7. `POST /api/sleep/wake`
*   **Description:** Wakes the system up manually, stops the active sleep session, and returns the session summary.
*   **Response Payload:**
    ```json
    {
      "status": "SUCCESS",
      "session": {
        "type": "actual_sleep",
        "duration_hours": 7.5,
        "movement_count": 12,
        "quality": "Good",
        "average_noise": 120.5,
        "average_ldr": 15.0
      }
    }
    ```

### 8. `GET /api/sleep/window`
*   **Description:** Returns the active hours window for automatic PIR sleep detection.
*   **Response Payload:** `{"start_hour": 22, "end_hour": 10}`

### 9. `POST /api/sleep/window`
*   **Description:** Updates the automatic sleep detection window.
*   **Request Payload:** `{"start_hour": 23, "end_hour": 9}`
*   **Response Payload:** `{"status": "SUCCESS", "start_hour": 23, "end_hour": 9}`

---

## 5. Comprehensive Teacher Viva Q&A

### Q1: Why did you use raw TCP sockets instead of HTTP for streaming audio from the ESP32?
**Answer:** HTTP is a stateless protocol that requires sending headers (such as `Host`, `Content-Length`, `User-Agent`) with every request. Sending $16\text{kHz}$ PCM audio requires streaming continuous chunks of data ($32\text{KB/sec}$). Creating a new HTTP request for every chunk would introduce massive network overhead and connection handshake delays. A raw TCP socket keeps a single connection open, allowing us to send raw binary packets with zero header overhead.

### Q2: What is Nagle's Algorithm, and why did you disable it (`TCP_NODELAY`)?
**Answer:** Nagle's algorithm is a TCP optimization designed to reduce network traffic. It buffers small outgoing packets and waits to send them until it can combine them into a single larger packet.
While this saves bandwidth, it introduces latency (often 100–200ms). For a real-time voice assistant, buffering delays would make button clicks and status reports feel sluggish. Setting `client.setNoDelay(true)` disables Nagle's algorithm, forcing TCP to send every packet immediately.

### Q3: Why did you choose UDP instead of TCP for server auto-discovery?
**Answer:** TCP requires knowing the server's IP address beforehand to perform a 3-way handshake. When the server starts up, it doesn't know the IP address of the phone running the app. 
UDP supports **broadcasting**. The server broadcasts announcements to the local subnet (e.g., `255.255.255.255`) on port `9999`. Any device on the same Wi-Fi network can receive this broadcast, read the server's IP from the packet, and save it.

### Q4: How does your code handle partial command packets received over TCP?
**Answer:** TCP streams data as a continuous flow of bytes rather than distinct packets. A single read call might return only part of a command (e.g. `CMD:STA` instead of `CMD:START_SLEEP`).
The server handles this in `_extract_command`. If a command prefix (e.g., `CMD:`) is found in the buffer but there is no matching newline terminator (`\n`), the function returns `None`. This leaves the partial command in the buffer, allowing the next socket read to complete the command string.

---

## 6. Evidence Paths
*   TCP socket listener setup: [agentic_companion.py#L1954-L1982](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1954-L1982)
*   Marker parsing logic: [agentic_companion.py#L1166-L1233](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1166-L1233)
*   Command extractor definition: [agentic_companion.py#L777-L795](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L777-L795)
*   REST endpoint handlers: [agentic_companion.py#L1681-L1947](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1681-L1947)
*   Disable Nagle's algorithm: [gemini_LLM_btn.ino#L1838](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L1838)
