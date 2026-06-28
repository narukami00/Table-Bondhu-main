"""
TCP Server - Handle connections from ESP32
"""
import socket
import threading
from ..utils import logger
from ..config import HOST, PORT
from .handlers import ClientHandler

class EmbeddedServer:
    """TCP Server for ESP32 audio streaming"""
    
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
    
    def start(self):
        """Start the TCP server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running = True
            
            logger.info(f"Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    
                    # Handle client in a separate thread
                    handler = ClientHandler(conn, addr)
                    client_thread = threading.Thread(target=handler.handle, daemon=True)
                    client_thread.start()
                    
                except KeyboardInterrupt:
                    logger.info("Server interrupted")
                    self.stop()
                except Exception as e:
                    logger.error(f"Connection error: {e}")
        
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the TCP server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info("Server stopped")
