import os
import wave
import numpy as np
import onnx_asr

print("Loading Parakeet...")
asr = onnx_asr.load_model(
    "nemo-conformer-tdt",
    path=r"C:\Users\Rafsan Riasat\AppData\Roaming\com.pais.handy\models\parakeet-tdt-0.6b-v2-int8",
    quantization="int8",
)
print("Model loaded.\n")

recordings_dir = os.path.join(os.path.dirname(__file__), "recordings_analysis")
files = sorted(f for f in os.listdir(recordings_dir) if f.endswith(".wav"))

for f in files:
    path = os.path.join(recordings_dir, f)
    with wave.open(path, "r") as wf:
        rate = wf.getframerate()
        frames = wf.getnframes()
        duration = frames / rate
        raw = wf.readframes(frames)

    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    if duration < 0.1:
        print(f"{f} ({duration:.1f}s): [empty]")
        continue

    # Try the declared rate
    try:
        text = asr.recognize(audio_np, sample_rate=rate).strip()
    except Exception:
        text = ""

    # Also try 22050 if declared rate differs
    if rate != 22050:
        try:
            text22 = asr.recognize(audio_np, sample_rate=22050).strip()
        except Exception:
            text22 = ""
    else:
        text22 = text

    print(f"{f} ({rate}Hz, {duration:.1f}s)")
    print(f"  Declared rate: \"{text}\"")
    if text22 != text:
        print(f"  @22050Hz:      \"{text22}\"")
    print()
