"""
Helper functions
"""
import os
import datetime

def get_timestamp():
    """Get current timestamp in format YYYYMMDD_HHMMSS"""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def create_recording_filename(folder="recordings"):
    """Generate filename for audio recording"""
    timestamp = get_timestamp()
    return os.path.join(folder, f"audio_{timestamp}.wav")
