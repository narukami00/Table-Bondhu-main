"""
Agentic Companion Server (Raspberry Pi 4 Optimized - FULLY RESTORED)
All ESP32 communication features restored + Pi optimizations
"""

import ollama
import socket
import numpy as np
from faster_whisper import WhisperModel
import threading
import time
import wave
import os
import re
import json
import subprocess
import datetime
import math
import struct
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080
OLLAMA_CLIENT = ollama.Client(host='http://127.0.0.1:11434', timeout=60)
MODEL_NAME = "qwen2.5:0.5b"
REMINDERS_FILE = "reminders.json"
RECORDINGS_DIR = "recordings_analysis"
COMMAND_TRIGGERS = ["reminder", "reminders", "hi", "hello", "hey", "yo"]
QUESTION_WORDS = ["what", "how", "why", "can you", "is", "do", "where",
                   "when", "who", "which", "could", "would", "should",
                   "tell me", "explain"]
KEYWORD_CHUNK_SECONDS = 1.5
KEYWORD_DEBOUNCE_SECONDS = 5
keyword_suppress_until = 0  # suppress keyword detection while TTS is playing

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
# Sleep state: persisted across app restarts via sleep_status.json
is_sleeping = False
sleep_status_file = "sleep_status.json"
# Sleep Window: auto-sleep only allowed between these hours (prevents false-sleep when away)
sleep_window_start = 22   # Hour (24h) when auto-sleep activates
sleep_window_end   = 10   # Hour (24h) when auto-sleep deactivates
send_lock = threading.Lock()
chat_lock = threading.Lock()
active_audio_process = None
loop_alarm_active = False


