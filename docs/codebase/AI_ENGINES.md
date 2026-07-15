# Table-Bondhu Offline AI Engines (`AI_ENGINES.md`)

This document provides a low-level, technical breakdown of the offline machine learning, natural language processing, and audio synthesis pipelines running on the Table-Bondhu companion server.

---

## 1. Automatic Speech Recognition (ASR) Pipeline

Table-Bondhu performs local, offline Speech-to-Text using the **NVIDIA Parakeet Conformer-TDT (Time-Delay Neural Network / Transducer)** model.

```
┌──────────────┐   Raw PCM bytes (TCP)    ┌───────────────────────────────────┐
│ ESP32 Client │ ───────────────────────► │ Python ASR Processor              │
└──────────────┘                          │ 1. Convert PCM to float32         │
                                          │ 2. Resample to 16kHz via interp   │
                                          │ 3. Run ONNX inference (Parakeet)  │
                                          └─────────────────┬─────────────────┘
                                                            │ Text Transcript
                                                            ▼
```

### A. Initialization
The ASR runtime is initialized on server startup using the `onnx_asr` library. It loads a quantized `int8` ONNX model file.

```python
# --- Load ASR Model (agentic_companion.py: Lines 130 - 134) ---
try:
    import onnx_asr
    print("[*] Loading local Parakeet ASR model (quantization=int8)...")
    asr_model = onnx_asr.load_model('nemo-conformer-tdt', path=ASR_MODEL_PATH, quantization='int8')
    print("[+] ASR Model loaded successfully.")
except Exception as e:
    print(f"[-] Failed to load ONNX ASR: {e}")
```

### B. Signal Processing & Resampling
The incoming raw TCP buffer contains 16-bit signed integers (`int16`). ASR engines require normalized floating-point arrays (`float32` between `-1.0` and `1.0`) sampled at $16000\text{Hz}$ to transcribe correctly.
If the incoming audio sample rate deviates due to clock discrepancies, the server resamples it in real-time using linear interpolation:

```python
# --- Process Speech Samples (agentic_companion.py: Lines 1423 - 1430) ---
audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
if measured_rate > 0 and measured_rate != 16000 and len(audio_np) > 0:
    # Resample to 16000Hz using linear interpolation
    target_count = int(len(audio_np) * 16000 / measured_rate)
    src_idx = np.arange(len(audio_np))
    tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
    audio_np = np.interp(tgt_idx, src_idx, audio_np)

# Normalize sample amplitude to [-1.0, 1.0] range
audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
text = asr_model.recognize(audio_float, sample_rate=16000).strip()
```

---

## 2. LLM Orchestration & Prompt Constraints

Once the voice command is transcribed, the server sends it to a local instance of **LM Studio** using an OpenAI-compatible API client.

### A. Strict System Prompts (The "Guardrails")
Since the ESP32’s TFT screen has a small $128\times 160$ pixel area, long answers would overrun the display. The system prompt forces the LLM to keep its answers under **15 words**, avoid markdown/emojis, and output structured command tags (`[CMD:...]`):

```python
# --- LLM Prompts (agentic_companion.py: Lines 55 - 77) ---
SYSTEM_INSTRUCTION = """You are a helpful and cute desk assistant built into a tiny microcontroller. 
Your answers are displayed on a 160x128 pixel screen. 
You MUST be extremely concise. Keep every answer under 15 words. 
Do not use markdown formatting. You MUST NOT use any emojis or emoticons in your responses.

You have the ability to manage reminders, alarms, and sleep tracking.
- If the user says they are going to sleep, taking a nap, or tell you to enter sleep/nap mode, append: [CMD:START_SLEEP]
  Example: "I am taking a nap" -> "Goodnight! Sweet dreams. [CMD:START_SLEEP]"
  Example: "Going to sleep now" -> "Goodnight! Sleep well. [CMD:START_SLEEP]"
- If the user asks you to add an alarm or reminder, extract the task/description and target time.
  Append: [CMD:ADD_REMINDER|task|YYYY-MM-DD HH:MM:SS]
  Example: "Remind me to call Mom at 3:30 PM today" (assume today is 2026-07-15) -> "Adding reminder for 3:30 PM. [CMD:ADD_REMINDER|call Mom|2026-07-15 15:30:00]"
"""
```

---

## 3. Offline Text-to-Speech (TTS) & Pikachu Pitch Modulation

Synthesizing cute, character-accurate voice responses locally requires a two-step pipeline:

```
┌─────────────────┐    VITS Synthesizer    ┌──────────────────────┐
│  Text Response  │ ─────────────────────► │  Raw float32 WAV     │
└─────────────────┘                        └──────────┬───────────┘
                                                      │
                                                      │ Rescale to int16, Pitch+Speed +40%
                                                      ▼
┌─────────────────┐                        ┌──────────────────────┐
│ Laptop Speaker  │ ◄───────────────────── │   Modified WAV       │
└─────────────────┘                        └──────────────────────┘
```

