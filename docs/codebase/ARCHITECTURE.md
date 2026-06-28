# Architecture

## Core Sections (Required)

### 1) Architectural Style

- Primary style: Layered Client-Server Architecture + State-Driven Firmware (FSM)
- Why this classification:
  - The Python backend follows a layered data flow (TCP Socket Server -> Audio Transcription -> LLM processing -> TCP response/audio stream).
  - The ESP32 firmware is structured as a Finite State Machine (FSM) driven by state flags (`STATE_IDLE`, `STATE_LISTENING`, `STATE_THINKING`, `STATE_SPEAKING`, etc.).
- Primary constraints:
  - **Microcontroller Limitations**: The ESP32 has limited RAM and flash memory, meaning image assets (sprites) must be carefully compiled to avoid heap exhaustion or boot crashes (e.g. allocating buffers in heap malloc instead of static RAM).
  - **Latency and Network Sync**: Sockets must remain connected and responsive. Threading locks are required on the server to prevent interleaved network writes when alarms fire during active conversation.
  - **Local resource dependency**: Local ASR (Whisper/Parakeet) and local LLM (LM Studio) require high CPU/GPU compute on the host machine.

### 2) System Flow

```text
[ESP32 Mic / Button] -> [TCP Socket Audio Stream] -> [Local WAV File] -> [ASR (Whisper/Parakeet)] -> [LLM (Gemini/Gemma)] -> [Reminder Command parser] -> [TCP Text/TTS Response] -> [ESP32 Screen/Speaker]
```

1. **Activation**: The user presses a physical button or says the wake phrase *"wake up"*. The ESP32 enters the `STATE_LISTENING` state.
2. **Audio Streaming**: The ESP32 streams raw PCM audio bytes (16-bit, 16kHz mono) inside a `___START___` and `___END___` wrapper over TCP port 8080.
3. **Buffering & Saving**: The Python server receives the TCP stream, extracts raw bytes, and writes them to a temporary wave file (`temp_live.wav` or timestamped recording).
4. **Speech-to-Text**: The transcription module (either Google Web Speech API or local ONNX Parakeet/Whisper ASR) transcribes the wav file into raw text.
5. **LLM Query & Parsing**: The text is forwarded to the LLM (LM Studio Local Gemma or Google Gemini API). The LLM processes the query and appends action tags (e.g., `[CMD:ADD_REMINDER|...|...]`) for scheduler updates.
6. **Command Processing**: If an agentic reminder tag is found, the server updates `reminders.json` database.
7. **Response & TTS**: The text answer is sent back via the TCP connection, or synthesized into a TTS audio file and streamed back to the microcontroller's speaker (along with a state change code).

### 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `agentic_companion.py` / `main.py` | Initializing servers, managing socket threads, scheduling alarms, calling ASR/LLM. | Rendering display graphics, managing hardware pins. | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L25-L48) |
| `Python/audio/` | Transcribing wave files and structuring I/O audio properties. | Directly communicating with LLMs or sockets. | [Python/audio/processor.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/audio/processor.py) |
| `Python/llm/` | LLM client creation, system prompting, conversation memory cleaning. | Writing audio files, socket bindings. | [Python/llm/gemini_client.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/llm/gemini_client.py) |
| `gemini_LLM_btn.ino` | Running the hardware loop, drawing character sprites to the screen, sounding buzzers, polling button states, shifting TFT themes based on LDR sensors. | Deciding reminder trigger times, running speech recognition algorithms. | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L81-L92) |

### 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| Finite State Machine (FSM) | [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino#L81-L92) | Controls the UI layout, character animations, and buzzer alerts on the ESP32 dynamically based on connection and request states. |
| Background Thread Workers | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L8), [gemini_LLM.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM.py#L64) | Enables continuous non-blocking task execution (like checking alarm schedules or transcribing audio segments in queues). |
| Threading Locks (Mutex) | [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L47-L49) | Protects shared socket connections and chat session history from race conditions during concurrent server triggers (e.g. alarm ringing while user speaks). |

### 5) Known Architectural Risks

- **Concurrent Socket Access Risk**: When an alarm triggers on the server background scheduler thread, it may attempt to send a message to the ESP32. If the user is currently talking or the system is sending LLM replies, the socket stream could become corrupted without strict lock validation. [Evidence: [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L47)]
- **ASR/LLM Inference Blocking**: Running local model inference on CPU (Whisper/LM Studio) introduces blocking lag times, which makes the voice assistant feel unresponsive if the machine is low-powered. [Evidence: [test_rates.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/test_rates.py)]
- **Zero Authentication Protocol**: The TCP protocol has no encryption, auth tokens, or TLS handshake. Anyone on the local network can connect to the port 8080. [Evidence: [Python/server/tcp_server.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/server/tcp_server.py)]

### 6) Evidence

- [agentic_companion.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion.py)
- [gemini_LLM_btn/gemini_LLM_btn.ino](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/gemini_LLM_btn/gemini_LLM_btn.ino)
- [Python/main.py](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/Python/main.py)
- [docs/API.md](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/docs/API.md)
