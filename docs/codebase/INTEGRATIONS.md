# Table-Bondhu API & Third-Party Integrations (`INTEGRATIONS.md`)

This document records the external API integrations, local model configurations, endpoints, and data payloads used in the Table-Bondhu project.

---

## 1. Local LLM Integration (LM Studio)

The companion server routes natural language prompts to a local **LM Studio** instance running a quantized instruction-tuned model.

*   **Default Endpoint:** `http://localhost:1234/v1/chat/completions` (OpenAI-compatible REST API).
*   **Target Model:** `qwen2.5-coder-1.5b-instruct`
*   **Request Payload Format:**
    ```json
    {
      "model": "qwen2.5-coder-1.5b-instruct",
      "messages": [
        {"role": "system", "content": "SYSTEM_INSTRUCTION_HERE"},
        {"role": "user", "content": "USER_TRANSCRIBED_SPEECH_HERE"}
      ],
      "temperature": 0.3,
      "max_tokens": 80
    }
    ```
*   **Response Payload Parsing:** The server extracts the raw reply string, parses any embedded bracketed commands (like `[CMD:START_SLEEP]` or `[CMD:ADD_REMINDER]`), and strips these tags before sending the text to the client.

---

## 2. Weather Integration (Open-Meteo)

The companion server periodically fetches real-time weather reports for the clock display.

*   **Base URL:** `https://api.open-meteo.com/v1/forecast`
*   **Query Parameters:**
    *   `latitude`: `22.8956` (KUET Campus, Khulna, Bangladesh)
    *   `longitude`: `89.5011`
    *   `current_weather`: `true`
*   **Request Method:** HTTP GET (using Python's `urllib.request` library with a custom `User-Agent` header).
*   **Response Payload Format:**
    ```json
    {
      "current_weather": {
        "temperature": 28.5,
        "windspeed": 12.5,
        "winddirection": 180,
        "weathercode": 3,
        "is_day": 1,
        "time": "2026-07-15T22:30:00Z"
      }
    }
    ```
*   **Weather Code Mapping:** The server maps the returned `weathercode` to one of four weather states:
    *   `0`: Sunny (Icon index `0`)
    *   `1, 2, 3, 45, 48`: Cloudy (Icon index `1`)
    *   `51 - 67, 80 - 82`: Rainy (Icon index `2`)
    *   `71 - 77, 85 - 86`: Snowy (Icon index `3`)

---

## 3. Local Speech Recognition Integration (Parakeet ASR)

The server runs speech-to-text locally using the Conformer-TDT model.

*   **ONNX Model Path:** Controlled by the `ASR_MODEL_PATH` variable in the server's `.env` configuration file.
*   **Processing Engine:** `onnx_asr` library running quantized `int8` conformer models.
*   **Input Requirements:** Accepts raw floating-point arrays (`float32` between `-1.0` and `1.0`) sampled at exactly $16000\text{Hz}$ mono.

---

## 4. Local Text-to-Speech Integration ( VITS Piper )

The server synthesizes speech responses locally using the Piper engine.

*   **Piper Model Assets:**
    *   `PIPER_MODEL_PATH`: points to `models/vits-piper-en_US-amy-low/en_US-amy-low.onnx`
    *   `PIPER_LEXICON_PATH`: lexicon dictionary file.
    *   `PIPER_TOKENS_PATH`: tokens file.
*   **Synthesis Engine:** `sherpa-onnx` library.
*   **Output Format:** Generates a raw floating-point array (`float32`) sampled at $22050\text{Hz}$ mono.

---

## 5. Evidence Paths
*   LM Studio endpoints: [agentic_companion.py#L90-L98](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L90-L98)
*   Open-Meteo coordinate queries: [agentic_companion.py#L585-L612](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L585-L612)
*   Parakeet initialization check: [agentic_companion.py#L129-L142](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L129-L142)
*   Piper TTS model path configurations: [agentic_companion.py#L144-L162](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L144-L162)
