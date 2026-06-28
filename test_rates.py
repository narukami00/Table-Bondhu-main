import numpy as np
import wave
import onnx_asr

model = onnx_asr.load_model('nemo-conformer-tdt', path=r'C:\Users\Rafsan Riasat\AppData\Roaming\com.pais.handy\models\parakeet-tdt-0.6b-v2-int8', quantization='int8')

path = 'recordings_analysis/rec_20260627_093341.wav'
with wave.open(path, 'rb') as wf:
    frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float64)

print(f'Samples: {len(audio)}')

for rate in [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000]:
    target = int(len(audio) * 16000 / rate)
    src = np.arange(len(audio))
    tgt = np.linspace(0, len(audio) - 1, target)
    resampled = np.interp(tgt, src, audio)
    audio_f = (resampled.astype(np.float32) / 32768.0).astype(np.float32)
    text = model.recognize(audio_f, sample_rate=16000).strip()
    dur = len(audio) / rate
    print(f'  Rate {rate:5d} -> {dur:.1f}s -> "{text}"')
