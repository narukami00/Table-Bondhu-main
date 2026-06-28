"""
Audio Processor - Handle audio data from ESP32
"""
import wave
from ..utils import logger
from ..config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_SAMPLE_WIDTH

class AudioProcessor:
    """Process audio data received from ESP32"""
    
    @staticmethod
    def save_audio(audio_data, filename, sample_rate=AUDIO_SAMPLE_RATE):
        """
        Save audio buffer to WAV file
        
        Args:
            audio_data (bytes): Raw audio data
            filename (str): Output filename
            sample_rate (int): Sample rate in Hz
        """
        try:
            with wave.open(filename, "wb") as wf:
                wf.setnchannels(AUDIO_CHANNELS)
                wf.setsampwidth(AUDIO_SAMPLE_WIDTH)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            logger.info(f"Audio saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            return False
    
    @staticmethod
    def calculate_framerate(audio_data, duration):
        """
        Calculate actual framerate based on data and duration
        
        Args:
            audio_data (bytes): Audio data
            duration (float): Duration in seconds
            
        Returns:
            int: Calculated sample rate
        """
        total_samples = len(audio_data) / AUDIO_SAMPLE_WIDTH
        return int(total_samples / duration)
