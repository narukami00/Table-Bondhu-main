"""
Chat Memory Manager - Manage conversation history
"""
from ..utils import logger

class ChatMemory:
    """Manage and optimize chat history"""
    
    def __init__(self, max_history=6):
        """
        Initialize chat memory
        
        Args:
            max_history (int): Maximum number of message pairs to keep
        """
        self.max_history = max_history
        self.history = []
    
    def optimize_history(self, chat_session):
        """
        Keep only recent messages to prevent token bloat
        
        Args:
            chat_session: Gemini chat session object
        """
        while len(chat_session.history) > self.max_history:
            chat_session.history.pop(0)
            chat_session.history.pop(0)
        logger.info(f"History optimized to {len(chat_session.history)} messages")
    
    def add_message(self, role, content):
        """Add message to history"""
        self.history.append({"role": role, "content": content})
