"""
Transcriber - Convert audio to text using Google Speech Recognition
"""
import speech_recognition as sr
from ..utils import logger

class Transcriber:
    def __init__(self, language='en-US'):
        self.recognizer = sr.Recognizer()
        self.language = language
    
    def transcribe_from_file(self, filename):
        """
        Transcribe audio from a WAV file
        
        Args:
            filename (str): Path to WAV file
            
        Returns:
            str: Transcribed text
        """
        try:
            logger.info(f"Transcribing audio from {filename}...")
            with sr.AudioFile(filename) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data, language=self.language)
                logger.info(f"Transcription: {text}")
                return text
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return "Could not understand audio"
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition error: {e}")
            return "API Error. Check Internet connection."
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return "Transcription failed"
