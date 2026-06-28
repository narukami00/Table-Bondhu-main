import socket
import wave
from faster_whisper import WhisperModel
import datetime
import os
import time
import threading  # <--- We are using this to handle the connections!
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080      
SAVE_FOLDER = "recordings"

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

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

print("Loading Whisper Model (this takes a moment)...")
whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

print("Initializing LLM (LM Studio)...")
chat_session = LocalChatSession(
    system_instruction="You are a voice assistant built into a tiny microcontroller named Table Bondhu build by Rafsan and Utsa. Your answers are displayed on a 160x128 pixel screen. You MUST be extremely concise. Keep every answer under 15 words. Do not use markdown formatting."
)

def process_audio_and_chat(filename, conn):
    try:
        # 1. Local Speech-to-Text using Whisper
        print("Transcribing audio locally using Whisper...")
        segments, info = whisper_model.transcribe(filename, beam_size=1, vad_filter=True)
        user_text = "".join([segment.text for segment in segments]).strip()
            
        print(f"\nYou asked: {user_text}")
        
        # 2. Gemini LLM (Local LM Studio)
        print("LLM is thinking...")
        response = chat_session.send_message(user_text)
        ai_answer = response.text.strip()
        print(f"AI answered: {ai_answer}")
        
        # Keep memory optimized (last 6 messages)
        while len(chat_session.history) > 6:
            chat_session.history.pop(0) 
            chat_session.history.pop(0)
            
        # 3. Send back to ESP32
        safe_answer = ai_answer.replace("\n", " ").replace("\r", "")
        conn.sendall(f"AI: {safe_answer}\n".encode())
        
    except Exception as e:
        print(f"Error in transcription or LLM pipeline: {e}")
        conn.sendall(b"System: AI Error.\n")

def handle_client(conn, addr):
    """This function runs in its own dedicated background thread."""
    print(f"\n[+] New connection accepted from {addr}")
    audio_buffer = bytearray()
    receiving_audio = False
    start_time = 0
    
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            
            # --- START BUTTON PRESSED ---
            if b"___START___" in data:
                print("\nRecording started...")
                receiving_audio = True
                start_time = time.time()
                audio_buffer = bytearray()
                parts = data.split(b"___START___")
                audio_buffer.extend(parts[-1])
                continue
                
            if receiving_audio:
                audio_buffer.extend(data)
                
                # --- END BUTTON RELEASED ---
                if b"___END___" in audio_buffer:
                    end_time = time.time()
                    duration = end_time - start_time
                    receiving_audio = False
                    
                    clean_audio = audio_buffer.split(b"___END___")[0]
                    
                    # Dynamic hardware stopwatch fix
                    total_samples = len(clean_audio) / 2
                    actual_framerate = int(total_samples / duration) if duration > 0 else 16000
                    
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = os.path.join(SAVE_FOLDER, f"audio_{timestamp}.wav")
                    
                    # Save the WAV file
                    with wave.open(filename, "wb") as wf:
                        wf.setnchannels(1)       
                        wf.setsampwidth(2)       
                        wf.setframerate(actual_framerate)
                        wf.writeframes(clean_audio)
                    
                    # Process the file
                    process_audio_and_chat(filename, conn)
                    
        except ConnectionResetError:
            break
        except Exception as e:
            print(f"Connection error: {e}")
            break
            
    print(f"[-] Client {addr} disconnected.")
    conn.close()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # This line prevents the "Address already in use" error if you restart the script quickly
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Push-to-Talk Server listening on {HOST}:{PORT}")
        print("Waiting for ESP32...")
        
        while True:
            # 1. Wait for the ESP32 to connect
            conn, addr = s.accept()
            
            # 2. As soon as it connects, launch a new thread just for this connection!
            client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            client_thread.start()

if __name__ == "__main__":
    start_server()