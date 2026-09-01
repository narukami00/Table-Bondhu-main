# speech.py - Speech Recognition & LLM Dialog Manager

import os
import re
import wave
import time
import datetime
import numpy as np
from pydub import AudioSegment
from faster_whisper import WhisperModel

import config
import audio
import reminders
import sleep

# Load Speech-to-Text translation engine
print("[*] Loading Faster-Whisper ASR Engine...")
asr_model = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=4)
print("[+] ASR Engine active.")


def process_speech(handler, audio_bytes, total_duration):
    """Processes incoming raw voice byte chunks from ESP32 client."""
    # Ensure audio length is multiple of 2 (16-bit)
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]
        
    num_samples = len(audio_bytes) / 2
    if num_samples < 100:
        print("[!] Too few audio samples, skipping translation.")
        try:
            handler.safe_send(b"UI_STATE:IDLE\n")
        except Exception:
            pass
        return

    # Calculate actual duration of recording
    if handler.first_audio_time > 0 and handler.recording_start_time > 0:
        audio_duration = time.time() - handler.first_audio_time
    else:
        audio_duration = total_duration
    if audio_duration < 0.1:
        audio_duration = total_duration

    measured_rate = int(num_samples / audio_duration) if audio_duration > 0 else 0
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[*] Voice Segment: {audio_duration:.2f}s, Measured Rate: {measured_rate} Hz")

    # Resample audio to 16kHz float32 for Whisper model input
    try:
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float64)
        if measured_rate > 0 and measured_rate != 16000 and len(audio_np) > 0:
            target_count = int(len(audio_np) * 16000 / measured_rate)
            src_idx = np.arange(len(audio_np))
            tgt_idx = np.linspace(0, len(audio_np) - 1, target_count)
            audio_np = np.interp(tgt_idx, src_idx, audio_np)
        audio_float = (audio_np.astype(np.float32) / 32768.0).astype(np.float32)
    except Exception as e:
        print(f"[ASR Error] Resampling failed: {e}")
        audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    # Save copy of wave audio for debugging
    try:
        rec_path = os.path.join(config.RECORDINGS_DIR, f"rec_{ts}.wav")
        with wave.open(rec_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(measured_rate if measured_rate > 0 else 16000)
            wf.writeframes(audio_bytes)
    except Exception as e:
        print(f"[ASR Warning] Debug wave file write failed: {e}")

    # Run Speech-to-Text Transcription via WhisperModel
    try:
        segments, _ = asr_model.transcribe(
            audio_float, 
            language="en", 
            beam_size=1, 
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=100)
        )
        text = " ".join([segment.text for segment in segments]).strip()
        
        if not text:
            print("[ASR] No speech detected in audio stream.")
            try:
                handler.safe_send(b"UI_STATE:IDLE\n")
            except Exception:
                pass
            return
            
        print(f"[ASR Transcription] Heard: '{text}'")

        # Log transcription text
        try:
            log_path = os.path.join(config.RECORDINGS_DIR, "transcriptions.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts}\t{measured_rate}\t16000\t{audio_duration:.2f}\t{text}\n")
        except Exception:
            pass
        
        # --- ALARM DISMISSAL CHECK ---
        clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
        if config.active_alarm_active:
            print("[Alarm] Speech command processed while alarm active. Silencing server alarm.")
            audio.stop_active_alarm()
            if any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
                try:
                    handler.safe_send(b"TIMER_STOP\n")
                except Exception:
                    pass
                handler.is_awake = False
                handler.safe_send(b"UI_STATE:IDLE\n")
                return
        elif any(word in clean_text for word in ["stop", "dismiss", "cancel", "shut up", "turn off", "stop it", "quit"]):
            try:
                handler.safe_send(b"TIMER_STOP\n")
            except Exception:
                pass
            handler.is_awake = False
            handler.safe_send(b"UI_STATE:IDLE\n")
            return

        # --- TIMER COMMAND HANDLER ---
        is_timer_query = any(w in clean_text for w in ["timer", "countdown", "focus"])
        is_stop_intent = any(w in clean_text for w in ["stop", "cancel", "quit", "dismiss", "terminate", "shut up", "stop it"])
        
        if is_timer_query and not is_stop_intent:
            duration = reminders.parse_timer_duration(clean_text) # (Note: imported or implemented)
            if duration is not None:
                handler.timer_running = True
                try:
                    handler.safe_send(f"TIMER_START:{duration}\n".encode())
                except Exception:
                    pass
                audio.play_speech_on_laptop(f"Starting countdown for {reminders.format_duration(duration)}.")
                handler.is_awake = False
            else:
                audio.play_speech_on_laptop("Please specify seconds, minutes, or hours.")
                handler.is_awake = False
                try:
                    handler.safe_send(b"UI_STATE:IDLE\n")
                except Exception:
                    pass
            return

        # --- ROUTE TO LLM DIALOG MANAGER ---
        print(f"[LLM Core] Routing prompt to Ollama session: '{text}'")
        handler.safe_send(b"UI_STATE:THINKING\n")
        
        response = config.chat_session.send_message(text)
        ai_answer = response.text.strip()
        print(f"[LLM Core] AI Response: {ai_answer}")
        
        # Execute action tags
        handle_llm_response(handler, ai_answer)
        
        # Keep chat history size constrained
        with config.chat_lock:
            while len(config.chat_session.history) > 6:
                config.chat_session.history.pop(0)
                
        handler.is_awake = False
            
    except Exception as e:
        print(f"[Speech Error] Pipeline processing crashed: {e}")
        try:
            handler.safe_send(b"UI_MSG:AI Error.\n")
        except Exception:
            pass
        handler.is_awake = False


