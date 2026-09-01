# sleep.py - Sleep Monitor & Diagnostics Engine

import os
import json
import time
import datetime
import numpy as np

import config

def load_sleep_status():
    """Load is_sleeping state from disk on startup."""
    if os.path.exists(config.SLEEP_STATUS_FILE):
        try:
            with open(config.SLEEP_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config.is_sleeping = data.get("is_sleeping", False)
        except Exception:
            config.is_sleeping = False


def save_sleep_status(sleeping: bool, start_time=None):
    """Persist active sleep state for REST queries."""
    config.is_sleeping = sleeping
    payload = {
        "is_sleeping": sleeping,
        "start_time": start_time,
        "updated_at": datetime.datetime.now().isoformat()
    }
    try:
        with open(config.SLEEP_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as e:
        print(f"[Sleep Error] Failed to save state file: {e}")


def log_sleep_event(event_name):
    """Append event status transitions to sleep log file."""
    try:
        log_path = os.path.join(config.RECORDINGS_DIR, "sleep_sessions.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts}\t{event_name}\n")
    except Exception as e:
        print(f"[Sleep Log Error] Failed to write event: {e}")


def process_sleep_session_end(handler):
    """Analyze and log the completed sleep session."""
    if handler.sleep_start_time is None:
        return None
        
    end_time = time.time()
    duration = end_time - handler.sleep_start_time
    duration_hours = duration / 3600.0
    
    # Ignore short sessions (under 10 minutes)
    if duration < 600.0:
        print(f"[Sleep Monitor] Session discarded (duration: {duration/60.0:.1f} mins too short).")
        handler.sleep_start_time = None
        return None
        
    session_type = "actual_sleep" if duration_hours >= 3.0 else "nap"
    display_type = "Sleep" if session_type == "actual_sleep" else "Nap"
    
    # Calculate statistics
    avg_noise = float(np.mean(handler.sleep_noise_levels)) if handler.sleep_noise_levels else 0.0
    max_noise = float(np.max(handler.sleep_noise_levels)) if handler.sleep_noise_levels else 0.0
    avg_ldr = float(np.mean(handler.sleep_ldr_levels)) if handler.sleep_ldr_levels else 150.0
    movements_per_hour = handler.sleep_movement_count / duration_hours
    
    # Determine quality based on movements, noise, and light levels
    if movements_per_hour <= 2.0 and avg_noise <= 300.0 and avg_ldr <= 500.0:
        quality = "Good"
    elif movements_per_hour > 5.0 or avg_noise > 600.0 or avg_ldr > 1200.0:
        quality = "Poor"
    else:
        quality = "Fair"

    # Calculate tardiness relative to scheduled bedtime
    tardiness_mins = 0
    if config.scheduled_sleep_time and session_type == "actual_sleep":
        try:
            sh, sm = map(int, config.scheduled_sleep_time.split(":"))
            start_dt = datetime.datetime.fromtimestamp(handler.sleep_start_time)
            scheduled_dt = start_dt.replace(hour=sh, minute=sm, second=0, microsecond=0)
            if start_dt.hour < 12 and sh >= 12:
                scheduled_dt = scheduled_dt - datetime.timedelta(days=1)
            if start_dt > scheduled_dt:
                tardiness_mins = int((start_dt - scheduled_dt).total_seconds() / 60)
        except Exception as e:
            print(f"[Sleep Error] Failed to compute tardiness: {e}")

    session_data = {
        "session_id": datetime.datetime.fromtimestamp(handler.sleep_start_time).strftime("%Y%m%d_%H%M%S"),
        "type": session_type,
        "start_time": datetime.datetime.fromtimestamp(handler.sleep_start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
        "duration_hours": round(duration_hours, 2),
        "movement_count": handler.sleep_movement_count,
        "average_noise": round(avg_noise, 1),
        "max_noise": round(max_noise, 1),
        "noise_events": handler.sleep_noise_events,
        "average_ldr": round(avg_ldr, 1),
        "quality": quality,
        "tardiness_minutes": tardiness_mins
    }
    
    # Send metrics update back to the physical display
    try:
        summary_cmd = f"UI_SLEEP_SUMMARY:{display_type}:{duration_hours:.1f}:{handler.sleep_movement_count}:{avg_noise:.0f}:{avg_ldr:.0f}:{quality}\n"
        handler.safe_send(summary_cmd.encode())
        print(f"[Sleep Monitor] Sent summary to ESP32: {summary_cmd.strip()}")
    except Exception as e:
        print(f"[Sleep Error] Failed to write metrics to socket: {e}")
        
    # Append session to JSON history DB
    try:
        sessions = []
        if os.path.exists(config.SLEEP_SESSIONS_FILE):
            try:
                with open(config.SLEEP_SESSIONS_FILE, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            except Exception:
                sessions = []
        sessions.append(session_data)
        with open(config.SLEEP_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
        print(f"[Sleep Monitor] Logged session details: {session_data['session_id']}")
    except Exception as e:
        print(f"[Sleep Error] Failed to write sessions file: {e}")
        
    handler.sleep_start_time = None
    return session_data
