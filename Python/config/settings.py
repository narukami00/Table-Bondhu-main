"""
Configuration settings - loads from .env file
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- GEMINI API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

# --- Server Configuration ---
HOST = '0.0.0.0'
PORT = 8080
SAVE_FOLDER = "recordings"

# --- WiFi Configurations (for reference) ---
WIFI_CONFIG_1 = {
    "ssid": os.getenv("WIFI_SSID_1"),
    "password": os.getenv("WIFI_PASSWORD_1"),
    "server_ip": os.getenv("SERVER_IP_1")
}

WIFI_CONFIG_2 = {
    "ssid": os.getenv("WIFI_SSID_2"),
    "password": os.getenv("WIFI_PASSWORD_2"),
    "server_ip": os.getenv("SERVER_IP_2")
}

# --- Audio Configuration ---
AUDIO_SAMPLE_RATE = 46000
AUDIO_CHANNELS = 1
AUDIO_SAMPLE_WIDTH = 2
CHUNK_SECONDS = 2.5

# --- LLM Configuration ---
GEMINI_MODEL = "gemini-3.5-flash"
SYSTEM_INSTRUCTION = """You are a voice assistant built into a tiny microcontroller. 
Your answers are displayed on a 160x128 pixel screen. 
You MUST be extremely concise. Keep every answer under 15 words. 
Do not use markdown formatting."""

# --- Voice Recognition ---
GOOGLE_SPEECH_RECOGNIZER_LANGUAGE = "en-US"

# Create recordings folder if it doesn't exist
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
