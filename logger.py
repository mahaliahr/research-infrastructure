import os
import json
from datetime import datetime
from config import LOG_DIR

def init_session():
    """Create new log files for this session."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    text_path  = os.path.join(LOG_DIR, f"session_{session_id}.txt")
    json_path  = os.path.join(LOG_DIR, f"session_{session_id}.jsonl")

    return text_path, json_path


def log_text(text_path, speaker, text):
    """Append a plain-text entry."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(text_path, "a") as f:
        f.write(f"[{timestamp}] {speaker}: {text}\n")


def log_json(json_path, event_type, data):
    """Append a structured JSON entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        **data
    }
    with open(json_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_session_events(json_path):
    """Read all events from a session JSONL file."""
    if not os.path.exists(json_path):
        return []
    events = []
    with open(json_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def list_sessions():
    """Return a list of available session IDs (from JSONL files)."""
    if not os.path.exists(LOG_DIR):
        return []
    sessions = []
    for fname in sorted(os.listdir(LOG_DIR), reverse=True):
        if fname.startswith("session_") and fname.endswith(".jsonl"):
            session_id = fname[len("session_"):-len(".jsonl")]
            sessions.append(session_id)
    return sessions
