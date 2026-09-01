# config.py - System Configurations & Global States

import os
import threading
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- NETWORK CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080
REST_PORT = 8888
UDP_PORT = 9999

# --- FILE PATHS ---
REMINDERS_FILE = "reminders.json"
SLEEP_STATUS_FILE = "sleep_status.json"
SLEEP_SESSIONS_FILE = "sleep_sessions.json"
RECORDINGS_DIR = "recordings_analysis"

if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

# --- THREAD LOCKS & GLOBAL BOUND OBJECTS ---
send_lock = threading.Lock()      # Prevents concurrent socket writes
db_lock = threading.Lock()        # Thread-safety for reminders database operations
chat_lock = threading.Lock()      # Thread-safety for LLM chat history manipulations

active_conn = None                # Active TCP socket connection to ESP32
active_handler = None             # Reference to the running VoiceAgentHandler thread
active_audio_process = None       # Process reference for the laptop speaker alarm audio player
loop_alarm_active = False         # Boolean controlling the alarm looping sound thread

# --- ALARM STATES ---
active_alarm_active = False       # True when an alarm is actively firing
active_alarm_name = ""            # Name/task of the triggered alarm
alarm_fired_at = None             # Timestamp of when the alarm started buzzing

# --- SLEEP CONTROLLER CONFIGS ---
is_sleeping = False
scheduled_sleep_time = None       # Configured bedtime (e.g. "23:00")
scheduled_sleep_checked_today = False

sleep_window_start = 22           # 10 PM (Start of bedtime window)
sleep_window_end = 10             # 10 AM (End of bedtime window)

# --- LLM SYSTEM INSTRUCTION (Core behavior parameters) ---
SYSTEM_INSTRUCTION = """You are Table-Bondhu, a helpful, cute offline desk assistant.
Your answers are displayed on a small ST7735 screen.
RULES:
1. Keep every answer under 15 words.
2. NO markdown formatting. NO emojis.
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
