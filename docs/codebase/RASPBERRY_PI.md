# Raspberry Pi 4 Server Architecture & Optimizations (`RASPBERRY_PI.md`)

This document provides a low-level, technical breakdown of the Raspberry Pi 4 optimized server ([`agentic_companion_raspberrypi_4.py`](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py)), detailing the architectural shifts, resource-saving techniques, and diagnostic Q&A for academic reviews.

---

## 1. Architectural Comparison: PC vs. Raspberry Pi 4

To support on-device execution on a 4GB RAM Raspberry Pi 4, several computationally heavy frameworks were replaced with lightweight, quantized alternatives:

| Subsystem | PC Server (`agentic_companion.py`) | Raspberry Pi Server (`agentic_companion_raspberrypi_4.py`) | Optimization Rationale |
| :--- | :--- | :--- | :--- |
| **LLM Inference** | Remote/Local REST API to LM Studio (running `qwen2.5-coder-1.5b-instruct`) | Local Ollama Instance (`qwen2.5:0.5b` or `qwen2.5:1.5b`) | Ollama manages memory-mapped storage and handles context loading efficiently on low-RAM Linux devices. |
| **Speech-to-Text (ASR)** | ONNX Runtime executing Parakeet Conformer-TDT model | Faster-Whisper Conformer (`tiny.en` quantized to `int8`) | Faster-Whisper with INT8 quantization reduces the memory footprint to ~70MB and uses ARM NEON instructions to speed up execution. |
| **Text-to-Speech (TTS)** | Sherpa-ONNX / Google TTS fallback | Sherpa-ONNX Piper VITS (`en_US-amy-low`) / Espeak fallback | Piper VITS synthesizes natural speech locally, falling back to `espeak` if resources are low. |
| **Audio Server** | Windows Waveform Audio / Linux ALSA (`aplay`) | Pipewire Audio Daemon (`pw-play`) | Matches the modern default audio framework used in Raspberry Pi OS Bookworm. |

---

## 2. Technical Breakdown of Pi 4 Optimizations

```
                     ┌────────────────────────────────────────┐
                     │  RASPBERRY PI 4 OPTIMIZATION ACTIONS   │
                     └───────────────────┬────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
┌─────────────────┐             ┌─────────────────┐             ┌─────────────────┐
│  Ollama Tuning  │             │ ASR Language    │             │ Tolerant Tag    │
│  num_predict=50 │             │ Bypass          │             │ Regex tolerates │
│  Restricts CPU  │             │ Bypasses lang   │             │ LLM formatting  │
│  decoding loops │             │ detection passes│             │ brace/brackets  │
└─────────────────┘             └─────────────────┘             └─────────────────┘
```

### A. LLM Resource Capping & Hallucination Defense
Small models like Qwen 0.5B are highly resource-efficient but prone to structural hallucinations (such as generating slightly incorrect command tags).
1.  **Context Capping (`num_predict`):** Capped the output length to 50 tokens (`"num_predict": 50`). Because the rules limit responses to 15 words, this stops the model's generation loop early, reducing CPU load and improving response times.
2.  **Sampling Parameters:** Set `temperature` to `0.1`, `top_k` to `20`, and `top_p` to `0.85`. This restricts the search space, reducing memory usage and making tag generation highly predictable.
3.  **Tolerant Regular Expressions:** Replaced strict tag matches with flexible, case-insensitive patterns:

```python
# --- Tag Matcher (agentic_companion_raspberrypi_4.py: Lines 1279 - 1283) ---
add_match = re.search(
    r'[\[{]\s*CMD\s*:\s*ADD_REMINDER\s*\|\s*([^|]+?)\s*\|\s*(ABS|REL|abs|rel)\s*\|\s*([^\]}]+?)\s*[\]}]', 
    ai_answer, 
    re.I
)
```

This allows the parser to successfully process tags even if the model outputs curly braces `{CMD: ...}` or adds extra spaces.

### B. ASR Performance Tuning (Language Specification Bypass)
By default, Whisper-based models perform a preliminary forward pass over the first audio segment to detect the spoken language.
*   **The Fix:** Added `language="en"` to `asr_model.transcribe()` inside the `keyword_detection_loop()` (running every 500ms). This bypasses the language detection phase entirely, saving significant CPU cycles and reducing response latency.

### C. Audio Normalization via `pydub`
To handle audio streams uploaded from the mobile app via REST `/api/voice_chat`:
*   **The Fix:** Loaded the uploaded WAV file into `AudioSegment`, forcing the channel layout to mono, the frame rate to $16000\text{Hz}$, and the bit depth to 16-bit. This removes the WAV file header and normalizes the format before passing the raw data to the transcription engine.

---

## 3. Teacher Viva Q&A

### Q1: Why did you choose Faster-Whisper instead of standard Whisper for speech recognition on the Pi 4?
**Answer:** The standard OpenAI Whisper library runs on PyTorch, which is unoptimized for low-power ARM CPUs and has a high memory footprint (often exceeding 500MB for the tiny model). 
**Faster-Whisper** uses CTranslate2, a fast inference engine for Transformer models. By quantizing the weights to **integer 8-bit (`int8`)**, it reduces memory usage to ~70MB and leverages ARM NEON vector instructions, decoding audio up to 4x faster than PyTorch Whisper on the Raspberry Pi 4.

### Q2: How does the Ollama keep-alive setting affect memory management on a 4GB RAM system?
**Answer:** The `keep_alive="15m"` parameter tells Ollama to keep the LLM weights loaded in RAM for 15 minutes after the last request. 
On a 4GB RAM system, loading a model from disk into RAM takes 3–5 seconds. Keeping the model in memory ensures responses to user requests are generated instantly, while the 15-minute timeout prevents the model from permanently consuming memory when the desk clock is idle.

### Q3: What happens if the local LLM generates a malformed command tag, such as `[CMD:ADD_REMINDER|buy milk|REL|5 mins]`?
**Answer:** The server uses tolerant regular expressions (`re.IGNORECASE`) to parse commands.
Even if the model generates a lowercase command (`[cmd:add_reminder...]`) or includes extra spaces, the parser will extract the key arguments. If the time parameter itself is malformed (e.g. `5 mins` instead of `5m`), `parse_relative_time` returns `None`, and the server sends a clean error message back to the display without crashing.

### Q4: Why is setting `num_predict` to 50 critical for running LLMs on a single-board computer?
**Answer:** By default, LLMs will continue generating text until they output an end-of-sequence (EOS) token or hit their maximum prediction limit (usually 128 or 256 tokens). 
On a Raspberry Pi 4 CPU, generating each token takes 50–100ms. Since our display rules restrict answers to 15 words, capping the generation limit at 50 tokens prevents the model from generating unnecessary text, saving CPU time and ensuring quick responses.

---

## 4. Evidence Mappings
*   Ollama chat options: [agentic_companion_raspberrypi_4.py#L140-L148](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L140-L148)
*   ASR model initialization: [agentic_companion_raspberrypi_4.py#L160](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L160)
*   ASR language bypass parameter: [agentic_companion_raspberrypi_4.py#L684](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L684)
*   Tolerant Tag matching: [agentic_companion_raspberrypi_4.py#L1277-L1293](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L1277-L1293)
*   AudioSegment resample parsing: [agentic_companion_raspberrypi_4.py#L1523-L1528](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L1523-L1528)
*   TCP client wake alarm silence: [agentic_companion_raspberrypi_4.py#L904](file:///F:/__KUET%20CSE22/Assignments/IOT/Table-Bondhu-main/agentic_companion_raspberrypi_4.py#L904)
