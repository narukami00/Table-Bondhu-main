"""
Agentic Companion Server
Hands-free voice activation, VAD silence detection, reminders & alarms with laptop audio playback
"""
import socket
import numpy as np
import onnx_asr
import threading
import time
import wave
import os
import re
import json
import io
import urllib.request
import datetime
from gtts import gTTS
from pydub import AudioSegment
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080

# Configure the LLM (LM Studio Local Endpoint)
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-coder-1.5b-instruct"
REMINDERS_FILE = "reminders.json"
RECORDINGS_DIR = "recordings_analysis"
COMMAND_TRIGGERS = ["reminder", "reminders", "hi", "hello", "hey", "yo"]
QUESTION_WORDS = ["what", "how", "why", "can you", "is", "do", "where",
                   "when", "who", "which", "could", "would", "should",
                   "tell me", "explain"]
KEYWORD_CHUNK_SECONDS = 2.5
KEYWORD_DEBOUNCE_SECONDS = 5

if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

# State variables
active_conn = None
active_handler = None
active_alarm_active = False
active_alarm_name = ""
alarm_fired_at = None
scheduled_sleep_time = None
scheduled_sleep_checked_today = False
send_lock = threading.Lock()  # Prevents interleaved sends from multiple threads
chat_lock = threading.Lock()  # Protects chat_session across threads

# --- LLM SYSTEM INSTRUCTION FOR AGENTIC COMMANDS ---
SYSTEM_INSTRUCTION = """You are a helpful and cute desk assistant built into a tiny microcontroller. 
Your answers are displayed on a 160x128 pixel screen. 
You MUST be extremely concise. Keep every answer under 15 words. 
Do not use markdown formatting. You MUST NOT use any emojis or emoticons in your responses.

You have the ability to manage reminders, alarms, and sleep tracking.
- If the user says they are going to sleep, taking a nap, or tell you to enter sleep/nap mode, append: [CMD:START_SLEEP]
  Example: "I am taking a nap" -> "Goodnight! Sweet dreams. [CMD:START_SLEEP]"
  Example: "Going to sleep now" -> "Goodnight! Sleep well. [CMD:START_SLEEP]"
- EXPLICIT TIME (absolute): [CMD:ADD_REMINDER|task|ABS|time]
  Examples: "remind me at 3pm" → "Added. [CMD:ADD_REMINDER|Reminder|ABS|3:00 PM]"
  "remind me to study database at 9pm" → "Added. [CMD:ADD_REMINDER|study database|ABS|9:00 PM]"
  "set alarm for 8:30 AM" → "Added. [CMD:ADD_REMINDER|Alarm|ABS|8:30 AM]"
  "remind me tomorrow to attend meeting at 9am" → "Added. [CMD:ADD_REMINDER|attend meeting|ABS|tomorrow 9:00 AM]"
  Use 12-hour format with AM/PM, or 24-hour like "15:00".
- RELATIVE TIME: [CMD:ADD_REMINDER|task|REL|Ns/Nm/Nh]
  "remind me to study database in 30 seconds" → "Added. [CMD:ADD_REMINDER|study database|REL|30s]"
  "set a reminder to buy milk for 2 hours" → "Added. [CMD:ADD_REMINDER|buy milk|REL|2h]"
  "alarm in 5 minutes" → "Added. [CMD:ADD_REMINDER|Alarm|REL|5m]"
  Use s=seconds, m=minutes, h=hours.
- If the user says "remind me" or "set a reminder" but doesn't specify a task, use "Reminder" as the task.
- To LIST reminders: [CMD:LIST_REMINDERS]
- To CLEAR all: [CMD:CLEAR_REMINDERS]
- To DELETE a specific reminder by its 1-based index from the active list: [CMD:DELETE_REMINDER|index]
  Examples: "delete the second reminder" (from active list context) → "Deleted. [CMD:DELETE_REMINDER|2]"
  "remove reminder number 1" → "Removed. [CMD:DELETE_REMINDER|1]"

Do not explain the command tags to the user, just include them at the end of your response."""

class LocalChatSession:
    def __init__(self, system_instruction):
        self.system_instruction = system_instruction
        self.history = []

    def send_message(self, user_text):
        with chat_lock:
            self.history.append({"role": "user", "content": user_text})
            messages = []
            if self.system_instruction:
                # Inject current date, time, and active reminders/tasks dynamically
                now = datetime.datetime.now()
                time_ctx = now.strftime("%A, %d %B %Y %I:%M %p")
                
                active_rems = get_reminders_list()
                rem_list_str = ""
                if active_rems:
                    for i, r in enumerate(active_rems, 1):
                        rem_list_str += f"{i}. {r.get('task')} (scheduled for {r.get('display_time')})\n"
                else:
                    rem_list_str = "No active reminders/tasks."
                
                sys_prompt = (
                    f"{self.system_instruction}\n\n"
                    f"[CONTEXT]\n"
                    f"- Current time/date: {time_ctx}\n"
                    f"- Active reminders list:\n{rem_list_str}\n"
                    f"Use this context to accurately answer queries about time, date, or reminders, and map deletion indexes correctly."
                )
                messages.append({"role": "system", "content": sys_prompt})
            messages.extend(self.history)
            
            data = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.7
            }
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(data).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                res = json.loads(response.read().decode("utf-8"))
                ai_answer = res["choices"][0]["message"]["content"]
                
            self.history.append({"role": "assistant", "content": ai_answer})
        
        class ResponseObject:
            def __init__(self, text):
                self.text = text
        return ResponseObject(ai_answer)

print("Loading Parakeet Model (tdt-0.6b)...")
asr_model = onnx_asr.load_model(
    'nemo-conformer-tdt',
    path=r'C:\Users\Rafsan Riasat\AppData\Roaming\com.pais.handy\models\parakeet-tdt-0.6b-v2-int8',
    quantization='int8'
)

# GTCRN Speech Denoiser is disabled because tiny neural enhancement models
# introduce processing artifacts (spectral masking/phase distortion) on the
# ESP32's raw 12-bit ADC audio, which degrades local ASR transcription accuracy.
speech_denoiser = None

print("Loading Offline VITS Text-to-Speech...")
try:
    import sherpa_onnx
    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
        model="models/vits-piper-en_US-amy-low/en_US-amy-low.onnx",
        tokens="models/vits-piper-en_US-amy-low/tokens.txt",
        data_dir="models/vits-piper-en_US-amy-low/espeak-ng-data"
    )
    model_config = sherpa_onnx.OfflineTtsModelConfig(
        vits=vits_config,
        num_threads=1,
        provider="cpu"
    )
    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=model_config,
        max_num_sentences=1
    )
    offline_tts = sherpa_onnx.OfflineTts(tts_config)
    print("[*] Offline VITS Text-to-Speech loaded successfully.")
except Exception as e:
    offline_tts = None
    print(f"[Warning] Failed to load Offline VITS Text-to-Speech: {e}")

print("Initializing Local LLM Session...")
chat_session = LocalChatSession(system_instruction=SYSTEM_INSTRUCTION)
print("Systems Online! Ready to listen.")

# --- LAPTOP AUDIO HELPERS ---
import sys
import subprocess
import math
import struct

active_audio_process = None
loop_alarm_active = False

