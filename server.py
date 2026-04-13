"""
server.py
FastAPI backend for Supervisor-Bot v1.5.

Endpoints
─────────
GET  /                    → serves the UI (static/index.html)
POST /session/start       → start a new recording session
POST /session/stop        → stop the current session
GET  /session/status      → current session state
GET  /stream              → SSE stream of events (transcript + bot)
GET  /sessions            → list past sessions
GET  /sessions/{id}       → replay events for a past session

Run with:
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import logger as log_module
import pipeline
from config import BUFFER_SIZE

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Supervisor-Bot v1.5")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Session state (simple in-process singleton) ────────────────────────────────

class SessionState:
    def __init__(self):
        self.active      = False
        self.text_log    = None
        self.json_log    = None
        self.session_id  = None
        self._stop_event = threading.Event()
        self._thread     = None
        self._event_queue: queue.Queue = queue.Queue()

    def _emit(self, event_type: str, data: dict):
        """Push an event to the SSE queue and write to logs."""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data,
        }
        self._event_queue.put(payload)

        if self.json_log:
            log_module.log_json(self.json_log, event_type, data)
        if self.text_log:
            speaker = "person" if event_type == "transcript" else "bot"
            text    = data.get("text", data.get("token", data.get("reply", "")))
            log_module.log_text(self.text_log, speaker, text)

    def _run_loop(self):
        """Background thread: record → transcribe → LLM, buffered."""
        snippet_buffer = []
        self._emit("session_start", {"message": "Session started"})

        while not self._stop_event.is_set():
            # Record
            self._emit("status", {"message": f"Recording snippet {len(snippet_buffer)+1}/{BUFFER_SIZE}…"})
            audio    = pipeline.record_audio()
            wav_path = pipeline.save_temp_wav(audio)

            # Transcribe
            self._emit("status", {"message": "Transcribing…"})
            transcript = pipeline.transcribe(wav_path)
            pipeline.cleanup_wav(wav_path)

            if transcript and not transcript.startswith("["):
                snippet_buffer.append(transcript)
                self._emit("transcript", {"text": transcript})

            # Respond when buffer is full
            if len(snippet_buffer) >= BUFFER_SIZE:
                joined = " ".join(snippet_buffer)

                # Ask the LLM whether this is a good moment to interject
                self._emit("status", {"message": "Deciding whether to interject…"})
                if pipeline.should_interject(joined):
                    self._emit("status", {"message": "Bot is thinking…"})
                    bot_reply = ""
                    self._emit("bot_start", {})
                    for token in pipeline.query_ollama_stream(joined):
                        bot_reply += token
                        self._emit("bot_token", {"token": token})
                    self._emit("bot_end", {"reply": bot_reply})
                    pipeline.log_summary_async(joined, self.text_log, self.json_log)
                else:
                    self._emit("status", {"message": "Listening… (bot chose not to interject)"})
                    print("[server] bot decided not to interject, continuing to listen")

                snippet_buffer = []

        self._emit("session_end", {"message": "Session ended"})

    def start(self):
        if self.active:
            return False
        self.text_log, self.json_log = log_module.init_session()
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._stop_event.clear()
        self._event_queue = queue.Queue()
        self.active = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self.active:
            return False
        self._stop_event.set()
        self.active = False
        return True


session = SessionState()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/session/start")
def start_session():
    ok = session.start()
    if not ok:
        raise HTTPException(409, "Session already running")
    return {"status": "started", "session_id": session.session_id}


@app.post("/session/stop")
def stop_session():
    ok = session.stop()
    if not ok:
        raise HTTPException(409, "No session running")
    return {"status": "stopped"}


@app.get("/session/status")
def session_status():
    return {
        "active":     session.active,
        "session_id": session.session_id,
    }


@app.get("/stream")
async def event_stream():
    """
    Server-Sent Events endpoint.
    The UI connects here and receives all session events in real time.
    """
    async def generator() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        while True:
            try:
                # Non-blocking poll of the queue; yield control between checks
                event = await loop.run_in_executor(
                    None, lambda: session._event_queue.get(timeout=0.2)
                )
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Send a keepalive comment
                yield ": keepalive\n\n"
            except Exception:
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/sessions")
def list_sessions():
    return {"sessions": log_module.list_sessions()}


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    json_path = os.path.join("logs", f"session_{session_id}.jsonl")
    events = log_module.read_session_events(json_path)
    if not events:
        raise HTTPException(404, "Session not found or empty")
    return {"session_id": session_id, "events": events}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)