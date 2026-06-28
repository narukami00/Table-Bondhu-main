"""
Client Handler - Handle individual ESP32 connections
"""
import socket
import time
from ..utils import logger
from ..audio import AudioProcessor, Transcriber
from ..llm import GeminiClient, ChatMemory

class ClientHandler:
    """Handle a single client connection"""
    
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.conn.settimeout(10)
        self.transcriber = Transcriber()
        self.llm = GeminiClient()
        self.memory = ChatMemory()
    
    def handle(self):
        """Handle client connection"""
        audio_buffer = bytearray()
        receiving_audio = False
        start_time = 0
        
        try:
            while True:
                data = self.conn.recv(4096)
                if not data:
                    break
                
                # Check for START marker
                if b"___START___" in data:
                    logger.info("Recording started")
                    receiving_audio = True
                    start_time = time.time()
                    audio_buffer = bytearray()
                    parts = data.split(b"___START___")
                    audio_buffer.extend(parts[-1])
                    continue
                
                if receiving_audio:
                    audio_buffer.extend(data)
                    
                    # Check for END marker
                    if b"___END___" in audio_buffer:
                        self.handle_audio(audio_buffer, start_time)
                        receiving_audio = False
        
        except socket.timeout:
            logger.warning(f"Client {self.addr} timeout")
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            self.conn.close()
            logger.info(f"Client {self.addr} disconnected")
    
    def handle_audio(self, audio_buffer, start_time):
        """Process audio data"""
        try:
            # Remove END marker
            clean_audio = audio_buffer.split(b"___END___")[0]
            
            # Save audio
            from ..utils import helpers
            filename = helpers.create_recording_filename()
            AudioProcessor.save_audio(clean_audio, filename)
            
            # Transcribe
            user_text = self.transcriber.transcribe_from_file(filename)
            
            # Get LLM response
            ai_answer = self.llm.send_message(user_text)
            
            # Optimize memory
            self.memory.optimize_history(self.llm.chat_session)
            
            # Send response back
            self.conn.sendall(ai_answer.encode() + b'\n')
            logger.info("Response sent to ESP32")
        
        except Exception as e:
            logger.error(f"Audio handling error: {e}")
