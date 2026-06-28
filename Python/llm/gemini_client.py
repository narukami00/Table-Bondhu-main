"""
Gemini LLM Client - Wrapper for Google Gemini API
"""
import google.generativeai as genai
from ..utils import logger
from ..config import GEMINI_API_KEY, GEMINI_MODEL, SYSTEM_INSTRUCTION

class GeminiClient:
    def __init__(self, api_key=None, model=GEMINI_MODEL):
        """
        Initialize Gemini client
        
        Args:
            api_key (str): Google Gemini API key
            model (str): Model name to use
        """
        api_key = api_key or GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not provided")
        
        genai.configure(api_key=api_key)
        self.model = model
        self.llm = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_INSTRUCTION
        )
        self.chat_session = self.llm.start_chat(history=[])
        logger.info(f"Gemini client initialized with model: {model}")
    
    def send_message(self, user_text):
        """
        Send message to Gemini and get response
        
        Args:
            user_text (str): User message
            
        Returns:
            str: AI response
        """
        try:
            logger.info(f"User: {user_text}")
            response = self.chat_session.send_message(user_text)
            ai_answer = response.text.strip()
            logger.info(f"AI: {ai_answer}")
            return ai_answer
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "Error processing request"
    
    def get_history(self):
        """Get chat history"""
        return self.chat_session.history