### A. VITS Offline Synthesis ( Piper )
We run the **VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech)** engine locally via `sherpa-onnx`.

```python
# --- Piper TTS Synthesizer (agentic_companion.py: Lines 144 - 159) ---
try:
    import sherpa_onnx
    print("[*] Loading local VITS (Piper) model...")
    tts_config = sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
            model=PIPER_MODEL_PATH,
            lexicon=PIPER_LEXICON_PATH,
            tokens=PIPER_TOKENS_PATH
        ),
        num_threads=2,
        debug=False
    )
    tts_engine = sherpa_onnx.OfflineTts(tts_config)
except Exception as e:
    print(f"[-] Failed to load offline VITS: {e}")
```

### B. Pikachu Voice Effect via Pydub
To match the Pikachu theme, the synthesized speech is modulated. We increase the pitch and speed by **40%**, making it sound like a high-pitched Pikachu voice:

```python
# --- Pitch and Speed modulation (agentic_companion.py: Lines 188 - 208) ---
def play_speech_on_laptop(text):
    # 1. Synthesize text to raw WAV using Piper
    audio_data = tts_engine.generate(text)
    raw_samples = np.array(audio_data.samples, dtype=np.float32)
    
    # 2. Rescale to 16-bit signed integer format
    int16_samples = (raw_samples * 32767.0).astype(np.int16)
    
    # 3. Load into Pydub AudioSegment
    sound = AudioSegment(
        int16_samples.tobytes(),
        frame_rate=audio_data.sample_rate,
        sample_width=2,
        channels=1
    )
    
    # 4. Shift pitch up by 40% (modifying raw sample rate)
    new_sample_rate = int(sound.frame_rate * 1.40)
    pikachu_sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
    pikachu_sound = pikachu_sound.set_frame_rate(sound.frame_rate) // Pitch shifted, keep standard sample rate
    
    # 5. Play over local laptop speakers
    pikachu_sound.export("response.wav", format="wav")
    import winsound
    winsound.PlaySound("response.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
```

---

## 4. Comprehensive Teacher Viva Q&A

### Q1: What is a "Conformer" architecture, and why is it used for Speech-to-Text?
**Answer:** A Conformer (Convolution-augmented Transformer) combines self-attention (Transformer) and convolution layers. Self-attention captures global, long-range dependencies in audio, while convolution captures local, short-range dependencies (like phonetic transitions). This hybrid design achieves higher transcription accuracy with fewer parameters, making it ideal for running locally on a standard laptop CPU.

### Q2: Why does the server resample raw incoming audio from the ESP32?
**Answer:** The ESP32's internal ADC clock relies on an RC oscillator, which is prone to slight frequency drift caused by heat or voltage variations. It may sample at $15800\text{Hz}$ or $16200\text{Hz}$ instead of exactly $16000\text{Hz}$.
If this audio is fed directly to the ASR model, the pitch will shift and the voice will sound distorted, leading to transcription errors. We track the actual duration of the raw stream to compute the true sample rate, then use linear interpolation to resample the audio to a standard $16000\text{Hz}$ before recognition.

### Q3: How do you extract structured commands (like `ADD_REMINDER`) from natural LLM text?
**Answer:** We use **Prompt Engineering**. We instruct the LLM to append special bracketed tags (`[CMD:...]`) at the end of its response.
Once the LLM generates a response, the server uses a regular expression (`re.search(r'\[CMD:([^\]]+)\]', text)`) to check for these tags. If a tag is found, the server extracts the parameters (e.g. description, timestamp), runs the corresponding action (e.g. saving the reminder to disk), and strips the tag from the text before sending the remaining response to the display and TTS engine.

### Q4: How does raising the sample rate in Pydub change the pitch of the synthesized voice?
**Answer:** In digitized audio, pitch and speed are governed by sample rate. If we have a sound recorded at $16000\text{Hz}$ and override its sample rate to $22400\text{Hz}$ (a 40% increase) without changing the underlying samples, the playback hardware reads the samples 40% faster. This shortens the duration of the audio (increasing speed) and compresses the sound waves (raising the frequency/pitch), creating a high-pitched voice effect.

---

## 5. Evidence Paths
*   ASR loading and configuration: [agentic_companion.py#L129-L142](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L129-L142)
*   ASR recognize execution: [agentic_companion.py#L1797](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L1797)
*   VITS Piper engine setup: [agentic_companion.py#L144-L162](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L144-L162)
*   Winsound/Pydub speech play: [agentic_companion.py#L182-L224](file:///F:/__KUET%20Assignments/IOT/Table-Bondhu-main/agentic_companion.py#L182-L224)