def handle_llm_response(handler, ai_answer):
    """Parses bracketed command tags out of the LLM responses to trigger system events."""
    # Robust case-insensitive tag extraction regex
    add_match = re.search(r'[\[{]\s*CMD\s*:\s*ADD_REMINDER\s*\|\s*([^|]+?)\s*\|\s*(ABS|REL|abs|rel)\s*\|\s*([^\]}]+?)\s*[\]}]', ai_answer, re.I)
    delete_match = re.search(r'[\[{]\s*CMD\s*:\s*DELETE_REMINDER\s*\|\s*(\d+)\s*[\]}]', ai_answer, re.I)
    list_match = re.search(r'[\[{]\s*CMD\s*:\s*LIST_REMINDERS\s*[\]}]', ai_answer, re.I) is not None
    clear_match = re.search(r'[\[{]\s*CMD\s*:\s*CLEAR_REMINDERS\s*[\]}]', ai_answer, re.I) is not None
    sleep_cmd_match = re.search(r'[\[{]\s*CMD\s*:\s*START_SLEEP\s*[\]}]', ai_answer, re.I) is not None

    # Strip tags to get clean display/speech text
    clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', ai_answer, flags=re.I).strip()
    clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()

    if not any([add_match, delete_match, list_match, clear_match, sleep_cmd_match]):
        clean_answer = ai_answer.strip()
        clean_answer = re.sub(r'[\[{]\s*CMD\s*:[^\]\}]+[\]\}]', '', clean_answer, flags=re.I).strip()
        clean_answer = re.sub(r'[\U00010000-\U0010ffff]', '', clean_answer).strip()
    
    try:
        if add_match:
            task = add_match.group(1).strip()
            time_type = add_match.group(2).strip().upper()
            time_value = add_match.group(3).strip()
            
            if time_type == "REL":
                trigger_dt, display_str = reminders.parse_relative_time(time_value)
            else:
                trigger_dt, display_str = reminders.parse_absolute_time(time_value)
            
            if trigger_dt:
                reminders.add_reminder(task, trigger_dt, display_str)
                handler.safe_send(f"UI_MSG:{clean_answer}\n".encode())
            else:
                handler.safe_send(b"UI_MSG:Invalid time format.\n")
            
        elif delete_match:
            index = int(delete_match.group(1).strip())
            deleted_task = reminders.delete_reminder_by_index(index)
            if deleted_task:
                header = f"UI_MSG:{clean_answer}\n".encode()
                audio.speak_on_esp32(handler.conn, clean_answer, header=header)
            else:
                msg = "Reminder index not found."
                header = f"UI_MSG:{msg}\n".encode()
                audio.speak_on_esp32(handler.conn, msg, header=header)
                
        elif list_match:
            # Let server_tcp module handle lists via helper method
            handler.send_reminder_list()
                
        elif clear_match:
            reminders.clear_reminders()
            handler.safe_send(f"UI_MSG:{clean_answer}\n".encode())
            
        elif sleep_cmd_match:
            header = f"UI_MSG:{clean_answer}\n".encode()
            audio.speak_on_esp32(handler.conn, clean_answer, header=header)
            handler.safe_send(b"CMD:START_SLEEP\n")
            handler.last_pir_state = 'SLEEPING'
            handler.sleep_start_time = time.time()
            handler.sleep_movement_count = 0
            handler.sleep_noise_levels = []
            handler.sleep_noise_events = 0
            handler.sleep_ldr_levels = []
            sleep.save_sleep_status(True, handler.sleep_start_time)
            print("[Sleep Monitor] Voice Command sleep session started.")
            
        else:
            print(f"[*] AI Response text output: '{clean_answer}'")
            header = f"UI_MSG:{clean_answer}\n".encode()
            audio.speak_on_esp32(handler.conn, clean_answer, header=header)
            
    except Exception as e:
        print(f"[Speech Error] Failed to execute tag command action: {e}")
