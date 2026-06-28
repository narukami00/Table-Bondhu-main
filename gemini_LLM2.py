import socket
import numpy as np
from faster_whisper import WhisperModel
import threading
import queue
import time
import wave
import os
import re
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080
CHUNK_SECONDS = 2.5
AWAKE_DURATION = 8

# The exact words that will wake the assistant
WAKE_PHRASES = ["hey", "okay"] 

# Configure the LLM (LM Studio Local Endpoint)
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "google/gemma-4-e4b"

class LocalChatSession:
    def __init__(self, system_instruction):
        self.system_instruction = system_instruction
        self.history = []

    def send_message(self, user_text):
        self.history.append({"role": "user", "content": user_text})
        messages = []
        if self.system_instruction:
            messages.append({"role": "system", "content": self.system_instruction})
        messages.extend(self.history)
        
        data = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7
        }
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            ai_answer = res["choices"][0]["message"]["content"]
            
        self.history.append({"role": "assistant", "content": ai_answer})
        
        class ResponseObject:
            def __init__(self, text):
                self.text = text
        return ResponseObject(ai_answer)

print("Loading Whisper Model...")
whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

print("Initializing LLM (LM Studio)...")
chat_session = LocalChatSession(
    system_instruction="You are a voice assistant built into a tiny microcontroller. Your answers are displayed on a 160x128 pixel screen. You MUST be extremely concise. Keep every answer under 15 words. Do not use markdown formatting."
)
print("Systems Online! Waiting for ESP32...")

def transcription_worker(conn, audio_queue):
    is_awake = False
    awake_time = 0
    
    while True:
        item = audio_queue.get()
        if item is None:
            break
            
        audio_bytes, actual_framerate = item
        temp_file = "temp_live.wav"
        
        with wave.open(temp_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(actual_framerate) # Applies the dynamic hardware fix
            wf.writeframes(audio_bytes)
            
        try:
            # 1. Transcribe the audio
            segments, info = whisper_model.transcribe(temp_file, beam_size=1, vad_filter=True)
            user_text = "".join([segment.text for segment in segments]).strip()
            
            if user_text:
                # Clean the text (remove punctuation, make lowercase)
                clean_text = re.sub(r'[^\w\s]', '', user_text.lower())
                
                # Timeout logic: Go back to sleep if 8 seconds pass without a question
                if is_awake and (time.time() - awake_time > AWAKE_DURATION):
                    is_awake = False
                    print("[System went back to sleep]")
                
                # --- WAKE WORD DETECTION ---
                detected_phrase = None
                for phrase in WAKE_PHRASES:
                    # Check for exact word or word + space to prevent false positives (like "heyday")
                    if clean_text == phrase or clean_text.startswith(phrase + " "):
                        detected_phrase = phrase
                        break
                
                if detected_phrase:
                    is_awake = True
                    awake_time = time.time()
                    print(f"\n*** WAKE PHRASE DETECTED: '{detected_phrase}' ***")
                    
                    # Extract the actual question
                    parts = clean_text.split(detected_phrase, 1)
                    question = parts[1].strip()
                    
                    if not question:
                        # User only said "Hey", tell the ESP32 screen we are listening
                        conn.sendall(b"System: Listening...\n")
                        audio_queue.task_done()
                        continue
                    else:
                        # User asked the question immediately
                        user_text = question 
                
                # --- LLM PROCESSING ---
                if is_awake:
                    print(f"You asked: {user_text}")
                    print("LLM is thinking...")
                    
                    response = chat_session.send_message(user_text)
                    ai_answer = response.text.strip()
                    
                    print(f"AI answered: {ai_answer}")
                    
                    # Sliding Window: Prevent token bloat (Keep only last 6 messages)
                    while len(chat_session.history) > 6:
                        chat_session.history.pop(0) 
                        chat_session.history.pop(0)
                    
                    # Send safe, single-line string to ESP32
                    safe_answer = ai_answer.replace("\n", " ").replace("\r", "")
                    conn.sendall(f"AI: {safe_answer}\n".encode())
                    
                    # Go back to sleep immediately after answering
                    is_awake = False 
                else:
                    # Ignore background chatter
                    print(f"[Ignored background chatter: {user_text}]")
                
        except Exception as e:
            print(f"Error in AI Pipeline: {e}")
        
        audio_queue.task_done()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr} - Streaming Live...")
                
                audio_queue = queue.Queue()
                ai_thread = threading.Thread(target=transcription_worker, args=(conn, audio_queue), daemon=True)
                ai_thread.start()
                
                audio_buffer = bytearray()
                start_time = time.time()
                
                while True:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            break
                        
                        audio_buffer.extend(data)
                        current_time = time.time()
                        elapsed = current_time - start_time
                        
                        # Process audio strictly in 2.5-second chunks
                        if elapsed >= CHUNK_SECONDS:
                            total_samples = len(audio_buffer) / 2
                            actual_framerate = int(total_samples / elapsed)
                            audio_queue.put((audio_buffer, actual_framerate))
                            
                            audio_buffer = bytearray()
                            start_time = time.time()
                            
                    except ConnectionResetError:
                        break
                
                print("Client disconnected.")
                audio_queue.put(None)

if __name__ == "__main__":
    start_server()