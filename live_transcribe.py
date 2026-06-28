import socket
import numpy as np
from faster_whisper import WhisperModel
import threading
import queue
import time
import wave
import os

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080
CHUNK_SECONDS = 2.5  # Process audio in 2.5-second chunks

print("Loading Whisper Model (this takes a moment)...")
model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
print("Model loaded successfully!")

def transcription_worker(conn, audio_queue):
    """Background thread that runs the AI model."""
    while True:
        item = audio_queue.get()
        if item is None: # Stop signal
            break
            
        audio_bytes, actual_framerate = item
        
        # Save to a temporary WAV file so Whisper can auto-resample the pitch
        temp_file = "temp_live.wav"
        with wave.open(temp_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(actual_framerate) # Apply the dynamic hardware fix
            wf.writeframes(audio_bytes)
            
        try:
            # Whisper reads the WAV, sees the weird framerate, and perfectly fixes it
            segments, info = model.transcribe(temp_file, beam_size=1, vad_filter=True)
            text = "".join([segment.text for segment in segments]).strip()
            
            if text:
                print(f"Recognized: {text}")
                conn.sendall(text.encode() + b'\n')
        except Exception as e:
            print(f"Transcription Error: {e}")
        
        audio_queue.task_done()

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"\nLive Transcription Server listening on {HOST}:{PORT}")
        
        while True:
            print("Waiting for ESP32 to connect...")
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr} - Streaming Live...")
                
                # Create a queue and start the background AI thread
                audio_queue = queue.Queue()
                ai_thread = threading.Thread(target=transcription_worker, args=(conn, audio_queue), daemon=True)
                ai_thread.start()
                
                audio_buffer = bytearray()
                start_time = time.time() # Start the live stopwatch
                
                while True:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            break
                        
                        audio_buffer.extend(data)
                        current_time = time.time()
                        elapsed = current_time - start_time
                        
                        # Once 2.5 real-world seconds have passed, process the chunk
                        if elapsed >= CHUNK_SECONDS:
                            # Calculate the true hardware speed of the ESP32 for this specific chunk
                            total_samples = len(audio_buffer) / 2
                            actual_framerate = int(total_samples / elapsed)
                            
                            print(f"[Debug] Processing 2.5s chunk at {actual_framerate} Hz")
                            
                            # Push the audio and the calculated speed to the AI
                            audio_queue.put((audio_buffer, actual_framerate))
                            
                            # Reset the buffer and stopwatch for the next 2.5 seconds
                            audio_buffer = bytearray()
                            start_time = time.time()
                            
                    except ConnectionResetError:
                        break
                
                print("Client disconnected.")
                audio_queue.put(None) # Tell the background thread to exit

if __name__ == "__main__":
    start_server()