def _load_sleep_status():
    """Restore is_sleeping from disk on server restart."""
    global is_sleeping
    if os.path.exists(sleep_status_file):
        try:
            with open(sleep_status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            is_sleeping = data.get("is_sleeping", False)
        except Exception:
            is_sleeping = False


def _save_sleep_status(sleeping: bool, start_time=None):
    """Persist sleep state so the Android app can query it after reopen."""
    global is_sleeping
    is_sleeping = sleeping
    payload = {
        "is_sleeping": sleeping,
        "start_time": start_time,
        "updated_at": datetime.datetime.now().isoformat()
    }
    try:
        with open(sleep_status_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as e:
        print(f"[Sleep Status] Failed to persist status: {e}")


# Load persisted sleep state on startup
_load_sleep_status()

# --- LLM SYSTEM INSTRUCTION (Optimized for Qwen 0.5B) ---
SYSTEM_INSTRUCTION = """You are a helpful offline desk assistant.
Your answers are displayed on a small screen.
RULES:
1. Keep every answer under 15 words.
2. NO markdown. NO emojis.
3. ONLY use command tags when the user explicitly asks for reminders, alarms, sleep, or timer. For casual conversation like greetings or questions, respond naturally WITHOUT any tags.
4. Do NOT invent new tags or modify the tag name. Format tags exactly as specified below.

Command tags (ONLY when requested):
- Going to sleep: append [CMD:START_SLEEP]. Example: "I am taking a nap" -> "Goodnight! Sweet dreams. [CMD:START_SLEEP]"
- Set reminder: [CMD:ADD_REMINDER|task|ABS|time] or [CMD:ADD_REMINDER|task|REL|time]
  Examples: remind me at 3pm -> Added. [CMD:ADD_REMINDER|Reminder|ABS|3:00 PM]
  remind me in 5 minutes -> Added. [CMD:ADD_REMINDER|Reminder|REL|5m]
- List reminders: [CMD:LIST_REMINDERS]
- Clear reminders: [CMD:CLEAR_REMINDERS]
- Delete reminder: [CMD:DELETE_REMINDER|index]
  Examples: delete the second reminder -> Deleted. [CMD:DELETE_REMINDER|2]

Do not explain the command tags. Just include them at the end of your response."""

class LocalChatSession:
    def __init__(self, system_instruction):
        self.system_instruction = system_instruction
        self.history = []

    def send_message(self, user_text):
        with chat_lock:
            self.history.append({"role": "user", "content": user_text})
            messages = []
            if self.system_instruction:
                now = datetime.datetime.now()
                time_ctx = now.strftime("%A, %d %B %Y %I:%M %p")
                
                active_rems = get_reminders_list()
                rem_list_str = "\n".join([f"{i}. {r.get('task')} at {r.get('display_time')}" for i, r in enumerate(active_rems, 1)]) or "None"
                
                sys_prompt = (
                    f"{self.system_instruction}\n\n"
                    f"CONTEXT: Time={time_ctx}. Active Reminders: {rem_list_str}"
                )
                messages.append({"role": "system", "content": sys_prompt})
            messages.extend(self.history[-4:])
            
            try:
                # Optimized generation parameters for local execution on Pi 4 (reduced search space & prediction tokens)
                response = OLLAMA_CLIENT.chat(
                    model=MODEL_NAME,
                    messages=messages,
                    options={
                        "temperature": 0.1,
                        "num_predict": 50,
                        "top_k": 20,
                        "top_p": 0.85
                    },
                    keep_alive="15m"
                )
                ai_answer = response['message']['content']
            except Exception as e:
                print(f"[LLM Error] Ollama request failed: {e}")
                ai_answer = "My brain is offline. Please try again."
                
            self.history.append({"role": "assistant", "content": ai_answer})
        
        class ResponseObject:
            def __init__(self, text): self.text = text
        return ResponseObject(ai_answer)

print("Loading Faster-Whisper (tiny.en, int8 for Pi 4)...")
asr_model = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=4)
print("[*] Faster-Whisper loaded successfully.")

print("Loading Offline VITS Text-to-Speech...")
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
    print("[*] Offline VITS Text-to-Speech loaded successfully.")
except Exception as e:
    offline_tts = None
    print(f"[Warning] Failed to load Offline VITS: {e}. Will fallback to espeak.")

print("Initializing Local LLM Session...")
chat_session = LocalChatSession(system_instruction=SYSTEM_INSTRUCTION)
print("Systems Online! Ready to listen.")

# --- AUDIO HELPERS ---
def generate_default_sounds():
    if not os.path.exists("beep.wav"):
        with wave.open("beep.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            for i in range(1200):
                w.writeframes(struct.pack('h', int(32767.0 * math.sin(2.0 * math.pi * 2000 * i / 8000))))
    if not os.path.exists("alarm_sound.wav"):
        with wave.open("alarm_sound.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            for i in range(8000):
                val = int(32767.0 * math.sin(2.0 * math.pi * 1000 * i / 8000)) if (i % 1600) < 800 else 0
                w.writeframes(struct.pack('h', val))

def play_wake_up_sound():
    global keyword_suppress_until
    generate_default_sounds()
    try:
        subprocess.Popen(["pw-play", "beep.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        keyword_suppress_until = time.time() + 0.5
    except Exception as e:
        print(f"[Audio Error] Failed to play wake up sound: {e}")

def play_alarm_sound():
    global active_audio_process, loop_alarm_active
    stop_active_alarm()
    generate_default_sounds()
    loop_alarm_active = True
    def alarm_loop():
        global active_audio_process
        while loop_alarm_active:
            try:
                proc = subprocess.Popen(["pw-play", "alarm_sound.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                active_audio_process = proc
                proc.wait()
            except Exception: break
            time.sleep(0.5)
    threading.Thread(target=alarm_loop, daemon=True).start()

def stop_active_alarm():
    global active_alarm_active, active_alarm_name, alarm_fired_at, active_audio_process, loop_alarm_active
    active_alarm_active = False; active_alarm_name = ""; alarm_fired_at = None; loop_alarm_active = False
    if active_audio_process is not None:
        try: active_audio_process.kill()
        except Exception: pass
        active_audio_process = None
    # Kill any orphaned pw-play processes from the alarm loop
    try:
        subprocess.run(["pkill", "-f", "pw-play alarm_sound.wav"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception: pass
    print("[Alarm] Buzzing stopped.")

def play_speech_on_laptop(text):
    global keyword_suppress_until
    try:
        temp_wav = "temp_tts.wav"
        success = False
        
        if offline_tts is not None:
            try:
                audio = offline_tts.generate(text)
                audio_samples = np.array(audio.samples, dtype=np.float32)
                int16_samples = (audio_samples * 32767.0).astype(np.int16)
                with wave.open(temp_wav, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(audio.sample_rate)
                    w.writeframes(int16_samples.tobytes())
                success = True
            except Exception as tts_err:
                print(f"[Warning] VITS failed: {tts_err}")
        
        if not success:
            print("[TTS] Falling back to espeak (100% offline)")
            subprocess.run(["espeak", "-v", "en", "-s", "150", "-p", "75", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            espeak_dur = max(2.0, len(text.split()) / 2.5)
            keyword_suppress_until = time.time() + espeak_dur + 0.5
            return espeak_dur
        
        duration_sec = max(2.0, len(text.split()) / 2.5)
        subprocess.Popen(["pw-play", temp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        keyword_suppress_until = time.time() + duration_sec + 0.5
        return duration_sec
        
    except Exception as e:
        print(f"[TTS Error] {e}")
        return None

def speak_on_esp32(conn, text, header=None):
    duration_sec = play_speech_on_laptop(text)
    if duration_sec is None: duration_sec = max(5.0, len(text) * 0.1)
    try:
        with send_lock:
            if header: conn.sendall(header)
            conn.sendall(f"DURATION:{duration_sec:.1f}\n".encode())
        print(f"[TTS Laptop] Sent sync instructions (duration: {duration_sec:.1f}s) to ESP32")
        return True
    except Exception as e:
        print(f"[TTS Laptop Error] Failed to send sync: {e}")
        return False

# --- REMINDERS & SCHEDULER STORE ---
db_lock = threading.Lock()

def parse_relative_time(rel_str):
    rel_str = rel_str.strip().lower()
    match = re.match(r'^(\d+)\s*(s|sec|second|m|min|minute|h|hr|hour)s?$', rel_str)
    if not match: return None, None
    amount, unit = int(match.group(1)), match.group(2)
    if unit in ('s', 'sec', 'second'):
        delta, display = datetime.timedelta(seconds=amount), f"in {amount} second{'s' if amount != 1 else ''}"
    elif unit in ('m', 'min', 'minute'):
        delta, display = datetime.timedelta(minutes=amount), f"in {amount} minute{'s' if amount != 1 else ''}"
    else:
        delta, display = datetime.timedelta(hours=amount), f"in {amount} hour{'s' if amount != 1 else ''}"
    return datetime.datetime.now() + delta, display

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
    if not os.path.exists(REMINDERS_FILE): return []
    try:
        with open(REMINDERS_FILE, 'r') as f:
            reminders = json.load(f)
        # Migrate old format: {time: "HH:MM"} -> {trigger_time: ISO, display_time: str}
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
    with db_lock:
        reminders = _load_reminders_internal()
        reminders.append({"task": task, "trigger_time": trigger_dt.isoformat(), "display_time": display_str, "fired": False, "created": datetime.datetime.now().isoformat()})
        _save_reminders_internal(reminders)

def get_reminders_list():
    with db_lock: return [r for r in _load_reminders_internal() if not r.get("fired", False)]

def clear_reminders():
    with db_lock: _save_reminders_internal([])

def delete_reminder_by_index(index):
    with db_lock:
        try:
            index = int(index)
        except (ValueError, TypeError):
            print(f"[Reminder] Failed to cast index {index} to integer.")
            return None
        reminders = _load_reminders_internal()
        active = [r for r in reminders if not r.get("fired", False)]
        if 1 <= index <= len(active):
            active[index - 1]["fired"] = True
            _save_reminders_internal(reminders)
            return active[index - 1].get("task", "Reminder")
    return None

# --- WEATHER ---
def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.8956&longitude=89.5011&currentweather=true"
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
    if not matches: return None
    total_seconds = 0
    for val_str, unit in matches:
        val = int(val_str)
        if unit.startswith('s'): total_seconds += val
        elif unit.startswith('m'): total_seconds += val * 60
        elif unit.startswith('h') or unit.startswith('hr'): total_seconds += val * 3600
    return total_seconds if total_seconds > 0 else None

def format_duration(seconds):
    if seconds < 60: return f"{seconds} seconds"
    elif seconds < 3600:
        m, s = seconds // 60, seconds % 60
        return f"{m} minutes and {s} seconds" if s > 0 else f"{m} minutes"
    else:
        h, m = seconds // 3600, (seconds % 3600) // 60
        return f"{h} hours and {m} minutes" if m > 0 else f"{h} hours"

def log_sleep_event(event_name):
    try:
        log_path = os.path.join(RECORDINGS_DIR, "sleep_sessions.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts}\t{event_name}\n")
    except Exception as e:
        print(f"[Error] Failed to write to sleep_sessions.log: {e}")

# --- SCHEDULER THREAD ---
def alarm_scheduler():
    global active_alarm_active, active_alarm_name, active_conn, alarm_fired_at, scheduled_sleep_time, scheduled_sleep_checked_today, active_handler
    print("[*] Alarm scheduler active.")
    
    while True:
        try:
            now = datetime.datetime.now()
            
            if active_alarm_active and alarm_fired_at is not None:
                elapsed = (now - alarm_fired_at).total_seconds()
                if elapsed > 30:
                    print(f"[ALARM] Auto-dismissed after {int(elapsed)}s")
                    stop_active_alarm()
                    alarm_fired_at = None
                    if active_conn:
                        try:
                            with send_lock: active_conn.sendall(b"UI_STATE:IDLE\n")
                        except Exception: pass
            
            if scheduled_sleep_time:
                now_hm = now.strftime("%H:%M")
                if now_hm == scheduled_sleep_time:
                    if not scheduled_sleep_checked_today:
                        scheduled_sleep_checked_today = True
                        print(f"[Sleep Schedule] Target time {scheduled_sleep_time} reached!")
                        
                        if active_handler:
                            last_ldr = getattr(active_handler, 'last_ldr_val', 500)
                            last_motion = getattr(active_handler, 'last_motion_time', time.time())
                            time_since_motion = time.time() - last_motion
                            
                            if last_ldr < 200 and time_since_motion >= 300:
                                print("[Sleep Schedule] Conditions MET. Triggering sleep automatically!")
                                active_handler.sleep_start_time = time.time()
                                active_handler.sleep_movement_count = 0
                                active_handler.sleep_noise_levels = []
                                active_handler.sleep_noise_events = 0
                                active_handler.sleep_ldr_levels = [last_ldr]
                                active_handler.last_pir_state = 'SLEEPING'
                                _save_sleep_status(True, active_handler.sleep_start_time)
                                try: active_conn.sendall(b"CMD:START_SLEEP\n")
                                except Exception: pass

            pending_alarms = []
            with db_lock:
                reminders = _load_reminders_internal()
                updated = False
                
                for r in reminders:
                    if r.get("fired", False): continue
                    trigger_str = r.get("trigger_time", "")
                    if not trigger_str: continue
                    try:
                        trigger_dt = datetime.datetime.fromisoformat(trigger_str)
                    except ValueError: continue
                    if now >= trigger_dt:
                        r["fired"] = True; updated = True
                        active_alarm_active = True
                        active_alarm_name = r.get("task", "Alarm")
                        alarm_fired_at = now
                        pending_alarms.append(r.get("display_time", trigger_str))
                        
                if updated: _save_reminders_internal(reminders)
            
            for display in pending_alarms:
                print(f"\n[ALARM] Triggered! Task: {active_alarm_name} (was set for {display})")
                play_alarm_sound()
                if active_conn:
                    try:
                        with send_lock: active_conn.sendall(f"UI_ALARM:{active_alarm_name}\n".encode())
                    except Exception as e:
                        print(f"Failed to send alarm command to client: {e}")
                
        except Exception as e:
            print(f"[Scheduler Error] {e}")
            
        time.sleep(5)

# --- CLIENT SOCKET HANDLER (FULLY RESTORED) ---
class VoiceAgentHandler:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.is_awake = False
        self.is_speaking = False
        self.speech_buffer = bytearray()
        self.noise_floor = 300
        self.rms_threshold = 450
        self.recording_start_time = 0
        self.speech_ready_time = 0
        self.audio_bytes_received = 0
        self.first_audio_time = 0
        self.keyword_buffer = bytearray()
        self.keyword_chunk_start = time.time()
        self.last_keyword_trigger = 0
        self.recv_buffer = bytearray()
        self.send_lock = threading.Lock()
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.timer_running = False
        self.last_pir_state = 'AWAKE'
        self.last_ldr_val = 500
        self.last_motion_time = time.time()
        self.sleep_start_time = None
        self.sleep_movement_count = 0
        self.sleep_noise_levels = []
        self.sleep_noise_events = 0
        self.sleep_ldr_levels = []
        
    def calibrate(self):
        print(f"[*] Calibrating noise baseline for {self.addr}...")
        
        self.conn.setblocking(False)
        try:
            while True:
                if not self.conn.recv(16384): break
        except (BlockingIOError, Exception): pass
        finally:
            self.conn.setblocking(True)
        
        calibration_rms = []
        start_time = time.time()
        while time.time() - start_time < 1.0:
            try:
                data = self.conn.recv(4096)
                if not data: break
                data_np = np.frombuffer(data, dtype=np.int16)
                if len(data_np) > 0:
                    rms = np.sqrt(np.mean(data_np.astype(np.float64)**2))
                    calibration_rms.append(rms)
            except Exception: break
            
        if calibration_rms:
            self.noise_floor = np.mean(calibration_rms)
            self.rms_threshold = max(self.noise_floor * 1.55, 450)
            print(f"[*] Calibration complete. Noise Floor: {self.noise_floor:.1f}")
        else:
            print("[!] Calibration failed. Using defaults.")

    def safe_send(self, data):
        with send_lock:
            try: self.conn.sendall(data)
            except Exception: pass

    def keyword_detection_loop(self):
        while True:
            time.sleep(0.5)
            if self.is_awake or self.timer_running: continue
            # Suppress keyword detection while TTS is playing through speakers
            if time.time() < keyword_suppress_until:
                self.keyword_buffer = bytearray()
                self.keyword_chunk_start = time.time()
                continue
            elapsed = time.time() - self.keyword_chunk_start
            # Early trigger: if we have at least 0.5s of audio and the tail is silent, process now
            should_process = elapsed >= KEYWORD_CHUNK_SECONDS
            if not should_process and elapsed >= 0.5 and len(self.keyword_buffer) >= 1600:
                tail = self.keyword_buffer[-1600:]  # last 0.5s (16-bit mono 16kHz)
                tail_samples = np.frombuffer(bytes(tail), dtype=np.int16)
                if len(tail_samples) > 0:
                    rms = float(np.sqrt(np.mean(tail_samples.astype(np.float64)**2)))
                    if rms < 150:  # silence threshold
                        should_process = True
            if not should_process: continue
            if len(self.keyword_buffer) < 800:
                self.keyword_buffer = bytearray()
                self.keyword_chunk_start = time.time()
                continue

            chunk = bytes(self.keyword_buffer)
            self.keyword_buffer = bytearray()
            self.keyword_chunk_start = time.time()

            num_samples = len(chunk) / 2
            measured_rate = int(num_samples / KEYWORD_CHUNK_SECONDS) if KEYWORD_CHUNK_SECONDS > 0 else 0
            if measured_rate < 1000: continue

            try:
                audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float64)
                if measured_rate != 16000 and len(audio_np) > 0:
                    target_count = int(len(audio_np) * 16000 / measured_rate)
                    src_idx = np.arange(len(audio_np))
                    tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
                    audio_np = np.interp(tgt_idx, src_idx, audio_np)
                audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
            except Exception: continue

            try:
                segments, info = asr_model.transcribe(audio_float, language="en", beam_size=1, vad_filter=False)
                text = " ".join([segment.text for segment in segments]).strip()
            except Exception: continue
            if not text: continue

            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            print(f"[KEYWORD] Heard: '{text}'")

            if time.time() - self.last_keyword_trigger < KEYWORD_DEBOUNCE_SECONDS: continue

            if self.timer_running:
                is_cancel = any(w in clean_text for w in ["cancel", "delete", "remove", "dismiss"]) or \
                            (any(w in clean_text for w in ["stop", "quit", "terminate", "shut up", "stop it"]) and "timer" in clean_text)
                is_pause = any(w in clean_text for w in ["pause", "hold"])
                is_resume = any(w in clean_text for w in ["resume", "continue", "start", "play"])
                
                if is_cancel:
                    self.last_keyword_trigger = time.time()
                    self.timer_running = False
                    try: self.safe_send(b"TIMER_CANCEL\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer stopped.")
                elif is_pause:
                    self.last_keyword_trigger = time.time()
                    try: self.safe_send(b"TIMER_PAUSE\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer paused.")
                elif is_resume:
                    self.last_keyword_trigger = time.time()
                    try: self.safe_send(b"TIMER_RESUME\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer resumed.")
                continue

            has_target_word = any(w in clean_text for w in ["reminder", "reminders", "alarm", "alarms", "task", "tasks"])
            is_creation_intent = any(w in clean_text for w in ["set", "add", "create", "remind me", "remind me to"])
            is_delete_intent = any(w in clean_text for w in ["delete", "remove", "clear", "cancel"])
            
            if has_target_word and not is_creation_intent and not is_delete_intent:
                self.last_keyword_trigger = time.time()
                self.send_reminder_list()
                continue

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
                            threading.Timer(1.5, self.send_reminder_list).start()
                        else:
                            self.safe_send(b"UI_MSG:Not found.\n")
                            play_speech_on_laptop(f"Could not find reminder number {idx}.")
                    else:
                        self.safe_send(b"UI_MSG:Specify index.\n")
                        play_speech_on_laptop("Which reminder number would you like to delete?")
                continue

            greeting_words = ["hi", "hello", "hey", "yo"]
            is_greeting = any(w in clean_text.split() for w in greeting_words)
            if is_greeting:
                self.last_keyword_trigger = time.time()
                self.play_greeting()
                continue

            is_timer_query = any(w in clean_text for w in ["timer", "countdown", "focus"])
            if is_timer_query:
                self.last_keyword_trigger = time.time()
                if any(w in clean_text for w in ["cancel", "stop", "quit", "terminate", "shut up", "stop it"]):
                    play_speech_on_laptop("No timer is currently running.")
                else:
                    duration = parse_timer_duration(clean_text)
                    if duration is not None:
                        self.timer_running = True
                        try: self.safe_send(f"TIMER_START:{duration}\n".encode())
                        except Exception: pass
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
            if clean_word in number_map: return number_map[clean_word]
        match = re.search(r'\b\d+\b', text)
        if match: return int(match.group(0))
        return None

    def send_reminder_list(self):
        reminders = get_reminders_list()
        try:
            if reminders:
                formatted_items = []
                for idx, r in enumerate(reminders, 1):
                    task = r['task']
                    time_str = r.get('display_time', '?')
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

    def weather_updater(self):
        while True:
            time.sleep(1800)
            if active_conn == self.conn:
                fetch_and_send_weather(self.conn)
            else:
                break

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
            response = chat_session.send_message(text)
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
        pos = buf.find(marker)
        if pos < 0: return None
        nl_pos = buf.find(b"\n", pos)
        if nl_pos < 0: return None
        before = buf[:pos]
        cmd = buf[pos:nl_pos].decode('utf-8', errors='ignore').strip()
        after = buf[nl_pos+1:]
        return (before, cmd, after)

    def run(self):
        global active_conn, active_handler, active_alarm_active, active_alarm_name, alarm_fired_at
        active_conn = self.conn
        active_handler = self
        
        self.calibrate()
        kw_thread = threading.Thread(target=self.keyword_detection_loop, daemon=True)
        kw_thread.start()
        # Fetch weather immediately and start periodic updater
        fetch_and_send_weather(self.conn)
        threading.Thread(target=self.weather_updater, daemon=True).start()
        self.conn.settimeout(30)
        try:
            self.safe_send(b"UI_STATE:IDLE\n")
        except Exception as e:
            print(f"Failed to send initial IDLE state: {e}")
            return
            
        while True:
            try:
                data = self.conn.recv(4096)
                if not data: break
                
                self.recv_buffer.extend(data)
                audio_chunks = []
                
                processing = True
                while processing:
                    processing = False
                    
                    result = self._extract_command(self.recv_buffer, b"CMD:")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if cmd == "CMD:WOKE":
                            self.is_awake = True
                            self.speech_buffer = bytearray()
                            self.recording_start_time = time.time()
                            self.speech_ready_time = time.time() + 1.0
                            self.audio_bytes_received = 0
                            self.first_audio_time = 0
                            print("\n[*] Button pressed: recording started...")
                            if active_alarm_active:
                                print("[Alarm] Physical button pressed. Silencing server alarm.")
                                stop_active_alarm()
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    result = self._extract_command(self.recv_buffer, b"___END___")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if self.is_awake:
                            print("[*] Button released: recording stopped")
                            duration = time.time() - self.recording_start_time
                            self.process_speech(self.speech_buffer, duration)
                            self.speech_buffer = bytearray()
                            self.is_awake = False
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    result = self._extract_command(self.recv_buffer, b"LDR:")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        try:
                            ldr_value = int(cmd.split(":")[1])
                            self.last_ldr_val = ldr_value
                            print(f"[*] LDR: {ldr_value} (0-4095)")
                            if self.sleep_start_time is not None:
                                self.sleep_ldr_levels.append(ldr_value)
                        except Exception: pass
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # Try to extract TIMER_DONE (ESP32 notifies countdown completed)
                    result = self._extract_command(self.recv_buffer, b"TIMER_DONE")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        self.timer_running = False
                        print("[TIMER] Countdown completed on ESP32")
                        
                        active_alarm_active = True
                        active_alarm_name = "Timer Finished"
                        alarm_fired_at = datetime.datetime.now()
                        play_alarm_sound()
                        print("[TIMER] Playing completed alarm sound...")
                        
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    result = self._extract_command(self.recv_buffer, b"PIR:MOTION")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        print("[PIR] Motion detected")
                        self.last_motion_time = time.time()
                        if self.sleep_start_time is not None:
                            self.sleep_movement_count += 1
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    result = self._extract_command(self.recv_buffer, b"PIR:WAKE")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        self.last_pir_state = 'AWAKE'
                        print("[PIR] Device woke up fully.")
                        _save_sleep_status(False)
                        log_sleep_event("WAKE")
                        self.end_sleep_session()
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    result = self._extract_command(self.recv_buffer, b"PIR:SLEEP")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if self.last_pir_state != 'SLEEPING':
                            self.last_pir_state = 'SLEEPING'
                            print("[PIR] Device went to sleep.")
                            log_sleep_event("SLEEP")
                            if self.sleep_start_time is None:
                                self.sleep_start_time = time.time()
                                self.sleep_movement_count = 0
                                self.sleep_noise_levels = []
                                self.sleep_noise_events = 0
                                self.sleep_ldr_levels = []
                                _save_sleep_status(True, self.sleep_start_time)
                                print(f"[Sleep Monitor] Session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    result = self._extract_command(self.recv_buffer, b"PIR:PREWAKE")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if self.last_pir_state != 'PREWAKE':
                            self.last_pir_state = 'PREWAKE'
                            print("[PIR] Device entered pre-wake standby.")
                            log_sleep_event("PREWAKE")
                            if self.sleep_start_time is not None:
                                self.sleep_movement_count += 1
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                
                tail = bytes(self.recv_buffer)
                partial_markers = [b"CMD:", b"___END___", b"LDR:", b"TIMER_DONE", b"PIR:"]
                safe_len = len(tail)
                for marker in partial_markers:
                    for prefix_len in range(1, len(marker)):
                        if tail.endswith(marker[:prefix_len]):
                            safe_len = min(safe_len, len(tail) - prefix_len)
                            break
                
                if safe_len > 0:
                    audio_data = bytes(self.recv_buffer[:safe_len])
                    self.recv_buffer = self.recv_buffer[safe_len:]
                    audio_chunks.append(audio_data)
                
                for chunk in audio_chunks:
                    if chunk:
                        self.keyword_buffer.extend(chunk)
                        
                        if self.last_pir_state in ('SLEEPING', 'PREWAKE'):
                            align_len = len(chunk) - (len(chunk) % 2)
                            if align_len >= 2:
                                samples = np.frombuffer(chunk[:align_len], dtype=np.int16)
                                if len(samples) > 0:
                                    rms = float(np.sqrt(np.mean(samples.astype(np.float64)**2)))
                                    self.sleep_noise_levels.append(rms)
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
            except ConnectionResetError: break
            except Exception as e:
                print(f"[Error] Connection loop error: {e}")
                break
                
        print(f"[-] Client {self.addr} disconnected")
        if active_conn == self.conn: active_conn = None
        if active_handler == self: active_handler = None
        self.end_sleep_session()
            
    def end_sleep_session(self):
        if self.sleep_start_time is not None:
            end_time = time.time()
            duration = end_time - self.sleep_start_time
            duration_hours = duration / 3600.0
            
            if duration < 600.0:
                print(f"[Sleep Monitor] Discarding short sleep session of {duration/60.0:.1f} minutes")
                self.sleep_start_time = None
                return
                
            session_type = "actual_sleep" if duration_hours >= 3.0 else "nap"
            display_type = "Sleep" if session_type == "actual_sleep" else "Nap"
            
            avg_noise = float(np.mean(self.sleep_noise_levels)) if self.sleep_noise_levels else 0.0
            max_noise = float(np.max(self.sleep_noise_levels)) if self.sleep_noise_levels else 0.0
            avg_ldr = float(np.mean(self.sleep_ldr_levels)) if self.sleep_ldr_levels else 150.0
            
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
            
            try:
                summary_cmd = f"UI_SLEEP_SUMMARY:{display_type}:{duration_hours:.1f}:{self.sleep_movement_count}:{avg_noise:.0f}:{avg_ldr:.0f}:{quality}\n"
                self.safe_send(summary_cmd.encode())
                print(f"[Sleep Monitor] Sent summary to ESP32: {summary_cmd.strip()}")
            except Exception as e:
                print(f"[Sleep Monitor] Failed to send sleep summary: {e}")
            
            file_path = "sleep_sessions.json"
            try:
                sessions = []
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f: sessions = json.load(f)
                    except Exception: sessions = []
                sessions.append(session_data)
                with open(file_path, "w", encoding="utf-8") as f: json.dump(sessions, f, indent=2)
                print(f"[Sleep Monitor] Saved session to {file_path}")
            except Exception as e:
                print(f"[Sleep Monitor Error] Failed to save session: {e}")
                
            self.sleep_start_time = None
            
    def process_speech(self, audio_bytes, total_duration):
        global active_alarm_active
        
        if len(audio_bytes) % 2 != 0: audio_bytes = audio_bytes[:-1]
        
        num_samples = len(audio_bytes) / 2
        if num_samples < 100:
            print(f"[!] Too few samples ({int(num_samples)}), skipping")
            try: self.safe_send(b"UI_STATE:IDLE\n")
            except Exception: pass
            return

        if self.first_audio_time > 0 and self.recording_start_time > 0:
            audio_duration = time.time() - self.first_audio_time
        else:
            audio_duration = total_duration

        if audio_duration < 0.1: audio_duration = total_duration

        measured_rate = int(num_samples / audio_duration) if audio_duration > 0 else 0
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[*] Audio Duration: {audio_duration:.2f}s, Rate: {measured_rate} Hz")

        try:
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
            if measured_rate > 0 and measured_rate != 16000 and len(audio_np) > 0:
                target_count = int(len(audio_np) * 16000 / measured_rate)
                src_idx = np.arange(len(audio_np))
                tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
                audio_np = np.interp(tgt_idx, src_idx, audio_np)
            audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
        except Exception as e:
            print(f"[Warning] Resample failed: {e}")
            audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            rec_path = os.path.join(RECORDINGS_DIR, f"rec_{ts}.wav")
            with wave.open(rec_path, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2)
                wf.setframerate(measured_rate if measured_rate > 0 else 16000)
                wf.writeframes(audio_bytes)
            print(f"[*] Saved recording: {rec_path}")
        except Exception as e:
            print(f"[Warning] Failed to save recording: {e}")

        try:
            segments, _ = asr_model.transcribe(audio_float, language="en", beam_size=1, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=100))
            text = " ".join([segment.text for segment in segments]).strip()
            
            if not text:
                print("[No readable speech transcribed]")
                try: self.safe_send(b"UI_STATE:IDLE\n")
                except Exception: pass
                return
                
            print(f"[{'AWAKE' if self.is_awake else 'SLEEPING'}] Heard: '{text}'")

            try:
                log_path = os.path.join(RECORDINGS_DIR, "transcriptions.log")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"{ts}\t{measured_rate}\t16000\t{audio_duration:.2f}\t{text}\n")
            except Exception: pass
            
            if self.timer_running:
                clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
                is_cancel = any(w in clean_text for w in ["cancel", "delete", "remove", "dismiss"]) or \
                            (any(w in clean_text for w in ["stop", "quit", "terminate", "shut up", "stop it"]) and "timer" in clean_text)
                is_pause = any(w in clean_text for w in ["pause", "hold"])
                is_resume = any(w in clean_text for w in ["resume", "continue", "start", "play"])

                if is_cancel:
                    self.timer_running = False
                    try: self.safe_send(b"TIMER_CANCEL\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer stopped.")
                elif is_pause:
                    try: self.safe_send(b"TIMER_PAUSE\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer paused.")
                elif is_resume:
                    try: self.safe_send(b"TIMER_RESUME\n")
                    except Exception: pass
                    play_speech_on_laptop("Timer resumed.")
                else:
                    play_speech_on_laptop("Countdown is active. Say stop timer to cancel.")
                
                self.is_awake = False
                return

            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            if active_alarm_active:
                print("[Alarm] Speech command processed while alarm active. Silencing server alarm.")
                stop_active_alarm()
                # If they explicitly said a stop word, dismiss local client timer/buzzer and return immediately
                if any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
                    try:
                        self.safe_send(b"TIMER_STOP\n")
                    except Exception:
                        pass
                    self.is_awake = False
                    self.safe_send(b"UI_STATE:IDLE\n")
                    return
            elif any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
                # If alarm is not active but they said stop, just cancel the focus timer
                try:
                    self.safe_send(b"TIMER_STOP\n")
                except Exception:
                    pass
                self.is_awake = False
                self.safe_send(b"UI_STATE:IDLE\n")
                return
            
            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            is_timer_query = any(w in clean_text for w in ["timer", "countdown", "focus"])
            is_stop_intent = any(w in clean_text for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])
            
            if is_timer_query and not is_stop_intent:
                duration = parse_timer_duration(clean_text)
                if duration is not None:
                    self.timer_running = True
                    try: self.safe_send(f"TIMER_START:{duration}\n".encode())
                    except Exception: pass
                    play_speech_on_laptop(f"Starting countdown for {format_duration(duration)}.")
                    self.is_awake = False
                else:
                    play_speech_on_laptop("Please specify seconds, minutes, or hours.")
                    self.is_awake = False
                    try: self.safe_send(b"UI_STATE:IDLE\n")
                    except Exception: pass
                return

            print(f"[*] Processing user prompt: '{text}'")
            self.safe_send(b"UI_STATE:THINKING\n")
            
            response = chat_session.send_message(text)
            ai_answer = response.text.strip()
            print(f"[*] AI Response: {ai_answer}")
            
            self.handle_llm_response(ai_answer)
            
            with chat_lock:
                while len(chat_session.history) > 6:
                    chat_session.history.pop(0)
                    
            self.is_awake = False
                
        except Exception as e:
            print(f"[Error] process_speech pipeline error: {e}")
            try: self.safe_send(b"UI_MSG:AI Error.\n")
            except Exception: pass
            self.is_awake = False
            
    def handle_llm_response(self, ai_answer):
        # Case-insensitive, space-tolerant, and bracket/brace-tolerant regexes for small local LLM hallucinations
        add_match = re.search(r'[\[{]\s*CMD\s*:\s*ADD_REMINDER\s*\|\s*([^|]+?)\s*\|\s*(ABS|REL|abs|rel)\s*\|\s*([^\]}]+?)\s*[\]}]', ai_answer, re.I)
        delete_match = re.search(r'[\[{]\s*CMD\s*:\s*DELETE_REMINDER\s*\|\s*(\d+)\s*[\]}]', ai_answer, re.I)
        list_match = re.search(r'[\[{]\s*CMD\s*:\s*LIST_REMINDERS\s*[\]}]', ai_answer, re.I) is not None
        clear_match = re.search(r'[\[{]\s*CMD\s*:\s*CLEAR_REMINDERS\s*[\]}]', ai_answer, re.I) is not None
        sleep_cmd_match = re.search(r'[\[{]\s*CMD\s*:\s*START_SLEEP\s*[\]}]', ai_answer, re.I) is not None

        # Strip ALL CMD-like tags (valid and malformed) plus emojis
        clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
        clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

        # If the model hallucinated a bogus tag with no valid command match,
        # treat the entire response as natural language
        if not any([add_match, delete_match, list_match, clear_match, sleep_cmd_match]):
            clean_answer = ai_answer.strip()
            clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', clean_answer, flags=re.I).strip()
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
                header = f"UI_MSG:{clean_answer}\n".encode()
                speak_on_esp32(self.conn, clean_answer, header=header)
                self.safe_send(b"CMD:START_SLEEP\n")
                self.last_pir_state = 'SLEEPING'
                self.sleep_start_time = time.time()
                self.sleep_movement_count = 0
                self.sleep_noise_levels = []
                self.sleep_noise_events = 0
                self.sleep_ldr_levels = []
                _save_sleep_status(True, self.sleep_start_time)
                print(f"[Sleep Monitor] Manual sleep session triggered via voice command.")
                
            else:
                print(f"[*] Clean response: '{clean_answer}'")
                header = f"UI_MSG:{clean_answer}\n".encode()
                speak_on_esp32(self.conn, clean_answer, header=header)
        except Exception as e:
            print(f"[Error] Failed to send socket command: {e}")

# --- UDP DISCOVERY BEACON (RESTORED) ---
def udp_discovery_beacon():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[Discovery] UDP beacon broadcaster running on port 9999...")
    while True:
        try:
            broadcasts = ['255.255.255.255']
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith("127."):
                    parts = ip.split('.')
                    if len(parts) == 4:
                        parts[3] = '255'
                        broadcasts.append('.'.join(parts))
            for bcast in set(broadcasts):
                try:
                    udp_sock.sendto(b"TABLE_BONDHU_BEACON", (bcast, 9999))
                except Exception: pass
        except Exception: pass
        time.sleep(2)

# --- REST API SERVER (RESTORED) ---
class CompanionRestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self): self._set_headers(200)

    def do_GET(self):
        if self.path == '/api/reminders':
            self._set_headers(200)
            self.wfile.write(json.dumps(get_reminders_list()).encode('utf-8'))
        elif self.path == '/api/ping':
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "OK"}).encode('utf-8'))
        elif self.path == '/api/sleep/schedule':
            self._set_headers(200)
            global scheduled_sleep_time
            self.wfile.write(json.dumps({"scheduled_time": scheduled_sleep_time or ""}).encode('utf-8'))
        elif self.path == '/api/sleep/status':
            self._set_headers(200)
            payload = {"is_sleeping": False, "start_time": None}
            if os.path.exists(sleep_status_file):
                try:
                    with open(sleep_status_file, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception:
                    pass
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        elif self.path == '/api/sleep/window':
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "start_hour": sleep_window_start,
                "end_hour": sleep_window_end
            }).encode('utf-8'))
        elif self.path == '/api/sleep':
            self._set_headers(200)
            sessions = []
            if os.path.exists("sleep_sessions.json"):
                try:
                    with open("sleep_sessions.json", "r", encoding="utf-8") as f: sessions = json.load(f)
                except Exception: pass
            self.wfile.write(json.dumps(sessions).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_POST(self):
        global active_conn, active_handler, chat_session, scheduled_sleep_time
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try: data = json.loads(post_data.decode('utf-8'))
        except Exception: data = {}

        if self.path == '/api/chat':
            message = data.get("message", "")
            if not message:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty message"}).encode('utf-8'))
                return

            print(f"[REST Chat] Message from app: '{message}'")
            if active_alarm_active:
                print("[Alarm] Message from app while alarm active. Silencing server alarm.")
                stop_active_alarm()

            clean_msg = re.sub(r'[^\w\s]', '', message.lower()).strip()
            is_timer_query = any(w in clean_msg for w in ["timer", "countdown", "focus"])
            is_stop_intent = any(w in clean_msg for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])

            if is_timer_query and not is_stop_intent:
                duration = parse_timer_duration(clean_msg)
                if duration is not None:
                    if active_handler:
                        active_handler.timer_running = True
                    if active_conn:
                        try: active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                        except Exception: pass
                    response_text = f"Starting focus countdown for {format_duration(duration)}."
                    play_speech_on_laptop(response_text)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"response": response_text}).encode('utf-8'))
                    return

            if active_handler:
                try: active_handler.safe_send(b"UI_STATE:THINKING\n")
                except Exception: pass

            try:
                response = chat_session.send_message(message)
                ai_answer = response.text.strip()
                print(f"[REST Chat] AI Response: {ai_answer}")

                if active_handler:
                    active_handler.handle_llm_response(ai_answer)
                else:
                    clean_answer = re.sub(r'[\[{]CMD:[^\]\}]+[\]\}]', '', ai_answer).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'[\[{]CMD:[^\]\}]+[\]\}]', '', ai_answer).strip()
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
            if active_alarm_active:
                print("[Alarm] Voice chat uploaded from app while alarm active. Silencing server alarm.")
                stop_active_alarm()
            try:
                import base64
                audio_bytes = base64.b64decode(audio_b64)
                temp_path = "temp_app_voice.wav"
                with open(temp_path, "wb") as f:
                    f.write(audio_bytes)

                # Load and resample using pydub
                sound = AudioSegment.from_file(temp_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio_np = np.frombuffer(sound.raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                segments, _ = asr_model.transcribe(audio_np, language="en", beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                print(f"[REST Voice Chat] Transcribed: '{text}'")

                if not text:
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"text": "", "response": "Could not recognize speech. Please try speaking clearer."}).encode('utf-8'))
                    return

                clean_msg = re.sub(r'[^\w\s]', '', text.lower()).strip()
                is_timer_query = any(w in clean_msg for w in ["timer", "countdown", "focus"])
                is_stop_intent = any(w in clean_msg for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])

                if is_timer_query and not is_stop_intent:
                    duration = parse_timer_duration(clean_msg)
                    if duration is not None:
                        if active_handler:
                            active_handler.timer_running = True
                        if active_conn:
                            try: active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                            except Exception: pass
                        response_text = f"Starting focus countdown for {format_duration(duration)}."
                        play_speech_on_laptop(response_text)
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"text": text, "response": response_text}).encode('utf-8'))
                        return

                if active_handler:
                    try: active_handler.safe_send(b"UI_STATE:THINKING\n")
                    except Exception: pass

                response = chat_session.send_message(text)
                ai_answer = response.text.strip()
                print(f"[REST Voice Chat] AI Response: {ai_answer}")

                if active_handler:
                    active_handler.handle_llm_response(ai_answer)
                else:
                    clean_answer = re.sub(r'[\[{]CMD:[^\]\}]+[\]\}]', '', ai_answer).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'[\[{]CMD:[^\]\}]+[\]\}]', '', ai_answer).strip()
                clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

                self._set_headers(200)
                self.wfile.write(json.dumps({"text": text, "response": clean_answer}).encode('utf-8'))
            except Exception as e:
                print(f"[REST Voice Error] {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/reminders':
            task = data.get("task", "")
            time_str = data.get("time", "")
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
            index = data.get("index")
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
                try: active_conn.sendall(f"TIMER_START:{duration}\n".encode())
                except Exception: pass
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        elif self.path == '/api/timer/cancel':
            if active_handler:
                active_handler.timer_running = False
            if active_conn:
                try: active_conn.sendall(b"TIMER_CANCEL\n")
                except Exception: pass
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        elif self.path == '/api/sleep/start':
            sleep_type = data.get("type", "sleep")
            print(f"[REST Sleep] Force sleep trigger from app: {sleep_type}")
            if active_handler:
                start_ts = time.time()
                active_handler.sleep_start_time = start_ts
                active_handler.sleep_movement_count = 0
                active_handler.sleep_noise_levels = []
                active_handler.sleep_noise_events = 0
                active_handler.sleep_ldr_levels = []
                active_handler.last_pir_state = 'SLEEPING'
                _save_sleep_status(True, start_ts)
                try: active_conn.sendall(b"CMD:START_SLEEP\n")
                except Exception: pass
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "ESP32 desk clock is not connected to the server right now."}).encode('utf-8'))

        elif self.path == '/api/sleep/wake':
            print("[REST Sleep] Manual wake-up triggered from app.")
            if active_handler:
                active_handler.last_pir_state = 'AWAKE'
                _save_sleep_status(False)
                session_data = None
                if active_handler.sleep_start_time is not None:
                    end_time = time.time()
                    duration = end_time - active_handler.sleep_start_time
                    duration_hours = duration / 3600.0
                    session_type = "actual_sleep" if duration_hours >= 3.0 else "nap"
                    if duration >= 600.0:
                        avg_noise = float(np.mean(active_handler.sleep_noise_levels)) if active_handler.sleep_noise_levels else 0.0
                        avg_ldr = float(np.mean(active_handler.sleep_ldr_levels)) if active_handler.sleep_ldr_levels else 150.0
                        movements_per_hour = active_handler.sleep_movement_count / max(duration_hours, 0.01)
                        if movements_per_hour <= 2.0 and avg_noise <= 300.0 and avg_ldr <= 500.0:
                            quality = "Good"
                        elif movements_per_hour > 5.0 or avg_noise > 600.0 or avg_ldr > 1200.0:
                            quality = "Poor"
                        else:
                            quality = "Fair"
                        session_data = {
                            "type": session_type,
                            "duration_hours": round(duration_hours, 2),
                            "movement_count": active_handler.sleep_movement_count,
                            "quality": quality,
                            "average_noise": round(avg_noise, 1),
                            "average_ldr": round(avg_ldr, 1),
                        }
                active_handler.end_sleep_session()
                try: active_conn.sendall(b"CMD:FORCE_WAKE\n")
                except Exception: pass
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "session": session_data}).encode('utf-8'))
            else:
                _save_sleep_status(False)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "session": None}).encode('utf-8'))

        elif self.path == '/api/sleep/schedule':
            time_val = data.get("time", "")
            scheduled_sleep_time = time_val
            print(f"[REST Sleep] Configured target bedtime to: {scheduled_sleep_time}")
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS", "scheduled_time": scheduled_sleep_time}).encode('utf-8'))

        elif self.path == '/api/sleep/window':
            global sleep_window_start, sleep_window_end
            start = data.get("start_hour", 22)
            end   = data.get("end_hour", 10)
            try:
                start = int(start)
                end   = int(end)
                if 0 <= start <= 23 and 0 <= end <= 23:
                    sleep_window_start = start
                    sleep_window_end = end
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"status": "SUCCESS", "start_hour": start, "end_hour": end}).encode('utf-8'))
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Hours must be 0-23"}).encode('utf-8'))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

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
        
        print(f"\n[*] Hands-free Companion Server running on {HOST}:{PORT}")
        print("[*] Waiting for ESP32 connection...")
        
        sched_thread = threading.Thread(target=alarm_scheduler, daemon=True)
        sched_thread.start()
        
        udp_thread = threading.Thread(target=udp_discovery_beacon, daemon=True)
        udp_thread.start()

        rest_thread = threading.Thread(target=run_rest_server, daemon=True)
        rest_thread.start()
        
        while True:
            conn, addr = s.accept()
            print(f"[*] ESP32 Connected: {addr}")
            handler = VoiceAgentHandler(conn, addr)
            client_thread = threading.Thread(target=handler.run, daemon=True)
            client_thread.start()

if __name__ == "__main__":
    if subprocess.run(["which", "espeak"], capture_output=True).returncode != 0:
        print("[!] WARNING: 'espeak' not found. Install via: sudo apt install espeak")
    start_server()
