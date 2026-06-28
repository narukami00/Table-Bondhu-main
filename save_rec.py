import socket
import wave
import speech_recognition as sr
import datetime
import os
import time

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT = 8080      
SAVE_FOLDER = "recordings"

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
    print(f"Created folder: {SAVE_FOLDER}")

def process_audio(filename):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            print("Sending to Google API...")
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            print(f"Recognized: {text}")
            return text
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError as e:
        return "API Error. Check Laptop Internet."

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        print("Waiting for ESP32 to connect...")
        
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                audio_buffer = bytearray()
                receiving_audio = False
                start_time = 0
                
                while True:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            break
                        
                        # --- START MARKER ---
                        if b"___START___" in data:
                            print("Recording started...")
                            receiving_audio = True
                            start_time = time.time()
                            audio_buffer = bytearray()
                            parts = data.split(b"___START___")
                            audio_buffer.extend(parts[-1])
                            continue
                            
                        if receiving_audio:
                            audio_buffer.extend(data)
                            
                            # --- END MARKER ---
                            if b"___END___" in audio_buffer:
                                end_time = time.time()
                                duration = end_time - start_time
                                
                                print(f"Recording stopped. Real-world duration: {duration:.2f} seconds.")
                                receiving_audio = False
                                
                                # Strip the END marker out
                                clean_audio = audio_buffer.split(b"___END___")[0]
                                
                                # Calculate the actual speed (for logging purposes only)
                                total_samples = len(clean_audio) / 2
                                actual_framerate = int(total_samples / duration)
                                print(f"ESP32 True Hardware Framerate: {actual_framerate} Hz")
                                
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = os.path.join(SAVE_FOLDER, f"audio_{timestamp}.wav")
                                
                                with wave.open(filename, "wb") as wf:
                                    wf.setnchannels(1)       
                                    wf.setsampwidth(2)       
                                    wf.setframerate(actual_framerate)
                                    wf.writeframes(clean_audio)
                                
                                recognized_text = process_audio(filename)
                                
                                # Send text back
                                conn.sendall(recognized_text.encode() + b'\n')
                                print("Text sent to ESP32.\n")
                                
                    except ConnectionResetError:
                        break
                print("Client disconnected. Waiting for new connection...")

if __name__ == "__main__":
    start_server()