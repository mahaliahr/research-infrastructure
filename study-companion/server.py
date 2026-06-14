"""
server.py
FastAPI backend for the Study Companion.

Endpoints
─────────
GET  /              → UI
POST /chat          → send a message, returns SSE stream of tokens
POST /reset         → clear conversation history
GET  /status        → vault index status

Run with:
    uvicorn server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pipeline
import retrieval

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Study Companion")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Conversation state (single-user local tool) ────────────────────────────────

conversation_history: list[dict] = []


# ── Request models ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Stream a response to the user's message.
    Emits SSE events:
      { type: "token", content: "..." }
      { type: "sources", sources: [...] }
      { type: "done" }
    """
    user_message = req.message.strip()
    if not user_message:
        return {"error": "empty message"}

    # snapshot history for this request
    history_snapshot = list(conversation_history)

    async def generator() -> AsyncGenerator[str, None]:
        full_reply = ""
        sources_sent = False

        for token, chunks in pipeline.stream_response(history_snapshot, user_message):
            full_reply += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # send sources alongside first token
            if chunks is not None and not sources_sent:
                source_list = [
                    {"title": c["title"], "source": c["source"], "score": c["score"]}
                    for c in chunks
                ]
                yield f"data: {json.dumps({'type': 'sources', 'sources': source_list})}\n\n"
                sources_sent = True

        # update history after stream completes
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": full_reply})

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/reset")
def reset():
    conversation_history.clear()
    return {"status": "cleared"}


@app.get("/status")
def status():
    available = retrieval.is_available()
    chunk_count = 0
    if available:
        try:
            import requests as _req
            from config import CONTEXT_API_URL
            res = _req.get(f"{CONTEXT_API_URL}/health", timeout=3)
            chunk_count = res.json().get("chunks", 0)
        except Exception:
            pass
    return {
        "vault_indexed": available,
        "chunk_count": chunk_count,
        "history_turns": len(conversation_history) // 2,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=False)