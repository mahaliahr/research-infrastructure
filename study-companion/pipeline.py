"""
pipeline.py
Core logic: conversation history, RAG context injection, Ollama streaming.
"""

from __future__ import annotations

import ollama

import retrieval
from config import OLLAMA_MODEL, SYSTEM_PROMPT, MAX_HISTORY_TURNS


# ── Retrieval gate ────────────────────────────────────────────────────────────

NEEDS_RETRIEVAL_PROMPT = """does this message warrant searching a research vault for relevant notes?

reply YES if the message:
- asks about a specific research topic, concept, or project
- references something that might be in research notes
- is a substantive question about the work
- mentions specific technical components, ideas, or framings

reply NO if the message:
- is a greeting or small talk
- is a very short conversational follow-up (ok, thanks, interesting, go on)
- is about something clearly unrelated to research notes
- can be answered from conversation history alone

message: {message}

reply YES or NO only."""


def needs_retrieval(user_input: str) -> bool:
    words = user_input.strip().split()
    if len(words) <= 6:
        return False
    # short-circuit on obvious conversational openers
    conversational = {"thanks", "okay", "ok", "got it", "interesting", 
                      "right", "yes", "no", "sure", "makes sense", "go on"}
    if user_input.strip().lower() in conversational:
        return False
    return True


# ── Message builder ───────────────────────────────────────────────────────────

def build_messages(history: list[dict], user_input: str) -> tuple[list[dict], list[dict]]:
    """
    Build the messages array for Ollama.
    Only retrieves vault context if the message warrants it.
    """
    chunks = []
    if needs_retrieval(user_input):
        chunks = retrieval.retrieve(user_input)

    vault_context = retrieval.format_context(chunks)
    system = f"{SYSTEM_PROMPT}\n\n{vault_context}" if vault_context else SYSTEM_PROMPT

    messages = [{"role": "system", "content": system}]
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_input})

    return messages, chunks


# ── Streaming response ────────────────────────────────────────────────────────

def stream_response(history: list[dict], user_input: str):
    """
    Generator: yields (token, chunks) — chunks only on the first yield,
    then None for subsequent token yields.
    Caller is responsible for appending to history after the full response.
    """
    messages, chunks = build_messages(history, user_input)

    print(f"[pipeline] querying {OLLAMA_MODEL} (history: {len(history)} msgs, vault chunks: {len(chunks)})")

    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=True
    )

    first = True
    for chunk in stream:
        if "message" in chunk and "content" in chunk["message"]:
            token = chunk["message"]["content"]
            if first:
                yield token, chunks
                first = False
            else:
                yield token, None

    print(f"[pipeline] stream complete")