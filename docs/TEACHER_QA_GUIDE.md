# Table-Bondhu — IoT Presentation & Teacher Q&A Guide

This guide compiles detailed architectural explanations, implementation decisions, and coding details for the **Table-Bondhu** project. It is structured to prepare you for any questions a teacher, course coordinator, or examiner might ask during project evaluation or viva presentations.

---

## 1. System Architecture & Dual-Node Communication

### Q: Why did you use a dual-node (Client-Server) architecture? Why not run everything on the ESP32?
* **Answer**: The ESP32 is a low-power microcontroller with limited RAM (typically 520KB) and CPU speed (240MHz). Running deep-learning models for Speech-to-Text (ASR), Large Language Models (LLM), and Text-to-Speech (TTS) locally on the ESP32 is computationally impossible. 
* **Solution**: The ESP32 acts as a **thin-client** (sensing user inputs, streaming audio, and drawing the UI), while a local laptop/PC acts as the **thick-server** (running ASR, LLM, and TTS pipelines).

### Q: How do the ESP32 and Python Server communicate?
* **Answer**: They communicate over a raw, bidirectional **TCP Socket** on port `8080`. 
* **Nagle's Algorithm (TCP_NODELAY)**: We explicitly disable Nagle's algorithm (`client.setNoDelay(true)` on ESP32, and `socket.TCP_NODELAY` on the Python server). This disables TCP buffering delays, ensuring state commands (like button presses or alarm triggers) are sent instantly with zero lag.

### Q: What is the communication protocol? How does the server separate raw audio bytes from commands?
* **Answer**: We use a **mixed binary/text framing protocol**.
* Raw audio bytes are continuously streamed as binary data over TCP.
* Commands (like `CMD:WOKE`, `___END___`, `LDR:value`, `PIR:MOTION`) are sent as plain-text ASCII strings terminated by `\n`.
* **Marker-Based Extraction**: The Python server maintains a dynamic `recv_buffer`. Instead of splitting incoming packets strictly by newlines (which would corrupt binary audio since raw audio contains random `0x0A` bytes), the server scans the buffer byte-by-byte for known command headers (e.g., `b"CMD:"`, `b"PIR:"`, `b"LDR:"`). Once found, it extracts the command and leaves the raw audio stream intact.

---

## 2. Audio Capture & Processing Pipeline

### Q: How is audio captured on the ESP32?
* **Answer**: Audio is captured using the ESP32's built-in 12-bit Analog-to-Digital Converter (ADC1, GPIO 32) controlled by the **I2S (Inter-IC Sound) DMA (Direct Memory Access)** controller.
* **Sampling Rate**: 16kHz, 16-bit mono.
* **Why I2S DMA?**: DMA allows the I2S peripheral to write audio samples directly to RAM without involving the main CPU cores, preventing audio stutter and keeping UI animations smooth.

### Q: What software filtering is applied to the raw audio on the ESP32?
* **Answer**: The raw ADC input suffers from a DC bias (offset) and low amplitude. We apply two real-time filters:
  1. **DC Blocking Filter**: We implement a first-order high-pass filter:
     $$\text{output} = \text{input} - \text{prev\_input} + 0.995 \times \text{prev\_output}$$
     This dynamically centers the audio waveform around `0`.
  2. **12x Gain & Clamping**: We multiply the filtered signal by `12.0` to boost volume, and clamp it between `-32768` and `32767` to prevent integer overflow (anti-robotic distortion clamping).

---

## 3. Server-Side AI Pipelines (ASR, LLM, TTS)

### Q: How does the Automatic Speech Recognition (ASR) work offline?
* **Answer**: We run the **NVIDIA Parakeet Conformer-TDT (0.6B parameters)** model locally on the Python server using the `onnx_asr` runtime.
* **Why Parakeet TDT?**: It is an extremely lightweight, quantized Conformer model that transcribes voice commands in milliseconds without needing an internet connection.

### Q: How is the local LLM integrated? How do you restrict its responses?
* **Answer**: The transcribed text is sent to a local **LM Studio** endpoint running the `qwen2.5-coder-1.5b-instruct` model via an OpenAI-compatible API.
* **Prompt Engineering**: We use a custom `SYSTEM_INSTRUCTION` that forces the LLM to keep its answers under 15 words (fitting on the TFT display) and output specific command tags (like `[CMD:ADD_REMINDER|...]` or `[CMD:START_SLEEP]`) when voice triggers are detected.

### Q: How does the Text-to-Speech (TTS) engine work? How is the Pikachu voice effect done?
* **Answer**:
  1. **ASR to Audio**: We use the **Offline VITS (Piper)** TTS engine (`sherpa-onnx`) with fallbacks to Google TTS.
  2. **Pikachu Voice Modulation**: We load the synthesized audio into `pydub`. We increase the speed and pitch of the raw samples by **40%** to generate the cute, high-pitched Pikachu voice, then resample it to a standard `44100Hz` wav buffer for winsound playback.

---

## 4. UI Structure & Animation Rendering

### Q: How do you prevent screen flickering when rendering animations on the TFT screen?
* **Answer**: We use **Double Buffering (TFT_eSprite)**. 
* Instead of drawing directly to the physical screen over SPI (which causes flickering as pixels are overwritten), we write all visual elements (bitmaps, text bubbles, clock overlays) to an off-screen RAM buffer called `faceSprite`. 
* Once the entire frame is fully constructed in RAM, we push the sprite to the physical display in a single, high-speed SPI transfer (`faceSprite.pushSprite(0, 0)`).

