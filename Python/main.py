"""
Main entry point for Table-Bondhu backend server
"""
import socket
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from config import settings
from server import EmbeddedServer
from utils import logger

def main():
    """Start the embedded system server"""
    logger.info("Starting Table-Bondhu backend server...")
    
    server = EmbeddedServer(
        host=settings.HOST,
        port=settings.PORT
    )
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
