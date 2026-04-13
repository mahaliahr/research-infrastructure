"""
pipeline.py
Core processing logic: record → transcribe → LLM response.
Extracted from main.py so it can be imported by both the FastAPI server
and (optionally) a standalone terminal runner.
"""

import os
import tempfile
import subprocess
import threading
import ollama
import sounddevice as sd
import soundfile as sf

import logger as log_module
from config import (
    SAMPLE_RATE, CHANNELS, DURATION, BUFFER_SIZE,
    WHISPER_CLI, MODEL_PATH, OLLAMA_MODEL,
    CONTEXT_FILE, PERSONA
)

# ── Load PhD context once at import time ──────────────────────────────────────
if os.path.exists(CONTEXT_FILE):
    with open(CONTEXT_FILE, "r") as f:
        PHD_CONTEXT = f.read().strip()
else:
    PHD_CONTEXT = "No background context provided."


# ── Audio ─────────────────────────────────────────────────────────────────────

def record_audio():
    """Block for DURATION seconds and return a float32 audio array."""
    import numpy as np
    print(f"[pipeline] recording {DURATION}s (sample rate: {SAMPLE_RATE})")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32"
    )
    sd.wait()
    print(f"[pipeline] recording done — max amplitude: {float(np.abs(audio).max()):.4f}")
    return audio


def save_temp_wav(audio) -> str:
    """Write audio array to a named temp WAV file; return its path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, audio, SAMPLE_RATE)
    print(f"[pipeline] saved wav: {tmp.name}")
    return tmp.name


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe(audio_path: str) -> str:
    """
    Run whisper.cpp on audio_path, return transcript text.
    Logs whisper stdout/stderr to logs/ as before.
    """
    print(f"[pipeline] transcribing: {audio_path}")
    print(f"[pipeline] whisper binary: {WHISPER_CLI}")
    print(f"[pipeline] whisper model:  {MODEL_PATH}")

    os.makedirs("logs", exist_ok=True)
    with (
        open("logs/whisper_timings.log", "a") as logf,
        open("logs/whisper_debug.log",   "a") as debugf,
    ):
        try:
            subprocess.run(
                [WHISPER_CLI, "-m", MODEL_PATH, "-f", audio_path, "-otxt"],
                check=True,
                stdout=logf,
                stderr=debugf,
                text=True
            )
            print(f"[pipeline] whisper exited OK")
        except FileNotFoundError:
            print(f"[pipeline] ERROR: whisper binary not found at: {WHISPER_CLI}")
            return "[Whisper binary not found — check WHISPER_CLI in config.py]"
        except subprocess.CalledProcessError as e:
            print(f"[pipeline] ERROR: whisper failed (return code {e.returncode})")
            print(f"[pipeline] check logs/whisper_debug.log for details")
            return f"[Transcription error: return code {e.returncode}]"

    transcript_file = f"{audio_path}.txt"
    if not os.path.exists(transcript_file):
        print(f"[pipeline] ERROR: transcript file not found: {transcript_file}")
        return "[No transcript file produced]"

    with open(transcript_file, "r") as f:
        text = f.read().strip()

    print(f"[pipeline] transcript ({len(text)} chars): {text[:120]}{'...' if len(text) > 120 else ''}")
    return text


# ── LLM ───────────────────────────────────────────────────────────────────────

def build_interjection_prompt(transcript: str) -> str:
    return f"""{PERSONA}

Here is important background context about the student's PhD:
{PHD_CONTEXT}

Here is the most recent part of the conversation:
{transcript}

Now, respond as if you just heard this in a live conversation.
- Keep your reply short (1-2 sentences).
- React directly to what was said rather than summarising.
- Speak in a natural, human way (it's okay to sound tentative or reflective).
- Avoid lists or overly formal language.
"""


def build_summary_prompt(transcript: str) -> str:
    return f"""{PERSONA}

Here is the most recent part of the conversation:
{transcript}

Please produce a structured log entry:
1. Key points discussed
2. Open questions or tensions
3. Possible next steps
"""


def query_ollama_stream(transcript: str):
    """
    Generator: yields text tokens as they stream from Ollama.
    Usage: for token in query_ollama_stream(text): ...
    """
    print(f"[pipeline] querying ollama (model: {OLLAMA_MODEL})")
    prompt = build_interjection_prompt(transcript)
    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    token_count = 0
    for chunk in stream:
        if "message" in chunk and "content" in chunk["message"]:
            token = chunk["message"]["content"]
            token_count += 1
            yield token
    print(f"[pipeline] ollama response complete ({token_count} tokens)")


def log_summary_async(transcript: str, text_log: str, json_log: str):
    """Fire-and-forget: generate a structured summary and write it to logs."""
    def _worker():
        print(f"[pipeline] generating async summary...")
        prompt = build_summary_prompt(transcript)
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = resp["message"]["content"]
        log_module.log_json(json_log, "structured_summary", {"summary": summary})
        log_module.log_text(text_log, "structured_summary", summary)
        print(f"[pipeline] summary logged")

    threading.Thread(target=_worker, daemon=True).start()


# ── Cleanup helpers ────────────────────────────────────────────────────────────

def cleanup_wav(wav_path: str):
    for p in [wav_path, wav_path + ".txt"]:
        if os.path.exists(p):
            os.remove(p)


# ── Interjection decision ─────────────────────────────────────────────────────

DECISION_PROMPT = """You are listening to a supervision meeting between a PhD student and their supervisors.

Based only on the transcript below, decide whether this is a good moment to interject with a brief observation.

Reply with only the single word YES or NO.

Interject (YES) if:
- A substantive point, argument, or idea has been completed
- A question has been asked, directly or implicitly
- There is a natural pause or shift in the conversation
- Something technically or conceptually interesting has been raised

Do not interject (NO) if:
- The conversation is clearly mid-flow
- The content is thin, filler, or administrative
- Someone is still clearly in the middle of making a point
- The transcript is blank or contains only noise

Transcript:
{transcript}

Reply YES or NO only."""


def should_interject(transcript: str) -> bool:
    """
    Ask the LLM whether this is a good moment to interject.
    Returns True if yes, False if no or if the call fails.
    """
    prompt = DECISION_PROMPT.format(transcript=transcript)
    print(f"[pipeline] checking whether to interject...")
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response["message"]["content"].strip().upper()
        # Be generous with parsing — accept anything starting with Y
        decision = answer.startswith("Y")
        print(f"[pipeline] interject decision: {answer} → {'YES' if decision else 'NO'}")
        return decision
    except Exception as e:
        print(f"[pipeline] interject check failed ({e}), defaulting to YES")
        return True  # fail open so the bot still responds if something goes wrong