### Q: Why do the Sprite sizes change dynamically in code?
* **Answer**: 
  * In the active clock/idle states, the sprite size is **128x110**. This leaves the bottom 50 pixels of the screen free to render speech bubbles or status overlays directly on the TFT.
  * During **Sleep** and **Sleep Summary** modes, the sprite is enlarged to **128x160** to support full-screen rendering. Pushing a full 128x160 sprite requires 40KB of RAM, which we allocate dynamically on the ESP32 heap.

### Q: How is the speech bubble word wrap and text pagination implemented?
* **Answer**: Since the ST7735 screen is tiny, we implemented a custom pagination engine:
  1. **Word-Wrapping**: We split the LLM response text into words and dynamically compute line lengths (based on character width). If a word exceeds the 18-character bubble margin, it wraps to the next line.
  2. **Pagination**: A maximum of 4 lines fit in the speech bubble. If a message is longer, it splits the text into pages. The user can press the physical **BOOT** button (GPIO 0) to flip to the next page.

---

## 5. Sleep Monitoring & Sleep Machine Logic

### Q: Describe your sleep detection conditions.
* **Answer**: Sleep monitoring is triggered when:
  1. **Clock State Inactivity**: The device has been idle in `STATE_CLOCK` for more than 30 seconds.
  2. **Dark Environment**: The LDR light sensor reads a value less than `500` (representing night or a dark room).
  3. **Mostly Motionless (PIR Density Filter)**: Instead of requiring absolute silence, we check the activity density. We sample the debounced PIR sensor once a second for 30 seconds. If motion is detected in **3 seconds or less** out of the 30-second sliding history window, the user is considered "mostly motionless".

### Q: How do you prevent false wake-ups when the user first falls asleep?
* **Answer**: We implement a **20-second settling-in grace period** (`lastSleepEnteredMs`). When the device transitions to `STATE_SLEEPING`, the PIR sensor is ignored for the first 20 seconds, allowing the user to adjust blankets or settle down without waking the clock up.

### Q: How is sleep tracked on the server? What metrics are recorded?
* **Answer**: The server tracks:
  * **Start/End Times** and total **Duration** (hours).
  * **Movements**: Incremented every time the client transitions to `PREWAKE` (minor movements) or sends a `PIR:MOTION` trigger (extra waves).
  * **Noise Monitoring**: When sleeping, the client streams audio continuously. The server calculates the RMS level of each chunk. It tracks `average_noise`, `max_noise`, and counts `noise_events` (RMS > 600) representing coughing, talking, or snoring.
  * **Light Level**: Periodic LDR values are collected to calculate average room brightness.
  * **Classification**: Sessions under 30 mins are discarded. Sessions $\ge 4$ hours (or starting between 10 PM and 8 AM) are logged as `"actual_sleep"`. Otherwise, they are classified as a `"nap"`.
  * **Sleep Quality**: Rated `"Good"`, `"Fair"`, or `"Poor"` based on movements/hour, noise RMS, and room light levels.

---

## 6. Sleep Summary UI Screen

### Q: How does the Sleep Summary UI work on wakeup?
* **Answer**: Upon waking up, the server computes the session data and sends a command: `UI_SLEEP_SUMMARY:type:duration:movements:avg_noise:avg_ldr:quality\n`.
* The ESP32 switches to `STATE_SLEEP_SUMMARY` and displays a dashboard:
  * Styled title header (**SLEEP SUMMARY** or **NAP SUMMARY**).
  * Big bold text showing **Duration** (e.g., `8.2h`).
  * Quantitative stats for movements, average noise, and light levels.
  * A custom capsule badge displaying sleep quality (e.g., **QUALITY: GOOD**).
* **Exit**: The screen auto-dismisses back to the clock after **15 seconds** or immediately upon pressing the tactile button.

---

## 7. Alarm, Timer, and Weather Features

### Q: How do alarms and reminders work concurrently with sleep?
* **Answer**: The Python server runs a background thread `alarm_scheduler` polling `reminders.json`. If an alarm fires while the device is sleeping, it sends `UI_ALARM:taskName\n` to the ESP32. The ESP32 immediately wakes up, clears the sleeping state, and plays the alarm sound + flashes the screen.

### Q: How is weather data obtained and drawn?
* **Answer**: The server periodically fetches weather data (temperature and description code) from the **Open-Meteo API** (using KUET coordinates). It sends a command `WEATHER:temp:desc:iconIndex\n` to the ESP32. The ESP32 draws a custom weather icon (sun, cloud, rain, or snow) and temperature on the top-left corner of the clock overlay.

---

## 8. Adaptive Display & Light Themes

### Q: How is light-based theme switching implemented?
* **Answer**: The LDR sensor (GPIO 34) reads analog light intensity. We map this analog value (0–4095) into 4 distinct themes:
  * **Night** (LDR < 300)
  * **Dusk** (LDR < 700)
  * **Autumn** (LDR < 1200)
  * **Bright** (LDR $\ge$ 1200)
* When a theme changes, we switch the global color values (`COLOR_BG`, `COLOR_ACCENT`, `COLOR_BORDER`) to match the theme palette, creating an adaptive, light-sensitive display.
