# server_tcp.py - Multithreaded TCP Connection Handler

import socket
import threading
import time
import datetime
import re
import numpy as np

import config
import audio
import reminders
import weather
import sleep
import speech

class VoiceAgentHandler:
    """Manages raw TCP data framing, command extraction, and keyword spotter loops for a connected client."""
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
        self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.timer_running = False
        self.last_pir_state = 'AWAKE'
        self.last_ldr_val = 500
        self.last_motion_time = time.time()
        
        # Sleep monitoring buffers
        self.sleep_start_time = None
        self.sleep_movement_count = 0
        self.sleep_noise_levels = []
        self.sleep_noise_events = 0
        self.sleep_ldr_levels = []

    def calibrate(self):
        """Measures room noise floor over 1.0s to dynamically compute threshold."""
        print(f"[*] Calibrating noise baseline for {self.addr}...")
        self.conn.setblocking(False)
        try:
            while True:
                if not self.conn.recv(16384): break
        except (BlockingIOError, Exception):
            pass
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
            except Exception:
                break
            
        if calibration_rms:
            self.noise_floor = np.mean(calibration_rms)
            self.rms_threshold = max(self.noise_floor * 1.55, 450)
            print(f"[*] Calibration complete. Noise Floor: {self.noise_floor:.1f}, Threshold: {self.rms_threshold:.1f}")
        else:
            print("[!] Calibration failed. Using defaults.")

    def safe_send(self, data):
        """Thread-safe socket write."""
        with config.send_lock:
            try:
                self.conn.sendall(data)
            except Exception as e:
                print(f"[Socket Error] safe_send failed: {e}")

    def keyword_detection_loop(self):
        """Background thread executing fast, offline keyword checks on ambient audio."""
        while True:
            time.sleep(0.5)
            if self.is_awake or self.timer_running:
                continue
            if time.time() < audio.keyword_suppress_until:
                self.keyword_buffer = bytearray()
                self.keyword_chunk_start = time.time()
                continue
                
            elapsed = time.time() - self.keyword_chunk_start
            should_process = elapsed >= config.KEYWORD_CHUNK_SECONDS
            if not should_process and elapsed >= 0.5 and len(self.keyword_buffer) >= 1600:
                tail = self.keyword_buffer[-1600:]
                tail_samples = np.frombuffer(bytes(tail), dtype=np.int16)
                if len(tail_samples) > 0:
                    rms = float(np.sqrt(np.mean(tail_samples.astype(np.float64)**2)))
                    if rms < 150:  # Silence detected at tail
                        should_process = True
                        
            if not should_process:
                continue
            if len(self.keyword_buffer) < 800:
                self.keyword_buffer = bytearray()
                self.keyword_chunk_start = time.time()
                continue

            chunk = bytes(self.keyword_buffer)
            self.keyword_buffer = bytearray()
            self.keyword_chunk_start = time.time()

            num_samples = len(chunk) / 2
            measured_rate = int(num_samples / config.KEYWORD_CHUNK_SECONDS) if config.KEYWORD_CHUNK_SECONDS > 0 else 0
            if measured_rate < 1000:
                continue

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

            try:
                # Transcribe bypassing language detection pass to save resource load
                segments, info = speech.asr_model.transcribe(audio_float, language="en", beam_size=1, vad_filter=False)
                text = " ".join([segment.text for segment in segments]).strip()
            except Exception:
                continue
            if not text:
                continue

            clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
            print(f"[KEYWORD Engine] Heard: '{text}'")

            if time.time() - self.last_keyword_trigger < config.KEYWORD_DEBOUNCE_SECONDS:
                continue

            # Check if user said simple wake word
            greeting_words = ["hi", "hello", "hey", "yo"]
            if any(w in clean_text.split() for w in greeting_words):
                self.last_keyword_trigger = time.time()
                self.play_greeting()
                continue

    def play_greeting(self):
        try:
            self.safe_send(b"UI_STATE:GREETING\n")
            audio.play_speech_on_laptop("Hello! I am Table Bondhu. How can I help you today?")
        except Exception as e:
            print(f"[TCP Error] Failed to trigger greeting: {e}")

    def send_reminder_list(self):
        """Sends active reminders list back to ESP32 clock display."""
        active = reminders.get_reminders_list()
        try:
            if active:
                formatted_items = []
                for idx, r in enumerate(active, 1):
                    formatted_items.append(f"{idx}. {r['task']} @ {r.get('display_time', '?')}")
                items_str = "|".join(formatted_items)
                self.safe_send(f"UI_LIST:{items_str}\n".encode())
            else:
                self.safe_send(b"UI_MSG:No active reminders.\n")
        except Exception as e:
            print(f"[TCP Error] Failed to write UI_LIST: {e}")

    def weather_updater(self):
        """Periodic background weather updater loop."""
        while True:
            time.sleep(1800)  # Check every 30 minutes
            if config.active_conn == self.conn:
                weather.fetch_and_send_weather(self.conn)
            else:
                break

    def _extract_command(self, buf, marker):
        """Identifies text command frames embedded in raw binary audio stream."""
        pos = buf.find(marker)
        if pos < 0: return None
        nl_pos = buf.find(b"\n", pos)
        if nl_pos < 0: return None
        before = buf[:pos]
        cmd = buf[pos:nl_pos].decode('utf-8', errors='ignore').strip()
        after = buf[nl_pos+1:]
        return (before, cmd, after)

    def run(self):
        """Primary TCP handler thread loop."""
        global active_conn, active_handler, active_alarm_active, active_alarm_name, alarm_fired_at
        config.active_conn = self.conn
        config.active_handler = self
        
        self.calibrate()
        
        # Start background helper threads
        threading.Thread(target=self.keyword_detection_loop, daemon=True).start()
        threading.Thread(target=self.weather_updater, daemon=True).start()
        
        # Fetch weather conditions immediately
        weather.fetch_and_send_weather(self.conn)
        self.conn.settimeout(30)
        
        try:
            self.safe_send(b"UI_STATE:IDLE\n")
        except Exception as e:
            print(f"[TCP Error] Initial write failed: {e}")
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
                    
                    # 1. Check for physical WOKE button
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
                            print("\n[*] Physical button pressed: recording started...")
                            if config.active_alarm_active:
                                print("[Alarm] Physical button pressed. Silencing server alarm.")
                                audio.stop_active_alarm()
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # 2. Check for button release ___END___
                    result = self._extract_command(self.recv_buffer, b"___END___")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if self.is_awake:
                            print("[*] Physical button released: recording stopped")
                            duration = time.time() - self.recording_start_time
                            speech.process_speech(self, self.speech_buffer, duration)
                            self.speech_buffer = bytearray()
                            self.is_awake = False
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # 3. Parse LDR reading
                    result = self._extract_command(self.recv_buffer, b"LDR:")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        try:
                            ldr_value = int(cmd.split(":")[1])
                            self.last_ldr_val = ldr_value
                            if self.sleep_start_time is not None:
                                self.sleep_ldr_levels.append(ldr_value)
                        except Exception: pass
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # 4. Timer Completed Alarm event
                    result = self._extract_command(self.recv_buffer, b"TIMER_DONE")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        self.timer_running = False
                        print("[TIMER] Countdown completed on ESP32 client.")
                        
                        config.active_alarm_active = True
                        config.active_alarm_name = "Timer Finished"
                        config.alarm_fired_at = datetime.datetime.now()
                        audio.play_alarm_sound()
                        
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                    
                    # 5. PIR motion events
                    result = self._extract_command(self.recv_buffer, b"PIR:MOTION")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        self.last_motion_time = time.time()
                        if self.sleep_start_time is not None:
                            self.sleep_movement_count += 1
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    # 6. Sleep State transitions
                    result = self._extract_command(self.recv_buffer, b"PIR:SLEEP")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        if self.last_pir_state != 'SLEEPING':
                            self.last_pir_state = 'SLEEPING'
                            sleep.log_sleep_event("SLEEP")
                            if self.sleep_start_time is None:
                                self.sleep_start_time = time.time()
                                self.sleep_movement_count = 0
                                self.sleep_noise_levels = []
                                self.sleep_noise_events = 0
                                self.sleep_ldr_levels = []
                                sleep.save_sleep_status(True, self.sleep_start_time)
                                print(f"[Sleep Monitor] Auto-sleep started at {datetime.datetime.now()}")
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue

                    # 7. Wake State transitions
                    result = self._extract_command(self.recv_buffer, b"PIR:WAKE")
                    if result:
                        before, cmd, after = result
                        if before: audio_chunks.append(bytes(before))
                        self.last_pir_state = 'AWAKE'
                        sleep.save_sleep_status(False)
                        sleep.log_sleep_event("WAKE")
                        sleep.process_sleep_session_end(self)
                        self.recv_buffer = bytearray(after)
                        processing = True
                        continue
                        
                # Split remaining audio chunks to buffers
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
                        
                        # Compute noise volume during sleep for quality analysis
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
                print(f"[Timeout] Disconnecting {self.addr} (30s inactivity).")
                break
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"[TCP Error] Loop crashed: {e}")
                break
                
        print(f"[-] Client {self.addr} session closed.")
        if config.active_conn == self.conn: config.active_conn = None
        if config.active_handler == self: config.active_handler = None
        sleep.process_sleep_session_end(self)
