# main.py - Core System Entry Point

import socket
import threading
import time
import datetime
from http.server import HTTPServer

import config
import audio
import reminders
import weather
import sleep
import server_tcp
import server_rest

# --- LLM SESSION MANAGEMENT ---
class LocalChatSession:
    """Manages chat session routing to LM Studio local server."""
    def __init__(self, system_instruction):
        self.system_instruction = system_instruction
        self.history = []

    def send_message(self, user_text):
        with config.chat_lock:
            self.history.append({"role": "user", "content": user_text})
            messages = []
            if self.system_instruction:
                now = datetime.datetime.now()
                time_ctx = now.strftime("%A, %d %B %Y %I:%M %p")
                
                # Dynamic Context Injector
                active_rems = reminders.get_reminders_list()
                rem_list_str = "\n".join([f"{i}. {r.get('task')} at {r.get('display_time')}" for i, r in enumerate(active_rems, 1)]) or "None"
                
                sys_prompt = (
                    f"{self.system_instruction}\n\n"
                    f"CONTEXT: Time={time_ctx}. Active Reminders: {rem_list_str}"
                )
                messages.append({"role": "system", "content": sys_prompt})
            messages.extend(self.history[-4:])
            
            try:
                # Direct API integration to LM Studio
                import requests
                url = "http://localhost:1234/v1/chat/completions"
                payload = {
                    "model": "qwen2.5-coder-1.5b-instruct",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 80
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    ai_answer = response.json()['choices'][0]['message']['content']
                else:
                    ai_answer = "Default response: System offline."
            except Exception as e:
                print(f"[LLM Error] Connection failed: {e}")
                ai_answer = "Connection failed. Please retry."
                
            self.history.append({"role": "assistant", "content": ai_answer})
        
        class ResponseObject:
            def __init__(self, text): self.text = text
        return ResponseObject(ai_answer)


# Initialize global chat session
config.chat_session = LocalChatSession(system_instruction=config.SYSTEM_INSTRUCTION)
sleep.load_sleep_status()


# --- BACKGROUND SERVICES ---

def alarm_scheduler():
    """Validates scheduled bedtime windows and scheduled alarms every 5 seconds."""
    print("[*] Alarm scheduler daemon active.")
    while True:
        try:
            now = datetime.datetime.now()
            
            # 1. Auto-dismiss alarm sound after 30 seconds
            if config.active_alarm_active and config.alarm_fired_at is not None:
                elapsed = (now - config.alarm_fired_at).total_seconds()
                if elapsed > 30:
                    print(f"[ALARM] Auto-dismissed after {int(elapsed)}s")
                    audio.stop_active_alarm()
                    if config.active_conn:
                        try:
                            with config.send_lock:
                                config.active_conn.sendall(b"UI_STATE:IDLE\n")
                        except Exception: pass
            
            # 2. Scheduled Sleep Bedtime check
            if config.scheduled_sleep_time:
                now_hm = now.strftime("%H:%M")
                if now_hm == config.scheduled_sleep_time:
                    if not config.scheduled_sleep_checked_today:
                        config.scheduled_sleep_checked_today = True
                        print(f"[Sleep Schedule] bedtime target {config.scheduled_sleep_time} reached.")
                        
                        if config.active_handler:
                            last_ldr = getattr(config.active_handler, 'last_ldr_val', 500)
                            last_motion = getattr(config.active_handler, 'last_motion_time', time.time())
                            time_since_motion = time.time() - last_motion
                            
                            # Bedtime gating verification
                            if last_ldr < 200 and time_since_motion >= 300:
                                print("[Sleep Schedule] Gating matched. Setting auto-sleep state.")
                                config.active_handler.sleep_start_time = time.time()
                                config.active_handler.sleep_movement_count = 0
                                config.active_handler.sleep_noise_levels = []
                                config.active_handler.sleep_noise_events = 0
                                config.active_handler.sleep_ldr_levels = [last_ldr]
                                config.active_handler.last_pir_state = 'SLEEPING'
                                sleep.save_sleep_status(True, config.active_handler.sleep_start_time)
                                try:
                                    config.active_conn.sendall(b"CMD:START_SLEEP\n")
                                except Exception: pass

            # 3. Check reminders list
            pending_alarms = []
            with config.db_lock:
                reminders_list = reminders._load_reminders_internal()
                updated = False
                for r in reminders_list:
                    if r.get("fired", False): continue
                    trigger_str = r.get("trigger_time", "")
                    if not trigger_str: continue
                    try:
                        trigger_dt = datetime.datetime.fromisoformat(trigger_str)
                    except ValueError: continue
                    if now >= trigger_dt:
                        r["fired"] = True
                        updated = True
                        config.active_alarm_active = True
                        config.active_alarm_name = r.get("task", "Alarm")
                        config.alarm_fired_at = now
                        pending_alarms.append(r.get("display_time", trigger_str))
                        
                if updated:
                    reminders._save_reminders_internal(reminders_list)
            
            # Trigger audio loop for pending alarms
            for display in pending_alarms:
                print(f"\n[ALARM] Fired! Task: {config.active_alarm_name}")
                audio.play_alarm_sound()
                if config.active_conn:
                    try:
                        with config.send_lock:
                            config.active_conn.sendall(f"UI_ALARM:{config.active_alarm_name}\n".encode())
                    except Exception as e:
                        print(f"[Alarm Error] Failed to write UI_ALARM: {e}")
                        
        except Exception as e:
            print(f"[Scheduler Error] Run failed: {e}")
            
        time.sleep(5)


def udp_discovery_beacon():
    """Broadcasts UDP beacon packets every 5 seconds to help app automatically bind to server."""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[Discovery] UDP beacon thread running on port 9999...")
    while True:
        try:
            broadcasts = ['255.255.255.255']
            # Find all broadcast interfaces
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith("127."):
                    parts = ip.split('.')
                    if len(parts) == 4:
                        parts[3] = '255'
                        broadcasts.append('.'.join(parts))
            for bcast in set(broadcasts):
                try:
                    udp_sock.sendto(f"TABLE_BONDHU_SERVER:{socket.gethostbyname(socket.gethostname())}".encode(), (bcast, config.UDP_PORT))
                except Exception: pass
        except Exception: pass
        time.sleep(5)


def run_rest_server():
    """Starts REST HTTP server."""
    server_address = ('', config.REST_PORT)
    httpd = HTTPServer(server_address, server_rest.CompanionRestHandler)
    print(f"[REST API] Server running on port {config.REST_PORT}...")
    httpd.serve_forever()


def start_server():
    """Main TCP listener bootloader."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((config.HOST, config.PORT))
        s.listen()
        
        print(f"\n[+] Hands-Free Companion Server started on {config.HOST}:{config.PORT}")
        print("[+] Ready. Waiting for client (ESP32) connection...")
        
        # Start secondary service threads
        threading.Thread(target=alarm_scheduler, daemon=True).start()
        threading.Thread(target=udp_discovery_beacon, daemon=True).start()
        threading.Thread(target=run_rest_server, daemon=True).start()
        
        while True:
            conn, addr = s.accept()
            print(f"[*] Connection accepted from: {addr}")
            handler = server_tcp.VoiceAgentHandler(conn, addr)
            threading.Thread(target=handler.run, daemon=True).start()


if __name__ == "__main__":
    start_server()
