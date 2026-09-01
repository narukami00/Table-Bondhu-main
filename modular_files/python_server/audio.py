# audio.py - Audio Synthesis & Sound Playback Engines

import os
import sys
import wave
import math
import struct
import time
import subprocess
import threading
import numpy as np
from pydub import AudioSegment

import config

# Initialize TTS Voice Engine (VITS via sherpa-onnx)
print("[*] Loading Offline VITS Text-to-Speech...")
try:
    import sherpa_onnx
    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
        model="models/vits-piper-en_US-amy-low/en_US-amy-low.onnx",
        tokens="models/vits-piper-en_US-amy-low/tokens.txt",
        data_dir="models/vits-piper-en_US-amy-low/espeak-ng-data"
    )
    model_config = sherpa_onnx.OfflineTtsModelConfig(vits=vits_config, num_threads=2, provider="cpu")
    tts_config = sherpa_onnx.OfflineTtsConfig(model=model_config, max_num_sentences=1)
    offline_tts = sherpa_onnx.OfflineTts(tts_config)
    print("[+] Offline VITS TTS loaded.")
except Exception as e:
    offline_tts = None
    print(f"[Warning] VITS TTS loading failed: {e}. Falling back to system espeak.")


def generate_default_sounds():
    """Synthesize baseline raw PCM waveforms if sound assets are missing."""
    if not os.path.exists("beep.wav"):
        with wave.open("beep.wav", "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            for i in range(1200):  # 150ms beep
                w.writeframes(struct.pack('h', int(32767.0 * math.sin(2.0 * math.pi * 2000 * i / 8000))))
                
    if not os.path.exists("alarm_sound.wav"):
        with wave.open("alarm_sound.wav", "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            for i in range(8000):  # 1 second pulsing tone
                val = int(32767.0 * math.sin(2.0 * math.pi * 1000 * i / 8000)) if (i % 1600) < 800 else 0
                w.writeframes(struct.pack('h', val))


def play_wake_up_sound():
    """Play brief acknowledgement beep on PC speakers."""
    generate_default_sounds()
    try:
        if sys.platform.startswith('win'):
            import winsound
            winsound.PlaySound("beep.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            subprocess.Popen(["pw-play", "beep.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[Audio Error] Failed to play wake up sound: {e}")


def play_alarm_sound():
    """Trigger looped alarm sound on PC speaker asynchronously."""
    stop_active_alarm()
    generate_default_sounds()
    config.loop_alarm_active = True
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            # Loop the system hand alert sound asynchronously
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
        except Exception as e:
            print(f"Failed to play Windows alarm sound: {e}")
    else:
        def alarm_loop():
            while config.loop_alarm_active:
                try:
                    proc = subprocess.Popen(["pw-play", "alarm_sound.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    config.active_audio_process = proc
                    proc.wait()
                except Exception:
                    break
                time.sleep(0.5)
        threading.Thread(target=alarm_loop, daemon=True).start()


def stop_active_alarm():
    """Silence any active alarm player on PC/Laptop."""
    config.active_alarm_active = False
    config.active_alarm_name = ""
    config.alarm_fired_at = None
    config.loop_alarm_active = False
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
            print("[Alarm] Winsound alarm purge completed.")
        except Exception as e:
            print(f"Failed to stop Winsound alarm: {e}")
    else:
        if config.active_audio_process is not None:
            try:
                config.active_audio_process.kill()
            except Exception:
                pass
            config.active_audio_process = None
        try:
            subprocess.run(["pkill", "-f", "pw-play alarm_sound.wav"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass
        print("[Alarm] Pipewire playback stopped.")


def play_speech_on_laptop(text):
    """Synthesize text to speech on laptop speakers, returning duration in seconds."""
    try:
        temp_wav = "temp_tts_playback.wav"
        success = False
        
        # 1. Try local VITS Piper Synthesis
        if offline_tts is not None:
            try:
                audio = offline_tts.generate(text)
                audio_samples = np.array(audio.samples, dtype=np.float32)
                int16_samples = (audio_samples * 32767.0).astype(np.int16)
                
                with wave.open(temp_wav, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(audio.sample_rate)
                    w.writeframes(int16_samples.tobytes())
                success = True
            except Exception as tts_err:
                print(f"[Warning] VITS synthesis failed: {tts_err}")
                
        # 2. Try Google TTS network fallback
        if not success:
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang='en')
                tts.save("temp_gtts.mp3")
                # Convert MP3 to WAV using pydub
                sound = AudioSegment.from_mp3("temp_gtts.mp3")
                sound.export(temp_wav, format="wav")
                success = True
            except Exception as gtts_err:
                print(f"[Warning] Google TTS fallback failed: {gtts_err}")

        # 3. Fallback to basic system espeak if all else fails
        if not success:
            print("[TTS] Falling back to espeak (robotic offline speech)")
            try:
                if sys.platform.startswith('win'):
                    # On Windows, use built-in SAPI speech engine
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    threading.Thread(target=lambda: speaker.Speak(text), daemon=True).start()
                else:
                    subprocess.run(["espeak", "-v", "en", "-s", "150", "-p", "75", text],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as esp_err:
                print(f"Espeak execution failed: {esp_err}")
            
            espeak_dur = max(2.0, len(text.split()) / 2.5)
            return espeak_dur
            
        # Play synthesized WAV file
        duration_sec = max(2.0, len(text.split()) / 2.5)
        try:
            if sys.platform.startswith('win'):
                import winsound
                winsound.PlaySound(temp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                subprocess.Popen(["pw-play", temp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as play_err:
            print(f"Failed to play synthesized WAV: {play_err}")
            
        return duration_sec
        
    except Exception as e:
        print(f"[TTS Error] Playback pipeline crashed: {e}")
        return None


def speak_on_esp32(conn, text, header=None):
    """Sync text display with speech audio playback on PC/Laptop speaker."""
    duration_sec = play_speech_on_laptop(text)
    if duration_sec is None:
        duration_sec = max(5.0, len(text) * 0.1)
    try:
        with config.send_lock:
            if header:
                conn.sendall(header)
            conn.sendall(f"DURATION:{duration_sec:.1f}\n".encode())
        return True
    except Exception as e:
        print(f"[TTS Sync Error] Failed to write duration sync: {e}")
        return False