def generate_default_sounds():
    """Dynamically generate generic alert WAV files if not present (useful for headless Linux/Raspberry Pi)"""
    import os
    if not os.path.exists("beep.wav"):
        try:
            sample_rate = 8000
            with wave.open("beep.wav", "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                # 150ms of 2000Hz tone
                for i in range(int(sample_rate * 0.15)):
                    val = int(32767.0 * math.sin(2.0 * math.pi * 2000 * i / sample_rate))
                    w.writeframes(struct.pack('h', val))
        except Exception as e:
            print(f"Failed to generate beep.wav: {e}")

    if not os.path.exists("alarm_sound.wav"):
        try:
            sample_rate = 8000
            with wave.open("alarm_sound.wav", "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                # 1 second of pulsing 1000Hz tone (beep-beep)
                for i in range(int(sample_rate * 1.0)):
                    if (i % 1600) < 800:
                        val = int(32767.0 * math.sin(2.0 * math.pi * 1000 * i / sample_rate))
                    else:
                        val = 0
                    w.writeframes(struct.pack('h', val))
        except Exception as e:
            print(f"Failed to generate alarm_sound.wav: {e}")

def play_wake_up_sound():
    if sys.platform.startswith('win'):
        try:
            import winsound
            # Short high pitch beep to signal wakeup
            winsound.Beep(2000, 150)
            winsound.Beep(2500, 150)
        except Exception as e:
            print(f"Failed to play wake up sound: {e}")
    else:
        generate_default_sounds()
        try:
            subprocess.Popen(["aplay", "beep.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Audio Error] Failed to play wake up sound via aplay: {e}")

def play_alarm_sound():
    global active_audio_process, loop_alarm_active
    stop_active_alarm()
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            # Loop the system hand sound asynchronously
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
        except Exception as e:
            print(f"Failed to play alarm sound: {e}")
    else:
        generate_default_sounds()
        loop_alarm_active = True
        def alarm_loop():
            global active_audio_process
            while loop_alarm_active:
                try:
                    active_audio_process = subprocess.Popen(["aplay", "alarm_sound.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    active_audio_process.wait()
                except Exception:
                    break
                time.sleep(0.5)
        threading.Thread(target=alarm_loop, daemon=True).start()

def stop_active_alarm():
    global active_alarm_active, active_alarm_name, alarm_fired_at, active_audio_process, loop_alarm_active
    active_alarm_active = False
    active_alarm_name = ""
    alarm_fired_at = None
    loop_alarm_active = False
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
            print("[Alarm] Buzzing stopped.")
        except Exception as e:
            print(f"Failed to stop alarm sound: {e}")
    else:
        if active_audio_process is not None:
            try:
                active_audio_process.terminate()
            except Exception:
                pass
            active_audio_process = None
            print("[Alarm] Buzzing stopped.")

# --- TTS (Text-to-Speech) via Google TTS ---
def play_speech_on_laptop(text):
    """Play the synthesized speech on the laptop speakers using winsound, modulated to sound like Pikachu"""
    try:
        import winsound
        sound = None
        
        # Try offline VITS generation first
        if offline_tts is not None:
            try:
                # Generate offline raw audio
                audio = offline_tts.generate(text)
                # Convert float32 array to 16-bit PCM bytes
                audio_samples = np.array(audio.samples, dtype=np.float32)
                int16_samples = (audio_samples * 32767.0).astype(np.int16)
                raw_bytes = int16_samples.tobytes()
                
                sound = AudioSegment(
                    data=raw_bytes,
                    sample_width=2,
                    frame_rate=audio.sample_rate,
                    channels=1
                )
            except Exception as tts_err:
                print(f"[Warning] Offline VITS generation failed, falling back to Google TTS: {tts_err}")
        
        # Fallback to Google TTS (requires internet) if offline TTS failed or is uninitialized
        if sound is None:
            try:
                tts = gTTS(text=text, lang='en', slow=False)
                mp3_buf = io.BytesIO()
                tts.write_to_fp(mp3_buf)
                mp3_buf.seek(0)
                sound = AudioSegment.from_mp3(mp3_buf)
            except Exception as gtts_err:
                print(f"[Warning] Google TTS conversion failed: {gtts_err}")
        
        # If still None (e.g., missing ffmpeg/dependencies on Windows), fall back to native Windows SAPI5
        if sound is None:
            if sys.platform.startswith('win'):
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Rate = 2  # slightly faster to sound cute
                    speaker.Speak(text, 1) # SVSFlagsAsync = 1
                    words = len(text.split())
                    duration_sec = max(2.0, words / 2.5)
                    print(f"[SAPI5 TTS] Speaking natively: '{text}' ({duration_sec:.1f}s)")
                    return duration_sec
                except Exception as sapi_err:
                    print(f"[SAPI5 TTS Error] {sapi_err}")
        
        # --- PIKACHU VOICE EFFECT (PITCH & SPEED SHIFT) ---
        # Speed up and pitch up by 40% (creates a cute, high-pitched tone)
        new_sample_rate = int(sound.frame_rate * 1.40)
        pitched_sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
        # Resample to standard 44.1kHz rate so the audio interface plays it back correctly
        pitched_sound = pitched_sound.set_frame_rate(44100)
        
        # Calculate new duration (before adding silence so avatar mouth stops exactly when speech ends)
        duration_sec = len(pitched_sound.raw_data) / (pitched_sound.frame_rate * pitched_sound.channels * pitched_sound.sample_width)
        
        # Add 1 second of silence to prevent abrupt winsound truncation at the tail
        silence = AudioSegment.silent(duration=1000, frame_rate=44100)
        if pitched_sound.channels != silence.channels:
            silence = silence.set_channels(pitched_sound.channels)
        pitched_sound = pitched_sound + silence
        
        temp_wav = "temp_tts_playback.wav"
        pitched_sound.export(temp_wav, format="wav")
        
        # Play asynchronously (cross-platform)
        print(f"[TTS Pikachu] Playing asynchronously: '{text}' ({duration_sec:.1f}s)")
        if sys.platform.startswith('win'):
            import winsound
            winsound.PlaySound(temp_wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            try:
                subprocess.Popen(["aplay", temp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[Audio Error] Failed to play speech via aplay: {e}")
        return duration_sec
    except Exception as e:
        print(f"[TTS Pikachu Error] {e}")
        return None

def speak_on_esp32(conn, text, header=None):
    """Generate TTS and play on laptop while sending duration sync back to the ESP32.
    header: optional bytes to send atomically before DURATION (e.g. UI_MSG).
    """
    duration_sec = play_speech_on_laptop(text)
    if duration_sec is None:
        # Fallback to duration estimate based on text length
        duration_sec = max(5.0, len(text) * 0.1)
    
    try:
        with send_lock:
            if header:
                conn.sendall(header)
            conn.sendall(f"DURATION:{duration_sec:.1f}\n".encode())
        print(f"[TTS Laptop] Sent sync instructions (duration: {duration_sec:.1f}s) to ESP32")
        return True
    except Exception as e:
        print(f"[TTS Laptop Error] Failed to send sync: {e}")
        return False

# --- REMINDERS & SCHEDULER STORE ---
db_lock = threading.Lock()

def parse_relative_time(rel_str):
    """Parse relative time like '30s', '5m', '2h' into (trigger_datetime, display_str)"""
    rel_str = rel_str.strip().lower()
    match = re.match(r'^(\d+)\s*(s|sec|second|m|min|minute|h|hr|hour)s?$', rel_str)
    if not match:
        return None, None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in ('s', 'sec', 'second'):
        delta = datetime.timedelta(seconds=amount)
        display = f"in {amount} second{'s' if amount != 1 else ''}"
    elif unit in ('m', 'min', 'minute'):
        delta = datetime.timedelta(minutes=amount)
        display = f"in {amount} minute{'s' if amount != 1 else ''}"
    elif unit in ('h', 'hr', 'hour'):
        delta = datetime.timedelta(hours=amount)
        display = f"in {amount} hour{'s' if amount != 1 else ''}"
    else:
        return None, None
    trigger_dt = datetime.datetime.now() + delta
    return trigger_dt, display

def parse_absolute_time(abs_str):
    """Parse absolute time like '15:00', '3:00 PM', '2026-06-28 09:00' into (trigger_datetime, display_str)"""
    abs_str = abs_str.strip()
    now = datetime.datetime.now()
    
    # Try HH:MM AM/PM format (e.g., "3:00 PM", "8:30 am")
    match = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$', abs_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3).upper()
        if ampm == 'PM' and hour != 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        display = target.strftime("%I:%M %p").lstrip("0")
        return target, display
    
    # Try HH:MM format (24h, e.g., "15:00", "8:30")
    match = re.match(r'^(\d{1,2}):(\d{2})$', abs_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
            display = target.strftime("%I:%M %p").lstrip("0") + " (tomorrow)"
        else:
            display = target.strftime("%I:%M %p").lstrip("0")
        return target, display
    
    # Try YYYY-MM-DD HH:MM format (e.g., "2026-06-28 09:00")
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})$', abs_str)
    if match:
        dt = datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                               int(match.group(4)), int(match.group(5)))
        display = dt.strftime("%b %d %I:%M %p").lstrip("0")
        return dt, display
    
    # Try MM-DD HH:MM format (same year, e.g., "06-28 09:00")
    match = re.match(r'^(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})$', abs_str)
    if match:
        dt = datetime.datetime(now.year, int(match.group(1)), int(match.group(2)),
                               int(match.group(3)), int(match.group(4)))
        if dt <= now:
            dt = dt.replace(year=now.year + 1)
        display = dt.strftime("%b %d %I:%M %p").lstrip("0")
        return dt, display
    
    return None, None

def _load_reminders_internal():
    """Load reminders WITHOUT db_lock — caller must already hold it."""
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, 'r') as f:
            reminders = json.load(f)
        # Migrate old format: {time: "HH:MM"} → {trigger_time: ISO, display_time: str}
        migrated = False
        for r in reminders:
            if "trigger_time" not in r and "time" in r:
                time_str = r["time"]
                match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
                if match:
                    now = datetime.datetime.now()
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target <= now:
                        target += datetime.timedelta(days=1)
                    r["trigger_time"] = target.isoformat()
                    r["display_time"] = time_str
                    migrated = True
                else:
                    r["trigger_time"] = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()
                    r["display_time"] = time_str
                    migrated = True
                del r["time"]
        if migrated:
            with open(REMINDERS_FILE, 'w') as f:
                json.dump(reminders, f, indent=2)
        return reminders
    except Exception:
        return []

def _save_reminders_internal(reminders):
    """Save reminders WITHOUT db_lock — caller must already hold it."""
    try:
        with open(REMINDERS_FILE, 'w') as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        print(f"Failed to save reminders: {e}")

def load_reminders():
    with db_lock:
        return _load_reminders_internal()

def save_reminders(reminders):
    with db_lock:
        _save_reminders_internal(reminders)

def add_reminder(task, trigger_dt, display_str):
    """Add a reminder with full datetime trigger (atomic load-modify-save)"""
    with db_lock:
        reminders = _load_reminders_internal()
        reminders.append({
            "task": task,
            "trigger_time": trigger_dt.isoformat(),
            "display_time": display_str,
            "fired": False,
            "created": datetime.datetime.now().isoformat()
        })
        _save_reminders_internal(reminders)

def get_reminders_list():
    with db_lock:
        reminders = _load_reminders_internal()
    return [r for r in reminders if not r.get("fired", False)]

def clear_reminders():
    with db_lock:
        _save_reminders_internal([])

def delete_reminder_by_index(index):
    with db_lock:
        reminders = _load_reminders_internal()
        active_reminders = [r for r in reminders if not r.get("fired", False)]
        if 1 <= index <= len(active_reminders):
            target = active_reminders[index - 1]
            target["fired"] = True
            _save_reminders_internal(reminders)
            return target.get("task", "Reminder")
        return None

def get_weather():
    try:
        # Lat/Lon for Khulna, Bangladesh (KUET coordinates)
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.8956&longitude=89.5011&current_weather=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            current = data.get("current_weather", {})
            temp = round(current.get("temperature", 25))
            code = current.get("weathercode", 0)
            if code == 0:
                desc, icon_idx = "SUNNY", 0
            elif code in [1, 2, 3, 45, 48]:
                desc, icon_idx = "CLOUDY", 1
            elif code in [71, 72, 73, 75, 77, 85, 86]:
                desc, icon_idx = "SNOWY", 3
            else:
                desc, icon_idx = "RAINY", 2
            return temp, desc, icon_idx
    except Exception as e:
        print(f"[Weather Error] {e}")
        return None, None, None

def fetch_and_send_weather(conn):
    temp, desc, icon_idx = get_weather()
    if temp is not None:
        try:
            with send_lock:
                conn.sendall(f"WEATHER:{temp}:{desc}:{icon_idx}\n".encode())
            print(f"[Weather] Sent conditions to client: {temp}C, {desc}")
        except Exception as e:
            print(f"[Weather] Failed to send weather: {e}")

def parse_timer_duration(text):
    matches = re.findall(r'(\d+)\s*(second|sec|minute|min|hour|hr|s|m|h)s?', text.lower())
    if not matches:
        return None
    total_seconds = 0
    for val_str, unit in matches:
        val = int(val_str)
        if unit.startswith('s'):
            total_seconds += val
        elif unit.startswith('m'):
            total_seconds += val * 60
        elif unit.startswith('h') or unit.startswith('hr'):
            total_seconds += val * 3600
    return total_seconds if total_seconds > 0 else None

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m} minutes and {s} seconds" if s > 0 else f"{m} minutes"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h} hours and {m} minutes" if m > 0 else f"{h} hours"

def alarm_scheduler():
    global active_alarm_active, active_alarm_name, active_conn, alarm_fired_at, scheduled_sleep_time, scheduled_sleep_checked_today, active_handler
    print("[*] Alarm scheduler active.")
    pending_alarms = []    # Alarms to send after releasing db_lock
    
    while True:
        try:
            now = datetime.datetime.now()
            
            # Auto-dismiss alarm after 30 seconds if user doesn't respond
            if active_alarm_active and alarm_fired_at is not None:
                elapsed = (now - alarm_fired_at).total_seconds()
                if elapsed > 30:
                    print(f"[ALARM] Auto-dismissed after {int(elapsed)}s")
                    stop_active_alarm()
                    alarm_fired_at = None
                    if active_conn:
                        try:
                            with send_lock:
                                active_conn.sendall(b"UI_STATE:IDLE\n")
                        except Exception:
                            pass
            
            # --- SCHEDULED SLEEP CHECKER ---

            if scheduled_sleep_time:
                now_hm = now.strftime("%H:%M")
                if now_hm == scheduled_sleep_time:
                    if not scheduled_sleep_checked_today:
                        scheduled_sleep_checked_today = True
                        print(f"[Sleep Schedule] Target time {scheduled_sleep_time} reached! Checking room status...")
                        
                        if active_handler:
                            last_ldr = getattr(active_handler, 'last_ldr_val', 500)
                            last_motion = getattr(active_handler, 'last_motion_time', time.time())
                            time_since_motion = time.time() - last_motion
                            
                            print(f"[Sleep Schedule] Current LDR: {last_ldr} | Time since motion: {time_since_motion:.1f}s")
                            
                            # Dark room (< 200 LDR) and idle for >= 5 minutes (300s)
                            if last_ldr < 200 and time_since_motion >= 300:
                                print("[Sleep Schedule] Conditions MET. Triggering sleep automatically!")
                                active_handler.sleep_start_time = time.time()
                                active_handler.sleep_movement_count = 0
                                active_handler.sleep_noise_levels = []
                                active_handler.sleep_noise_events = 0
                                active_handler.sleep_ldr_levels = [last_ldr]
                                active_handler.last_pir_state = 'SLEEPING'
                                try:
                                    active_conn.sendall(b"CMD:START_SLEEP\n")
                                except Exception:
                                    pass
                            else:
                                print("[Sleep Schedule] Conditions NOT met (room bright or motion detected). Waiting for actual sleep start later...")
                else:
                    scheduled_sleep_checked_today = False

            # Atomic load-check-save under db_lock
            pending_alarms = []
            with db_lock:
                reminders = _load_reminders_internal()
                updated = False
                
                for r in reminders:
                    if r.get("fired", False):
                        continue
                    trigger_str = r.get("trigger_time", "")
                    if not trigger_str:
                        continue
                    try:
                        trigger_dt = datetime.datetime.fromisoformat(trigger_str)
                    except ValueError:
                        continue
                    if now >= trigger_dt:
                        r["fired"] = True
                        updated = True
                        active_alarm_active = True
                        active_alarm_name = r.get("task", "Alarm")
                        alarm_fired_at = now
                        pending_alarms.append(r.get("display_time", trigger_str))
                        
                if updated:
                    _save_reminders_internal(reminders)
            
            # Send alarm commands outside db_lock
            for display in pending_alarms:
                print(f"\n[ALARM] Triggered! Task: {active_alarm_name} (was set for {display})")
                play_alarm_sound()
                if active_conn:
                    try:
                        with send_lock:
                            active_conn.sendall(f"UI_ALARM:{active_alarm_name}\n".encode())
                    except Exception as e:
                        print(f"Failed to send alarm command to client: {e}")
                
        except Exception as e:
            print(f"[Scheduler Error] {e}")
            
        time.sleep(5)

def log_sleep_event(event_name):
    """Helper to log sleep and wake transitions to sleep_sessions.log for future sleep monitoring analysis."""
    try:
        log_path = os.path.join(RECORDINGS_DIR, "sleep_sessions.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts}\t{event_name}\n")
    except Exception as e:
        print(f"[Error] Failed to write to sleep_sessions.log: {e}")

# --- CLIENT SOCKET HANDLER ---
class VoiceAgentHandler:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.is_awake = False
        self.speech_buffer = bytearray()
        self.noise_floor = 300
        self.rms_threshold = 450
        self.recording_start_time = 0
        self.speech_ready_time = 0
        self.audio_bytes_received = 0
        self.first_audio_time = 0
        # Keyword detection state
        self.keyword_buffer = bytearray()
        self.keyword_chunk_start = time.time()
        self.last_keyword_trigger = 0
        # TCP framing buffer — accumulates partial recv() data across calls
        self.recv_buffer = bytearray()
        # Socket write lock — prevents interleaved sendall from two threads
        self.send_lock = threading.Lock()
        # Enable TCP_NODELAY to avoid Nagle delays on small state commands
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.timer_running = False
        self.last_pir_state = 'AWAKE' # Track client sleep states (AWAKE, SLEEPING, PREWAKE)
        self.last_ldr_val = 500
        self.last_motion_time = time.time()
        # Sleep monitoring session variables
        self.sleep_start_time = None
        self.sleep_movement_count = 0
        self.sleep_noise_levels = []
        self.sleep_noise_events = 0
        
    def calibrate(self):
        print(f"[*] Calibrating noise baseline for {self.addr}...")
        
        # Clear any TCP backlog on initial connection
        self.conn.setblocking(False)
        try:
            while True:
                if not self.conn.recv(16384):
                    break
        except (BlockingIOError, Exception):
            pass
        finally:
            self.conn.setblocking(True)
        
        calibration_rms = []
        start_time = time.time()
        while time.time() - start_time < 1.0:
            try:
                data = self.conn.recv(4096)
                if not data:
                    break
                data_np = np.frombuffer(data, dtype=np.int16)
                if len(data_np) > 0:
                    rms = np.sqrt(np.mean(data_np.astype(np.float64)**2))
                    calibration_rms.append(rms)
            except Exception:
                break
            
        if calibration_rms:
            self.noise_floor = np.mean(calibration_rms)
            self.rms_threshold = max(self.noise_floor * 1.55, 450)
            print(f"[*] Calibration complete. Noise Floor: {self.noise_floor:.1f}")
        else:
            print("[!] Calibration failed. Using defaults.")

    def safe_send(self, data):
        """Thread-safe sendall using global lock."""
        with send_lock:
            self.conn.sendall(data)

    def weather_updater(self):
        while True:
            time.sleep(1800)
            if active_conn == self.conn:
                fetch_and_send_weather(self.conn)
            else:
                break

    def keyword_detection_loop(self):
        while True:
            time.sleep(0.5)
            # Skip if user is in button-press mode
            if self.is_awake:
                continue
            # Skip if not enough time has passed for a chunk
            elapsed = time.time() - self.keyword_chunk_start
            if elapsed < KEYWORD_CHUNK_SECONDS:
                continue
            # Skip if buffer is too small (empty audio)
            if len(self.keyword_buffer) < 800:
                self.keyword_buffer = bytearray()
                self.keyword_chunk_start = time.time()
                continue

            # Grab and clear buffer
            chunk = bytes(self.keyword_buffer)
            self.keyword_buffer = bytearray()
            self.keyword_chunk_start = time.time()

            # Calculate rate from chunk size (2.5s window)
            num_samples = len(chunk) / 2
            measured_rate = int(num_samples / KEYWORD_CHUNK_SECONDS) if KEYWORD_CHUNK_SECONDS > 0 else 0
            if measured_rate < 1000:
                continue

            # Resample to 16kHz
            try:
                audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float64)
                if measured_rate != 16000 and len(audio_np) > 0:
                    target_count = int(len(audio_np) * 16000 / measured_rate)
                    src_idx = np.arange(len(audio_np))
                    tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
                    audio_np = np.interp(tgt_idx, src_idx, audio_np)
                audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
            except Exception:
                continue

            # Transcribe
            try:
                text = asr_model.recognize(audio_float, sample_rate=16000).strip()
            except Exception:
                continue
            if not text:
                continue

            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            print(f"[KEYWORD] Heard: '{text}'")

            # Debounce check
            if time.time() - self.last_keyword_trigger < KEYWORD_DEBOUNCE_SECONDS:
                continue

            # === TIMER ACTIVE MODE ===
            # When timer is running, ONLY process timer-related commands (cancel/stop, pause, resume)
            # All other features are blocked to prevent interference
            if self.timer_running:
                # 1. Check Cancel/Stop Intent
                is_cancel = any(w in clean_text for w in ["cancel", "delete", "remove", "dismiss"]) or \
                            (any(w in clean_text for w in ["stop", "quit", "terminate", "shut up", "stop it"]) and "timer" in clean_text)
                
                # 2. Check Pause Intent
                is_pause = any(w in clean_text for w in ["pause", "hold"])
                
                # 3. Check Resume Intent
                is_resume = any(w in clean_text for w in ["resume", "continue", "start", "play"])
                
                if is_cancel:
                    self.last_keyword_trigger = time.time()
                    self.timer_running = False
                    try:
                        self.safe_send(b"TIMER_CANCEL\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer stopped.")
                elif is_pause:
                    self.last_keyword_trigger = time.time()
                    try:
                        self.safe_send(b"TIMER_PAUSE\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer paused.")
                elif is_resume:
                    self.last_keyword_trigger = time.time()
                    try:
                        self.safe_send(b"TIMER_RESUME\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer resumed.")
                continue  # Skip all other features while timer is running

            # === NORMAL MODE (no timer active) ===

            # Feature 1: Reminder List check
            has_target_word = any(w in clean_text for w in ["reminder", "reminders", "alarm", "alarms", "task", "tasks"])
            is_creation_intent = any(w in clean_text for w in ["set", "add", "create", "remind me", "remind me to"])
            is_delete_intent = any(w in clean_text for w in ["delete", "remove", "clear", "cancel"])
            
            if has_target_word and not is_creation_intent and not is_delete_intent:
                self.last_keyword_trigger = time.time()
                self.send_reminder_list()
                continue

            # Feature 2: Reminder Deletion check
            is_delete_query = any(w in clean_text for w in ["delete", "remove", "clear", "cancel"]) and \
                              any(w in clean_text for w in ["reminder", "alarm", "task", "all", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "first", "second", "third", "fourth", "fifth"])
            
            if is_delete_query:
                self.last_keyword_trigger = time.time()
                if "all" in clean_text or "every" in clean_text:
                    clear_reminders()
                    self.safe_send(b"UI_MSG:Cleared all.\n")
                    play_speech_on_laptop("Cleared all reminders.")
                else:
                    idx = self.extract_index(clean_text)
                    if idx is not None:
                        deleted_task = delete_reminder_by_index(idx)
                        if deleted_task:
                            msg = f"Deleted number {idx}: {deleted_task}."
                            self.safe_send(f"UI_MSG:Deleted #{idx}\n".encode())
                            play_speech_on_laptop(msg)
                            # Send updated list after a short delay
                            threading.Timer(1.5, self.send_reminder_list).start()
                        else:
                            self.safe_send(b"UI_MSG:Not found.\n")
                            play_speech_on_laptop(f"Could not find reminder number {idx}.")
                    else:
                        self.safe_send(b"UI_MSG:Specify index.\n")
                        play_speech_on_laptop("Which reminder number would you like to delete?")
                continue

            # Feature 3: Hi greeting
            if any(clean_text == w or clean_text.startswith(w + " ") for w in ["hi", "hello", "hey", "yo"]):
                self.last_keyword_trigger = time.time()
                self.play_greeting()
                continue

            # Feature 4: Timer start check (only when no timer is running)
            is_timer_query = any(w in clean_text for w in ["timer", "countdown", "focus"])
            if is_timer_query:
                self.last_keyword_trigger = time.time()
                if any(w in clean_text for w in ["cancel", "stop", "quit", "terminate", "shut up", "stop it"]):
                    play_speech_on_laptop("No timer is currently running.")
                else:
                    duration = parse_timer_duration(clean_text)
                    if duration is not None:
                        self.timer_running = True
                        try:
                            self.safe_send(f"TIMER_START:{duration}\n".encode())
                        except Exception:
                            pass
                        play_speech_on_laptop(f"Starting countdown for {format_duration(duration)}.")
                    else:
                        play_speech_on_laptop("Please specify seconds, minutes, or hours.")
                continue

    def extract_index(self, text):
        number_map = {
            "first": 1, "one": 1, "1st": 1, "1": 1,
            "second": 2, "two": 2, "2nd": 2, "2": 2,
            "third": 3, "three": 3, "3rd": 3, "3": 3,
            "fourth": 4, "four": 4, "4th": 4, "4": 4,
            "fifth": 5, "five": 5, "5th": 5, "5": 5,
            "sixth": 6, "six": 6, "6th": 6, "6": 6,
            "seventh": 7, "seven": 7, "7th": 7, "7": 7,
            "eighth": 8, "eight": 8, "8th": 8, "8": 8,
            "ninth": 9, "nine": 9, "9th": 9, "9": 9,
            "tenth": 10, "ten": 10, "10th": 10, "10": 10
        }
        words = text.split()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word).lower()
            if clean_word in number_map:
                return number_map[clean_word]
        match = re.search(r'\b\d+\b', text)
        if match:
            return int(match.group(0))
        return None

    def send_reminder_list(self):
        reminders = get_reminders_list()
        try:
            if reminders:
                formatted_items = []
                for idx, r in enumerate(reminders, 1):
                    task = r['task']
                    time_str = r.get('display_time', '?')
                    # Format default Alarm vs task with description
                    if task.lower() in ["reminder", "alarm"]:
                        formatted_items.append(f"{idx}. {task} @ {time_str}")
                    else:
                        formatted_items.append(f"{idx}. {task} @ {time_str}")
                items_str = "|".join(formatted_items)
                self.safe_send(f"UI_LIST:{items_str}\n".encode())
            else:
                self.safe_send(b"UI_MSG:No active reminders.\n")
            print(f"[*] Keyword: reminders displayed")
        except Exception as e:
            print(f"[Error] send_reminder_list: {e}")

    def play_greeting(self):
        try:
            self.safe_send(b"UI_STATE:GREETING\n")
            print(f"[*] Keyword: greeting triggered")
        except Exception as e:
            print(f"[Error] play_greeting: {e}")

    def is_question(self, text):
        if text.endswith("?"):
            return True
        for word in QUESTION_WORDS:
            if text == word or text.startswith(word + " "):
                return True
        return False

    def handle_single_question(self, text):
        try:
            print(f"[*] Single question: '{text}'")
            self.safe_send(b"UI_STATE:THINKING\n")
            response = chat_session.send_message(text)  # send_message acquires chat_lock internally
            ai_answer = response.text.strip()
            print(f"[*] AI Response: {ai_answer}")
            self.handle_llm_response(ai_answer)
        except Exception as e:
            print(f"[Error] Single question failed: {e}")
            try:
                self.safe_send(b"UI_MSG:Error.\n")
            except Exception:
                pass
            
    def _extract_command(self, buf, marker):
        """Find a text command (e.g. CMD:WOKE\\n) embedded in binary audio stream.
        Returns (before_bytes, command_str, after_bytes) or None if not found."""
        pos = buf.find(marker)
        if pos < 0:
            return None
        # Find the newline that terminates this command
        nl_pos = buf.find(b"\n", pos)
        if nl_pos < 0:
            return None  # incomplete command, wait for more data
        before = buf[:pos]
        cmd = buf[pos:nl_pos]  # exclude the \n itself
        after = buf[nl_pos+1:]
        return (before, cmd, after)

    def run(self):
        global active_conn, active_handler
        active_conn = self.conn
        active_handler = self
        
        self.calibrate()
        # Start keyword detection thread
        kw_thread = threading.Thread(target=self.keyword_detection_loop, daemon=True)
        kw_thread.start()
        # Start weather updater thread and fetch weather immediately
        fetch_and_send_weather(self.conn)
        threading.Thread(target=self.weather_updater, daemon=True).start()
        # Set recv timeout to detect dead connections (30s)
        self.conn.settimeout(30)
        try:
            self.safe_send(b"UI_STATE:IDLE\n")
        except Exception as e:
            print(f"Failed to send initial IDLE state: {e}")
            return
            
        while True:
            try:
                data = self.conn.recv(4096)
                if not data:
                    break
                
                # Accumulate into recv_buffer
                self.recv_buffer.extend(data)
                
                # Extract text commands embedded in the binary audio stream.
                # Commands are: CMD:WOKE\n, ___END___\n, LDR:xxx\n
                # Everything else is raw PCM audio bytes.
                #
                # IMPORTANT: Raw audio is binary — it contains random 0x0A bytes.
                # We must NOT split on \n generically. We only look for known
                # command prefixes as byte markers.
                
                audio_chunks = []  # collect audio byte segments
                
                processing = True
                while processing:
                    processing = False
                    
                    # Try to extract CMD: command
                    result = self._extract_command(self.recv_buffer, b"CMD:")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        cmd = cmd_bytes.decode('utf-8', errors='ignore').strip()
                        if cmd == "CMD:WOKE":
                            self.is_awake = True
                            self.speech_buffer = bytearray()
                            self.recording_start_time = time.time()
                            self.speech_ready_time = time.time() + 1.0
                            self.audio_bytes_received = 0
                            self.first_audio_time = 0
                            print("\n[*] Button pressed: recording started...")
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # Try to extract ___END___
                    result = self._extract_command(self.recv_buffer, b"___END___")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        if self.is_awake:
                            print("[*] Button released: recording stopped")
                            duration = time.time() - self.recording_start_time
                            self.process_speech(self.speech_buffer, duration)
                            self.speech_buffer = bytearray()
                            self.is_awake = False
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # Try to extract LDR: readings
                    result = self._extract_command(self.recv_buffer, b"LDR:")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        try:
                            ldr_str = cmd_bytes.decode('utf-8', errors='ignore').strip()
                            ldr_value = int(ldr_str.split(":")[1])
                            self.last_ldr_val = ldr_value
                            print(f"[*] LDR: {ldr_value} (0-4095)")
                            # Track LDR levels during sleep session
                            if hasattr(self, 'sleep_start_time') and self.sleep_start_time is not None:
                                if hasattr(self, 'sleep_ldr_levels'):
                                    self.sleep_ldr_levels.append(ldr_value)
                        except Exception:
                            pass
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # Try to extract TIMER_DONE (ESP32 notifies countdown completed)
                    result = self._extract_command(self.recv_buffer, b"TIMER_DONE")
                    if result:
                        global active_alarm_active, active_alarm_name, alarm_fired_at
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        self.timer_running = False
                        print("[TIMER] Countdown completed on ESP32, timer_running reset")
                        
                        # Trigger alarm sound on laptop/desktop speaker just like reminders/alarms!
                        active_alarm_active = True
                        active_alarm_name = "Timer Finished"
                        alarm_fired_at = datetime.datetime.now()
                        play_alarm_sound()
                        print("[TIMER] Playing completed alarm sound on laptop speaker...")
                        
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # Try to extract PIR:MOTION
                    result = self._extract_command(self.recv_buffer, b"PIR:MOTION")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        print("[PIR] Motion detected")
                        self.last_motion_time = time.time()
                        # Track motion during sleep
                        if hasattr(self, 'sleep_movement_count'):
                            self.sleep_movement_count += 1
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    # Try to extract PIR:WAKE (Device woke up fully due to motion/button/voice)
                    result = self._extract_command(self.recv_buffer, b"PIR:WAKE")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        self.last_pir_state = 'AWAKE'
                        print("[PIR] Device woke up fully.")
                        log_sleep_event("WAKE")
                        # End Sleep Monitoring Session and save to JSON
                        self.end_sleep_session()
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    # Try to extract PIR:SLEEP (Device went to sleep)
                    result = self._extract_command(self.recv_buffer, b"PIR:SLEEP")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        # Only log the transition to sleep to avoid spamming on keep-alive heartbeats
                        if self.last_pir_state != 'SLEEPING':
                            self.last_pir_state = 'SLEEPING'
                            print("[PIR] Device went to sleep.")
                            log_sleep_event("SLEEP")
                            # Start Sleep Monitoring Session
                            if not hasattr(self, 'sleep_start_time') or self.sleep_start_time is None:
                                self.sleep_start_time = time.time()
                                self.sleep_movement_count = 0
                                self.sleep_noise_levels = []
                                self.sleep_noise_events = 0
                                print(f"[Sleep Monitor] Session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    # Try to extract PIR:PREWAKE (Device entered pre-wake standby)
                    result = self._extract_command(self.recv_buffer, b"PIR:PREWAKE")
                    if result:
                        before, cmd_bytes, after = result
                        if before:
                            audio_chunks.append(bytes(before))
                        if self.last_pir_state != 'PREWAKE':
                            self.last_pir_state = 'PREWAKE'
                            print("[PIR] Device entered pre-wake standby.")
                            log_sleep_event("PREWAKE")
                            # Increment movement count during sleep (entering pre-wake counts as a movement)
                            if hasattr(self, 'sleep_movement_count'):
                                self.sleep_movement_count += 1
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                
                # Check if recv_buffer has a partial command marker at the tail
                # that might be completed by the next recv() call
                tail = bytes(self.recv_buffer)
                partial_markers = [b"CMD:", b"___END___", b"LDR:", b"TIMER_DONE", b"PIR:"]
                safe_len = len(tail)
                for marker in partial_markers:
                    # Check if the tail ends with any prefix of a marker
                    for prefix_len in range(1, len(marker)):
                        if tail.endswith(marker[:prefix_len]):
                            safe_len = min(safe_len, len(tail) - prefix_len)
                            break
                
                # Everything before the potential partial marker is audio data
                if safe_len > 0:
                    audio_data = bytes(self.recv_buffer[:safe_len])
                    self.recv_buffer = self.recv_buffer[safe_len:]
                    audio_chunks.append(audio_data)
                
                # Feed all extracted audio to keyword buffer and speech buffer
                for chunk in audio_chunks:
                    if chunk:
                        self.keyword_buffer.extend(chunk)
                        
                        # Real-time Sleep Monitor: Calculate audio RMS during sleep states
                        if self.last_pir_state in ('SLEEPING', 'PREWAKE'):
                            align_len = len(chunk) - (len(chunk) % 2)
                            if align_len >= 2:
                                samples = np.frombuffer(chunk[:align_len], dtype=np.int16)
                                if len(samples) > 0:
                                    rms = float(np.sqrt(np.mean(samples.astype(np.float64)**2)))
                                    if hasattr(self, 'sleep_noise_levels'):
                                        self.sleep_noise_levels.append(rms)
                                        # Threshold for noise spikes (coughing, snoring, tossing, door closing)
                                        if rms > 600.0:
                                            self.sleep_noise_events += 1
                        
                        if self.is_awake and time.time() >= self.speech_ready_time:
                            if self.first_audio_time == 0:
                                self.first_audio_time = time.time()
                            self.audio_bytes_received += len(chunk)
                            self.speech_buffer.extend(chunk)
                            
            except socket.timeout:
                print(f"[Timeout] No data from {self.addr} for 30s, disconnecting")
                break
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"[Error] Connection loop error: {e}")
                break
                
        print(f"[-] Client {self.addr} disconnected")
        if active_conn == self.conn:
            active_conn = None
        if active_handler == self:
            active_handler = None
        self.end_sleep_session()
            
    def end_sleep_session(self):
        if hasattr(self, 'sleep_start_time') and self.sleep_start_time is not None:
            end_time = time.time()
            duration = end_time - self.sleep_start_time
            duration_hours = duration / 3600.0
            
            # Discard very brief sessions under 10 minutes
            if duration < 600.0:
                print(f"[Sleep Monitor] Discarding short sleep session of {duration/60.0:.1f} minutes")
                self.sleep_start_time = None
                return
                
            # Classify session type: Sleep (>= 3 hours) or Nap (< 3 hours)
            session_type = "nap"
            if duration_hours >= 3.0:
                session_type = "actual_sleep"
            
            display_type = "Sleep" if session_type == "actual_sleep" else "Nap"
            
            # Calculate average and max noise
            if self.sleep_noise_levels:
                avg_noise = float(np.mean(self.sleep_noise_levels))
                max_noise = float(np.max(self.sleep_noise_levels))
            else:
                avg_noise = 0.0
                max_noise = 0.0
                
            # Calculate average LDR light levels
            if hasattr(self, 'sleep_ldr_levels') and self.sleep_ldr_levels:
                avg_ldr = float(np.mean(self.sleep_ldr_levels))
            else:
                avg_ldr = 150.0
                
            # Classify Sleep Quality: Good, Fair, Poor
            movements_per_hour = self.sleep_movement_count / duration_hours
            if movements_per_hour <= 2.0 and avg_noise <= 300.0 and avg_ldr <= 500.0:
                quality = "Good"
            elif movements_per_hour > 5.0 or avg_noise > 600.0 or avg_ldr > 1200.0:
                quality = "Poor"
            else:
                quality = "Fair"
                
            # Calculate tardiness if scheduled_sleep_time is active
            tardiness_mins = 0
            global scheduled_sleep_time
            if scheduled_sleep_time and session_type == "actual_sleep":
                try:
                    sh, sm = map(int, scheduled_sleep_time.split(":"))
                    start_dt = datetime.datetime.fromtimestamp(self.sleep_start_time)
                    scheduled_dt = start_dt.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    if start_dt.hour < 12 and sh >= 12:
                        scheduled_dt = scheduled_dt - datetime.timedelta(days=1)
                    if start_dt > scheduled_dt:
                        tardiness_mins = int((start_dt - scheduled_dt).total_seconds() / 60)
                except Exception as e:
                    print(f"[Warning] Failed to calculate tardiness: {e}")

            session_data = {
                "session_id": datetime.datetime.fromtimestamp(self.sleep_start_time).strftime("%Y%m%d_%H%M%S"),
                "type": session_type,
                "start_time": datetime.datetime.fromtimestamp(self.sleep_start_time).strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
                "duration_hours": round(duration_hours, 2),
                "movement_count": self.sleep_movement_count,
                "average_noise": round(avg_noise, 1),
                "max_noise": round(max_noise, 1),
                "noise_events": self.sleep_noise_events,
                "average_ldr": round(avg_ldr, 1),
                "quality": quality,
                "tardiness_minutes": tardiness_mins
            }
            
            # Send summary command back to client (ESP32)
            try:
                # Format: UI_SLEEP_SUMMARY:type:duration:movements:avg_noise:avg_ldr:quality
                summary_cmd = f"UI_SLEEP_SUMMARY:{display_type}:{duration_hours:.1f}:{self.sleep_movement_count}:{avg_noise:.0f}:{avg_ldr:.0f}:{quality}\n"
                self.safe_send(summary_cmd.encode())
                print(f"[Sleep Monitor] Sent summary to ESP32: {summary_cmd.strip()}")
            except Exception as e:
                print(f"[Sleep Monitor] Failed to send sleep summary to client: {e}")
            
            # Save to JSON
            file_path = "sleep_sessions.json"
            try:
                sessions = []
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            sessions = json.load(f)
                    except Exception:
                        sessions = []
                sessions.append(session_data)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, indent=2)
                print(f"[Sleep Monitor] Saved session to {file_path}: {session_data}")
            except Exception as e:
                print(f"[Sleep Monitor Error] Failed to save session: {e}")
                
            self.sleep_start_time = None
            
    def process_speech(self, audio_bytes, total_duration):
        global active_alarm_active
        
        # Ensure int16 alignment (TCP can split at any byte boundary)
        if len(audio_bytes) % 2 != 0:
            audio_bytes = audio_bytes[:-1]
        
        num_samples = len(audio_bytes) / 2
        if num_samples < 100:
            print(f"[!] Too few samples ({int(num_samples)}), skipping")
            try:
                self.safe_send(b"UI_STATE:IDLE\n")
            except Exception:
                pass
            return

        if self.first_audio_time > 0 and self.recording_start_time > 0:
            audio_duration = time.time() - self.first_audio_time
        else:
            audio_duration = total_duration

        if audio_duration < 0.1:
            audio_duration = total_duration

        # Rate from wall-clock (now accurate after discarding waving delay)
        measured_rate = int(num_samples / audio_duration) if audio_duration > 0 else 0
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[*] Audio Duration: {audio_duration:.2f}s, Rate: {measured_rate} Hz")

        # Resample to 16kHz (Parakeet's native rate) using linear interpolation
        try:
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
            if measured_rate > 0 and measured_rate != 16000 and len(audio_np) > 0:
                target_count = int(len(audio_np) * 16000 / measured_rate)
                src_idx = np.arange(len(audio_np))
                tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
                audio_np = np.interp(tgt_idx, src_idx, audio_np)
            audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
        except Exception as e:
            print(f"[Warning] Resample failed: {e}, using raw audio")
            audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Save raw recording for offline analysis (at measured rate)
        try:
            rec_path = os.path.join(RECORDINGS_DIR, f"rec_{ts}.wav")
            with wave.open(rec_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(measured_rate if measured_rate > 0 else 16000)
                wf.writeframes(audio_bytes)
            print(f"[*] Saved recording: {rec_path}")
        except Exception as e:
            print(f"[Warning] Failed to save recording: {e}")

        # (Speech enhancement bypassed to prevent ASR degradation from model artifacts)

        try:
            text = asr_model.recognize(audio_float, sample_rate=16000).strip()
            
            if not text:
                print("[No readable speech transcribed]")
                try:
                    self.safe_send(b"UI_STATE:IDLE\n")
                except Exception:
                    pass
                return
                
            print(f"[{'AWAKE' if self.is_awake else 'SLEEPING'}] Heard: '{text}'")

            # Log transcription result alongside the saved recording
            try:
                log_path = os.path.join(RECORDINGS_DIR, "transcriptions.log")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{ts}\t{measured_rate}\t16000\t{audio_duration:.2f}\t{text}\n")
            except Exception:
                pass
            
            # --- TIMER RUNNING BLOCK ---
            if self.timer_running:
                clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
                is_cancel = any(w in clean_text for w in ["cancel", "delete", "remove", "dismiss"]) or \
                            (any(w in clean_text for w in ["stop", "quit", "terminate", "shut up", "stop it"]) and "timer" in clean_text)
                is_pause = any(w in clean_text for w in ["pause", "hold"])
                is_resume = any(w in clean_text for w in ["resume", "continue", "start", "play"])

                if is_cancel:
                    self.timer_running = False
                    try:
                        self.safe_send(b"TIMER_CANCEL\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer stopped.")
                elif is_pause:
                    try:
                        self.safe_send(b"TIMER_PAUSE\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer paused.")
                elif is_resume:
                    try:
                        self.safe_send(b"TIMER_RESUME\n")
                    except Exception:
                        pass
                    play_speech_on_laptop("Timer resumed.")
                else:
                    play_speech_on_laptop("Countdown is active. Say stop timer to cancel.")
                
                self.is_awake = False
                return

            # --- ALARM DISMISSAL CHECK ---
            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            if active_alarm_active or any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
                if any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
                    if active_alarm_active:
                        stop_active_alarm()
                    try:
                        self.safe_send(b"TIMER_STOP\n")
                    except Exception:
                        pass
                    self.is_awake = False
                    self.safe_send(b"UI_STATE:IDLE\n")
                    return
            # --- TIMER SETUP CHECK (BUTTON PRESS MODE) ---
            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            is_timer_query = any(w in clean_text for w in ["timer", "countdown", "focus"])
            is_stop_intent = any(w in clean_text for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])
            
            if is_timer_query and not is_stop_intent:
                # Intercept normal timer setup
                duration = parse_timer_duration(clean_text)
                if duration is not None:
                    self.timer_running = True
                    try:
                        self.safe_send(f"TIMER_START:{duration}\n".encode())
                    except Exception:
                        pass
                    play_speech_on_laptop(f"Starting countdown for {format_duration(duration)}.")
                    self.is_awake = False
                else:
                    play_speech_on_laptop("Please specify seconds, minutes, or hours.")
                    self.is_awake = False
                    try:
                        self.safe_send(b"UI_STATE:IDLE\n")
                    except Exception:
                        pass
                return

            # --- LLM PROCESSING ---
            print(f"[*] Processing user prompt: '{text}'")
            self.safe_send(b"UI_STATE:THINKING\n")
            
            response = chat_session.send_message(text)  # send_message acquires chat_lock internally
            ai_answer = response.text.strip()
            print(f"[*] AI Response: {ai_answer}")
            
            # Parse and execute commands
            self.handle_llm_response(ai_answer)
            
            # Truncate session history to avoid token bloat (safe for odd-length)
            with chat_lock:
                while len(chat_session.history) > 6:
                    chat_session.history.pop(0)
                    
            # Put system back to sleep
            self.is_awake = False
                
        except Exception as e:
            print(f"[Error] process_speech pipeline error: {e}")
            try:
                self.safe_send(b"UI_MSG:AI Error.\n")
            except Exception:
                pass
            self.is_awake = False
            
    def handle_llm_response(self, ai_answer):
        # Scan for CMD tags - new format: [CMD:ADD_REMINDER|task|ABS|time] or [CMD:ADD_REMINDER|task|REL|30s]
        add_match = re.search(r'\[CMD:ADD_REMINDER\|([^|]+)\|(ABS|REL)\|([^\]]+)\]', ai_answer)
        delete_match = re.search(r'\[CMD:DELETE_REMINDER\|(\d+)\]', ai_answer)
        list_match = '[CMD:LIST_REMINDERS]' in ai_answer
        clear_match = '[CMD:CLEAR_REMINDERS]' in ai_answer
        sleep_cmd_match = '[CMD:START_SLEEP]' in ai_answer
        
        # Strip commands from message sent to user
        clean_answer = re.sub(r'\[CMD:[^\]]+\]', '', ai_answer).strip()
        # Remove any emojis/emoticons to prevent display corruption
        clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
        
        try:
            if add_match:
                task = add_match.group(1).strip()
                time_type = add_match.group(2).strip()
                time_value = add_match.group(3).strip()
                
                if time_type == "REL":
                    trigger_dt, display_str = parse_relative_time(time_value)
                else:
                    trigger_dt, display_str = parse_absolute_time(time_value)
                
                if trigger_dt:
                    add_reminder(task, trigger_dt, display_str)
                    self.safe_send(f"UI_MSG:{clean_answer}\n".encode())
                else:
                    self.safe_send(b"UI_MSG:Invalid time format.\n")
                
            elif delete_match:
                index = int(delete_match.group(1).strip())
                deleted_task = delete_reminder_by_index(index)
                if deleted_task:
                    header = f"UI_MSG:{clean_answer}\n".encode()
                    speak_on_esp32(self.conn, clean_answer, header=header)
                else:
                    msg = "Reminder index not found."
                    header = f"UI_MSG:{msg}\n".encode()
                    speak_on_esp32(self.conn, msg, header=header)
                    
            elif list_match:
                self.send_reminder_list()
                    
            elif clear_match:
                clear_reminders()
                self.safe_send(f"UI_MSG:{clean_answer}\n".encode())
                
            elif sleep_cmd_match:
                # Send Goodnight speech first
                header = f"UI_MSG:{clean_answer}\n".encode()
                speak_on_esp32(self.conn, clean_answer, header=header)
                # Send start sleep command to client (ESP32)
                self.safe_send(b"CMD:START_SLEEP\n")
                # Initialize Sleep Monitoring Session
                self.last_pir_state = 'SLEEPING'
                self.sleep_start_time = time.time()
                self.sleep_movement_count = 0
                self.sleep_noise_levels = []
                self.sleep_noise_events = 0
                self.sleep_ldr_levels = []
                print(f"[Sleep Monitor] Manual sleep session triggered via voice command.")
                
            else:
                # Send display text + TTS atomically (no interleaving between UI_MSG and AUDIO)
                header = f"UI_MSG:{clean_answer}\n".encode()
                speak_on_esp32(self.conn, clean_answer, header=header)
        except Exception as e:
            print(f"[Error] Failed to send socket command: {e}")

def udp_discovery_beacon():
    """Broadcast UDP discovery packets to help ESP32 dynamically locate the server IP"""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[Discovery] UDP beacon broadcaster running on port 9999...")
    while True:
        try:
            broadcasts = ['255.255.255.255']
            # Find all local interface IPs on the PC
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith("127."):
                    parts = ip.split('.')
                    if len(parts) == 4:
                        parts[3] = '255'
                        broadcasts.append('.'.join(parts))
            for bcast in set(broadcasts):
                try:
                    udp_sock.sendto(b"TABLE_BONDHU_BEACON", (bcast, 9999))
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(2)

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class CompanionRestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging every GET/POST request to keep stdout clean
        return

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        if self.path == '/api/reminders':
            self._set_headers(200)
            active_list = get_reminders_list()
            self.wfile.write(json.dumps(active_list).encode('utf-8'))

        elif self.path == '/api/ping':
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "OK"}).encode('utf-8'))

        elif self.path == '/api/sleep/schedule':
            self._set_headers(200)
            global scheduled_sleep_time
            self.wfile.write(json.dumps({"scheduled_time": scheduled_sleep_time or ""}).encode('utf-8'))

        elif self.path == '/api/sleep':
            self._set_headers(200)
            sessions = []
            if os.path.exists("sleep_sessions.json"):
                try:
                    with open("sleep_sessions.json", "r", encoding="utf-8") as f:
                        sessions = json.load(f)
                except Exception:
                    pass
            self.wfile.write(json.dumps(sessions).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_POST(self):
        global active_conn, active_handler, chat_session, scheduled_sleep_time
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception:
            data = {}

        if self.path == '/api/chat':
            message = data.get("message", "")
            if not message:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty message"}).encode('utf-8'))
                return

            print(f"[REST Chat] Message from app: '{message}'")
            
            # 1. Intercept timer countdown setup
            clean_msg = re.sub(r'[^\w\s]', '', message.lower()).strip()
            is_timer_query = any(w in clean_msg for w in ["timer", "countdown", "focus"])
            is_stop_intent = any(w in clean_msg for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])
            
            if is_timer_query and not is_stop_intent:
                duration = parse_timer_duration(clean_msg)
                if duration is not None:
                    if active_handler:
                        active_handler.timer_running = True
                    if active_conn:
                        try:
                            active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                        except Exception:
                            pass
                    response_text = f"Starting focus countdown for {format_duration(duration)}."
                    play_speech_on_laptop(response_text)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"response": response_text}).encode('utf-8'))
                    return

            # 2. Process LLM message
            if active_handler:
                try:
                    active_handler.safe_send(b"UI_STATE:THINKING\n")
                except Exception:
                    pass

            try:
                response = chat_session.send_message(message)
                ai_answer = response.text.strip()
                print(f"[REST Chat] AI Response: {ai_answer}")

                # Execute tags and play audio
                if active_handler:
                    active_handler.handle_llm_response(ai_answer)
                else:
                    clean_answer = re.sub(r'\[CMD:[^\]]+\]', '', ai_answer).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'\[CMD:[^\]]+\]', '', ai_answer).strip()
                clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

                self._set_headers(200)
                self.wfile.write(json.dumps({"response": clean_answer}).encode('utf-8'))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/voice_chat':
            audio_b64 = data.get("audio", "")
            if not audio_b64:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty audio data"}).encode('utf-8'))
                return

            print("[REST Voice Chat] Received audio upload from app. Processing ASR...")
            try:
                import base64
                audio_bytes = base64.b64decode(audio_b64)
                temp_path = "temp_app_voice.wav"
                with open(temp_path, "wb") as f:
                    f.write(audio_bytes)

                # Load and resample using pydub
                sound = AudioSegment.from_file(temp_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio_samples = np.frombuffer(sound.raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                text = asr_model.recognize(audio_samples, sample_rate=16000).strip()
                print(f"[REST Voice Chat] Transcribed: '{text}'")

                if not text:
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"text": "", "response": "Could not recognize speech. Please try speaking clearer."}).encode('utf-8'))
                    return

                # Intercept countdown query in voice
                clean_msg = re.sub(r'[^\w\s]', '', text.lower()).strip()
                is_timer_query = any(w in clean_msg for w in ["timer", "countdown", "focus"])
                is_stop_intent = any(w in clean_msg for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])
                
                if is_timer_query and not is_stop_intent:
                    duration = parse_timer_duration(clean_msg)
                    if duration is not None:
                        if active_handler:
                            active_handler.timer_running = True
                        if active_conn:
                            try:
                                active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                            except Exception:
                                pass
                        response_text = f"Starting focus countdown for {format_duration(duration)}."
                        play_speech_on_laptop(response_text)
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"text": text, "response": response_text}).encode('utf-8'))
                        return

                # Process LLM query
                if active_handler:
                    try:
                        active_handler.safe_send(b"UI_STATE:THINKING\n")
                    except Exception:
                        pass

                response = chat_session.send_message(text)
                ai_answer = response.text.strip()
                print(f"[REST Voice Chat] AI Response: {ai_answer}")

                if active_handler:
                    active_handler.handle_llm_response(ai_answer)
                else:
                    clean_answer = re.sub(r'\[CMD:[^\]]+\]', '', ai_answer).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'\[CMD:[^\]]+\]', '', ai_answer).strip()
                clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

                self._set_headers(200)
                self.wfile.write(json.dumps({"text": text, "response": clean_answer}).encode('utf-8'))
            except Exception as e:
                print(f"[REST Voice Error] {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/reminders':
            task = data.get("task", "")
            time_str = data.get("time", "")  # Expecting YYYY-MM-DD HH:MM:SS
            if not task or not time_str:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing task or time"}).encode('utf-8'))
                return

            try:
                trigger_dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                display_str = trigger_dt.strftime("%I:%M %p")
                add_reminder(task, trigger_dt, display_str)
                
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/reminders/delete':
            index = data.get("index") # 1-indexed
            if index is None:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing index"}).encode('utf-8'))
                return

            deleted_task = delete_reminder_by_index(index)
            if deleted_task:
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "deleted": deleted_task}).encode('utf-8'))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Reminder not found"}).encode('utf-8'))

        elif self.path == '/api/reminders/clear':
            clear_reminders()
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        elif self.path == '/api/timer/start':
            duration = data.get("duration", 1500)
            if active_handler:
                active_handler.timer_running = True
            if active_conn:
                try:
                    active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                except Exception:
                    pass
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        elif self.path == '/api/timer/cancel':
            if active_handler:
                active_handler.timer_running = False
            if active_conn:
                try:
                    active_conn.sendall(b"TIMER_CANCEL\n")
                except Exception:
                    pass
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        elif self.path == '/api/sleep/start':
            sleep_type = data.get("type", "sleep")
            print(f"[REST Sleep] Force sleep trigger from app: {sleep_type}")
            if active_handler:
                active_handler.sleep_start_time = time.time()
                active_handler.sleep_movement_count = 0
                active_handler.sleep_noise_levels = []
                active_handler.sleep_noise_events = 0
                active_handler.sleep_ldr_levels = []
                active_handler.last_pir_state = 'SLEEPING'
                try:
                    active_conn.sendall(b"CMD:START_SLEEP\n")
                except Exception:
                    pass
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "ESP32 desk clock is not connected to the server right now."}).encode('utf-8'))

        elif self.path == '/api/sleep/schedule':
            time_val = data.get("time", "") # HH:MM
            scheduled_sleep_time = time_val
            print(f"[REST Sleep] Configured target bedtime to: {scheduled_sleep_time}")
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS", "scheduled_time": scheduled_sleep_time}).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

def run_rest_server():
    server_address = ('', 8888)
    httpd = HTTPServer(server_address, CompanionRestHandler)
    print("[REST API] Server running on port 8888...")
    httpd.serve_forever()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        
        print(f"\nHands-free Companion Server running on {HOST}:{PORT}")
        print("Waiting for ESP32 connection...")
        
        # Start scheduler
        sched_thread = threading.Thread(target=alarm_scheduler, daemon=True)
        sched_thread.start()
        
        # Start UDP Discovery Beacon Broadcaster
        udp_thread = threading.Thread(target=udp_discovery_beacon, daemon=True)
        udp_thread.start()

        # Start REST API Web Server
        rest_thread = threading.Thread(target=run_rest_server, daemon=True)
        rest_thread.start()
        
        while True:
            conn, addr = s.accept()
            handler = VoiceAgentHandler(conn, addr)
            client_thread = threading.Thread(target=handler.run, daemon=True)
            client_thread.start()

if __name__ == "__main__":
    start_server()
