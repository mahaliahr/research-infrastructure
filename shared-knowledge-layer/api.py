import os
from dotenv import load_dotenv
from supabase import create_client
import ollama
import chromadb
import sqlite3
import json
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

load_dotenv()
supabase_client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SECRET_KEY")
)

COLLECTION_NAME = "phd_notes"

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(COLLECTION_NAME)

DB_PATH = "./phd_sessions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            note TEXT,
            started TEXT NOT NULL,
            ended TEXT,
            duration INTEGER,
            status TEXT DEFAULT 'active',
            source TEXT DEFAULT 'dashboard'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VAULT_PATH = os.path.expanduser("~/Documents/GitHub/research-notes/src/site/notes")  

def append_to_daily_note(session_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()

    if not row:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    daily_path = Path(VAULT_PATH) / "daily" / f"{today}.md"

    topic = row['type']
    if row['note']:
        topic += f" · {row['note']}"

    existing = daily_path.read_text() if daily_path.exists() else ""

    # Count existing sessions to number the new one
    session_count = existing.count("<summary>Session ") + 1

    entry = (
        f"<details>\n"
        f"<summary>Session {session_count}</summary>\n"
        f"start:: {row['started']}\n"
        f"topic:: {topic}\n"
        f"end:: {row['ended']}\n"
        f"</details>"
    )

    if existing:
        if "## sessions" in existing:
            # append after the ## sessions heading
            updated = existing.replace("## sessions", f"## sessions\n{entry}")
        else:
            updated = existing + f"\n\n## sessions\n{entry}"
    else:
        updated = f"---\ndate: {today}\n---\n\n## sessions\n{entry}"

    daily_path.write_text(updated)


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


def embed_text(text):
    response = ollama.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]


@app.post("/context")
def get_context(request: QueryRequest):
    query_embedding = embed_text(request.query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "heading": results["metadatas"][0][i]["heading"],
            "distance": results["distances"][0][i]
        })

    return {"query": request.query, "results": chunks}


@app.get("/health")
def health():
    return {"status": "ok", "chunks": collection.count()}

class SessionStart(BaseModel):
    type: str
    note: str = ""
    started: str

class SessionEnd(BaseModel):
    id: int
    ended: str
    duration: int
    started: str

@app.post("/sessions/start")
def start_session(session: SessionStart):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT INTO sessions (type, note, started) VALUES (?, ?, ?)",
        (session.type, session.note, session.started)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # write to Supabase
    supabase_client.table("sessions").insert({
        "type": session.type,
        "note": session.note,
        "started": session.started,
        "status": "active",
        "source": "dashboard"
    }).execute()

    return {"id": session_id, "status": "started"}

@app.post("/sessions/end")
def end_session(session: SessionEnd):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE sessions SET ended=?, duration=? WHERE id=?",
        (session.ended, session.duration, session.id)
    )
    conn.commit()
    conn.close()

    # update Supabase
    supabase_client.table("sessions").update({
        "ended": session.ended,
        "duration": session.duration,
        "status": "complete"
    }).eq("started", session.started).execute()

    append_to_daily_note(session.id)
    return {"status": "ended"}

@app.get("/sessions")
def get_sessions(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM sessions WHERE ended IS NOT NULL ORDER BY started DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return {"sessions": [dict(r) for r in rows]}