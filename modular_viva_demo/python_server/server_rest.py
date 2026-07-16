# server_rest.py - REST HTTP Web Server

import json
import base64
import datetime
import time
import re
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
from pydub import AudioSegment

import config
import audio
import reminders
import sleep
import speech


class CompanionRestHandler(BaseHTTPRequestHandler):
    """Bridges client REST updates from the Flutter companion app to the server engines."""
    def log_message(self, format, *args):
        return  # Silence console logging to keep console logs clean

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
            self.wfile.write(json.dumps(reminders.get_reminders_list()).encode('utf-8'))
            
        elif self.path == '/api/ping':
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "OK"}).encode('utf-8'))
            
        elif self.path == '/api/sleep/schedule':
            self._set_headers(200)
            self.wfile.write(json.dumps({"scheduled_time": config.scheduled_sleep_time or ""}).encode('utf-8'))
            
        elif self.path == '/api/sleep/status':
            self._set_headers(200)
            payload = {"is_sleeping": False, "start_time": None}
            if os.path.exists(config.SLEEP_STATUS_FILE):
                try:
                    with open(config.SLEEP_STATUS_FILE, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception: pass
            self.wfile.write(json.dumps(payload).encode('utf-8'))
            
        elif self.path == '/api/sleep/window':
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "start_hour": config.sleep_window_start,
                "end_hour": config.sleep_window_end
            }).encode('utf-8'))
            
        elif self.path == '/api/sleep':
            self._set_headers(200)
            sessions = []
            if os.path.exists(config.SLEEP_SESSIONS_FILE):
                try:
                    with open(config.SLEEP_SESSIONS_FILE, "r", encoding="utf-8") as f:
                        sessions = json.load(f)
                except Exception: pass
            self.wfile.write(json.dumps(sessions).encode('utf-8'))
            
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception:
            data = {}

        # 1. Text Chat Endpoint
        if self.path == '/api/chat':
            message = data.get("message", "")
            if not message:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty message"}).encode('utf-8'))
                return

            print(f"[REST Chat] Prompt: '{message}'")
            if config.active_alarm_active:
                print("[Alarm] Message from app while alarm active. Silencing server alarm.")
                audio.stop_active_alarm()

            if config.active_handler:
                try: config.active_handler.safe_send(b"UI_STATE:THINKING\n")
                except Exception: pass

            try:
                response = config.chat_session.send_message(message)
                ai_answer = response.text.strip()
                print(f"[REST Chat] AI Reply: {ai_answer}")

                if config.active_handler:
                    speech.handle_llm_response(config.active_handler, ai_answer)
                else:
                    clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    audio.play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
                clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

                self._set_headers(200)
                self.wfile.write(json.dumps({"response": clean_answer}).encode('utf-8'))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        # 2. Voice Chat Upload Endpoint
        elif self.path == '/api/voice_chat':
            audio_b64 = data.get("audio", "")
            if not audio_b64:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Empty audio"}).encode('utf-8'))
                return

            print("[REST Voice Chat] Decoding voice recording...")
            if config.active_alarm_active:
                print("[Alarm] Voice chat uploaded from app while alarm active. Silencing server alarm.")
                audio.stop_active_alarm()
            try:
                audio_bytes = base64.b64decode(audio_b64)
                temp_path = "temp_app_voice.wav"
                with open(temp_path, "wb") as f:
                    f.write(audio_bytes)

                # Resample and normalize using pydub
                sound = AudioSegment.from_file(temp_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio_np = np.frombuffer(sound.raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                # Transcribe speech
                segments, _ = speech.asr_model.transcribe(audio_np, language="en", beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                print(f"[REST Voice Chat] Transcribed text: '{text}'")

                if not text:
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"text": "", "response": "Could not recognize speech."}).encode('utf-8'))
                    return

                if config.active_handler:
                    try: config.active_handler.safe_send(b"UI_STATE:THINKING\n")
                    except Exception: pass

                # Route to LLM Dialog
                response = config.chat_session.send_message(text)
                ai_answer = response.text.strip()
                print(f"[REST Voice Chat] AI Response: {ai_answer}")

                if config.active_handler:
                    speech.handle_llm_response(config.active_handler, ai_answer)
                else:
                    clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
                    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
                    audio.play_speech_on_laptop(clean_answer)

                clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
                clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

                self._set_headers(200)
                self.wfile.write(json.dumps({"text": text, "response": clean_answer}).encode('utf-8'))
            except Exception as e:
                print(f"[REST Voice Error] {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        # 3. Add Reminder Endpoint
        elif self.path == '/api/reminders':
            task = data.get("task", "")
            time_str = data.get("time", "")
            if not task or not time_str:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing parameters"}).encode('utf-8'))
                return
            try:
                trigger_dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                display_str = trigger_dt.strftime("%I:%M %p")
                reminders.add_reminder(task, trigger_dt, display_str)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        # 4. Delete Reminder Endpoint
        elif self.path == '/api/reminders/delete':
            index = data.get("index")
            if index is None:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing index"}).encode('utf-8'))
                return
            deleted_task = reminders.delete_reminder_by_index(index)
            if deleted_task:
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "deleted": deleted_task}).encode('utf-8'))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Index not found"}).encode('utf-8'))

        # 5. Clear Reminders Endpoint
        elif self.path == '/api/reminders/clear':
            reminders.clear_reminders()
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))

        # 6. Manual Sleep Start Endpoint
        elif self.path == '/api/sleep/start':
            sleep_type = data.get("type", "sleep")
            print(f"[REST Sleep] Force sleep start trigger: {sleep_type}")
            if config.active_handler:
                start_ts = time.time()
                config.active_handler.sleep_start_time = start_ts
                config.active_handler.sleep_movement_count = 0
                config.active_handler.sleep_noise_levels = []
                config.active_handler.sleep_noise_events = 0
                config.active_handler.sleep_ldr_levels = []
                config.active_handler.last_pir_state = 'SLEEPING'
                sleep.save_sleep_status(True, start_ts)
                try: config.active_conn.sendall(b"CMD:START_SLEEP\n")
                except Exception: pass
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS"}).encode('utf-8'))
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Desk clock offline."}).encode('utf-8'))

        # 7. Manual Sleep Wake Endpoint
        elif self.path == '/api/sleep/wake':
            print("[REST Sleep] Force wake-up trigger.")
            if config.active_handler:
                config.active_handler.last_pir_state = 'AWAKE'
                sleep.save_sleep_status(False)
                session_data = None
                if config.active_handler.sleep_start_time is not None:
                    end_time = time.time()
                    duration = end_time - config.active_handler.sleep_start_time
                    duration_hours = duration / 3600.0
                    session_type = "actual_sleep" if duration_hours >= 3.0 else "nap"
                    if duration >= 600.0:
                        avg_noise = float(np.mean(config.active_handler.sleep_noise_levels)) if config.active_handler.sleep_noise_levels else 0.0
                        avg_ldr = float(np.mean(config.active_handler.sleep_ldr_levels)) if config.active_handler.sleep_ldr_levels else 150.0
                        movements_per_hour = config.active_handler.sleep_movement_count / max(duration_hours, 0.01)
                        if movements_per_hour <= 2.0 and avg_noise <= 300.0 and avg_ldr <= 500.0:
                            quality = "Good"
                        elif movements_per_hour > 5.0 or avg_noise > 600.0 or avg_ldr > 1200.0:
                            quality = "Poor"
                        else:
                            quality = "Fair"
                        session_data = {
                            "type": session_type,
                            "duration_hours": round(duration_hours, 2),
                            "movement_count": config.active_handler.sleep_movement_count,
                            "quality": quality,
                            "average_noise": round(avg_noise, 1),
                            "average_ldr": round(avg_ldr, 1),
                        }
                config.active_handler.end_sleep_session()
                try: config.active_conn.sendall(b"CMD:FORCE_WAKE\n")
                except Exception: pass
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "session": session_data}).encode('utf-8'))
            else:
                sleep.save_sleep_status(False)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "SUCCESS", "session": None}).encode('utf-8'))

        # 8. Configure Sleep Schedule Endpoint
        elif self.path == '/api/sleep/schedule':
            time_val = data.get("time", "")
            config.scheduled_sleep_time = time_val
            print(f"[REST Sleep] Configured target bedtime: {config.scheduled_sleep_time}")
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "SUCCESS", "scheduled_time": config.scheduled_sleep_time}).encode('utf-8'))

        # 9. Configure Sleep Window Endpoint
        elif self.path == '/api/sleep/window':
            start = data.get("start_hour", 22)
            end = data.get("end_hour", 10)
            try:
                start = int(start)
                end = int(end)
                if 0 <= start <= 23 and 0 <= end <= 23:
                    config.sleep_window_start = start
                    config.sleep_window_end = end
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


import os # To resolve import scoping checks
