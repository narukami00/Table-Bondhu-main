# reminders.py - Alarms & Reminders Database Controller

import os
import re
import json
import datetime
import config

def parse_relative_time(rel_str):
    """Convert relative string like '10m' or '2 hours' to trigger datetime."""
    rel_str = rel_str.strip().lower()
    match = re.match(r'^(\d+)\s*(s|sec|second|m|min|minute|h|hr|hour)s?$', rel_str)
    if not match:
        return None, None
    amount = int(match.group(1))
    unit = match.group(2)
    
    if unit in ('s', 'sec', 'second'):
        delta = datetime.timedelta(seconds=amount)
        display = f"in {amount} second{'s' if amount != 1 else ''}"
    elif unit in ('m', 'min', 'minute'):
        delta = datetime.timedelta(minutes=amount)
        display = f"in {amount} minute{'s' if amount != 1 else ''}"
    else:
        delta = datetime.timedelta(hours=amount)
        display = f"in {amount} hour{'s' if amount != 1 else ''}"
        
    return datetime.datetime.now() + delta, display


def parse_absolute_time(abs_str):
    """Convert absolute time formats (like '3:00 PM', '15:30') to trigger datetime."""
    abs_str = abs_str.strip()
    now = datetime.datetime.now()

    # format: "3:00 PM"
    match = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$', abs_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3).upper()
        if ampm == 'PM' and hour != 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        display = target.strftime("%I:%M %p").lstrip("0")
        return target, display

    # format: "15:30" (24-hour clock)
    match = re.match(r'^(\d{1,2}):(\d{2})$', abs_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
            display = target.strftime("%I:%M %p").lstrip("0") + " (tomorrow)"
        else:
            display = target.strftime("%I:%M %p").lstrip("0")
        return target, display

    # format: "2026-06-28 09:00"
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})$', abs_str)
    if match:
        dt = datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)),
                               int(match.group(4)), int(match.group(5)))
        display = dt.strftime("%b %d %I:%M %p").lstrip("0")
        return dt, display

    return None, None


def _load_reminders_internal():
    """Reads JSON DB from disk. Caller must already acquire db_lock."""
    if not os.path.exists(config.REMINDERS_FILE):
        return []
    try:
        with open(config.REMINDERS_FILE, 'r') as f:
            reminders = json.load(f)
        return reminders
    except Exception:
        return []


def _save_reminders_internal(reminders):
    """Writes list to JSON DB on disk. Caller must already acquire db_lock."""
    try:
        with open(config.REMINDERS_FILE, 'w') as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        print(f"[DB Error] Failed to write reminders: {e}")


def load_reminders():
    """Thread-safe reminders list fetch."""
    with config.db_lock:
        return _load_reminders_internal()


def save_reminders(reminders):
    """Thread-safe reminders list save."""
    with config.db_lock:
        _save_reminders_internal(reminders)


def add_reminder(task, trigger_dt, display_str):
    """Thread-safe add reminder task."""
    with config.db_lock:
        reminders = _load_reminders_internal()
        reminders.append({
            "task": task,
            "trigger_time": trigger_dt.isoformat(),
            "display_time": display_str,
            "fired": False,
            "created": datetime.datetime.now().isoformat()
        })
        _save_reminders_internal(reminders)


def get_reminders_list():
    """Retrieve all non-fired reminders."""
    with config.db_lock:
        return [r for r in _load_reminders_internal() if not r.get("fired", False)]


def clear_reminders():
    """Delete all reminders."""
    with config.db_lock:
        _save_reminders_internal([])


def delete_reminder_by_index(index):
    """Delete reminder by target list index position, converting input type."""
    with config.db_lock:
        try:
            index = int(index)
        except (ValueError, TypeError):
            print(f"[Reminder Error] Failed to cast deletion index {index} to int.")
            return None
            
        reminders = _load_reminders_internal()
        active = [r for r in reminders if not r.get("fired", False)]
        if 1 <= index <= len(active):
            active[index - 1]["fired"] = True
            _save_reminders_internal(reminders)
            return active[index - 1].get("task", "Reminder")
    return None
