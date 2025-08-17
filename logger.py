import os
import json
from datetime import datetime

LOG_DIR = "logs"

def init_session():
    """Create new log files for this session."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    text_path = os.path.join(LOG_DIR, f"session_{session_id}.txt")
    json_path = os.path.join(LOG_DIR, f"session_{session_id}.jsonl")

    return text_path, json_path

def log_text(text_path, speaker, text):
    """Append a plain text entry."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(text_path, "a") as f:
        f.write(f"[{timestamp}] {speaker}: {text}\n")

def log_json(json_path, event_type, data):
    """Append structured JSON entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        **data
    }
    with open(json_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
