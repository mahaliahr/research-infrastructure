"""
pipeline.py
Core processing logic: record → transcribe → LLM response.
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
    CONTEXT_FILE, PERSONA, SILENCE_THRESHOLD
)

# ── Load PhD context once at import time ──────────────────────────────────────
if os.path.exists(CONTEXT_FILE):
    with open(CONTEXT_FILE, "r") as f:
        PHD_CONTEXT = f.read().strip()
else:
    PHD_CONTEXT = "No background context provided."


# ── Audio ─────────────────────────────────────────────────────────────────────

def record_audio():
    import numpy as np
    print(f"[pipeline] recording {DURATION}s (sample rate: {SAMPLE_RATE})")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32"
    )
    sd.wait()
    amplitude = float(np.abs(audio).max())
    print(f"[pipeline] recording done — max amplitude: {amplitude:.4f}")
    return audio, amplitude


def is_silent(amplitude: float) -> bool:
    """Return True if the recording is below the silence threshold."""
    silent = amplitude < SILENCE_THRESHOLD
    if silent:
        print(f"[pipeline] silence detected (amplitude {amplitude:.4f} < threshold {SILENCE_THRESHOLD}) — skipping")
    return silent


def save_temp_wav(audio) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, audio, SAMPLE_RATE)
    print(f"[pipeline] saved wav: {tmp.name}")
    return tmp.name


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe(audio_path: str) -> str:
    print(f"[pipeline] transcribing: {audio_path}")
    print(f"[pipeline] whisper binary: {WHISPER_CLI}")
    print(f"[pipeline] whisper model:  {MODEL_PATH}")

    os.makedirs("logs", exist_ok=True)
    with (
        open("logs/whisper_timings.log", "a") as logf,
        open("logs/whisper_debug.log",   "a") as debugf,
    ):
        try:
            # --prompt seeds whisper with domain vocabulary to reduce transcription errors
            vocab_hint = (
                "PhD, supervision, speculative design, pedagogy, generative AI, "
                "epistemology, live coding, algorave, Strudel, Hydra, TidalCycles, "
                "Obsidian, digital garden, Eleventy, Vercel, machine learning, LLM, "
                "Creative Computing Institute, UAL"
            )
            subprocess.run(
                [WHISPER_CLI, "-m", MODEL_PATH, "-f", audio_path, "-otxt",
                 "--prompt", vocab_hint],
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


# ── LLM prompts ───────────────────────────────────────────────────────────────

def build_interjection_prompt(transcript: str, conversation_so_far: str = "") -> str:
    context_block = ""
    if conversation_so_far.strip():
        context_block = f"""
Here is a summary of the conversation so far:
{conversation_so_far}
"""

    return f"""{PERSONA}

Here is important background context about the student's PhD:
{PHD_CONTEXT}
{context_block}
Here is the most recent part of the conversation:
{transcript}

Now, respond as if you just heard this in a live conversation.
- Keep your reply to 1-2 sentences maximum.
- React directly and specifically to what was just said.
- Speak naturally — tentative, reflective, or curious as feels right.
- In every response vary how you open your response. Do not start with "It sounds like", "Wow", "That's interesting", or "Great". Instead try openings like "I wonder...", "There's something in...", "That raises...", "Could it be that...", "What strikes me...", or just dive straight into your thought.
- Avoid summarising what was said back to the speaker.
- No lists, no formal language.
- Where relevant, draw on the research context to enrich your response — but keep it brief and directly tied to what was just said.
"""


def build_rolling_summary_prompt(conversation_so_far: str, new_transcript: str) -> str:
    return f"""You are summarising an ongoing PhD supervision meeting for your own reference.

Current summary:
{conversation_so_far if conversation_so_far.strip() else "(nothing yet)"}

New conversation excerpt to incorporate:
{new_transcript}

Update the summary to include the new excerpt. Keep it concise (4-6 sentences max). 
Focus on: topics discussed, questions raised, ideas proposed. Plain prose, no lists.
"""


def build_session_summary_prompt(full_transcript: str, bot_responses: list) -> str:
    responses_text = "\n".join(f"- {r}" for r in bot_responses) if bot_responses else "(none)"
    return f"""{PERSONA}

Below is the full transcript of a supervision meeting and the responses you made during it.

--- Conversation transcript ---
{full_transcript}

--- Your responses during the session ---
{responses_text}

Please produce two short sections:

1. Meeting summary (4-6 sentences): what was discussed, key ideas and questions raised, any tensions or unresolved points.

2. Reflection on your contributions (2-3 sentences): what you added, what you might have missed, and any threads worth following up.

Keep it concise and honest. Plain prose.
"""


def build_per_buffer_summary_prompt(transcript: str) -> str:
    return f"""{PERSONA}

Here is the most recent part of the conversation:
{transcript}

Please produce a structured log entry:
1. Key points discussed
2. Open questions or tensions
3. Possible next steps
"""


# ── LLM calls ────────────────────────────────────────────────────────────────

def query_ollama_stream(transcript: str, conversation_so_far: str = ""):
    """Generator: yields text tokens as they stream from Ollama."""
    print(f"[pipeline] querying ollama (model: {OLLAMA_MODEL})")
    prompt = build_interjection_prompt(transcript, conversation_so_far)
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


def update_rolling_summary(conversation_so_far: str, new_transcript: str) -> str:
    """Synchronously update the rolling conversation summary."""
    print(f"[pipeline] updating rolling summary...")
    prompt = build_rolling_summary_prompt(conversation_so_far, new_transcript)
    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = resp["message"]["content"].strip()
        print(f"[pipeline] rolling summary updated ({len(summary)} chars)")
        return summary
    except Exception as e:
        print(f"[pipeline] rolling summary failed ({e}), keeping previous")
        return conversation_so_far


def generate_session_summary(full_transcript: str, bot_responses: list, text_log: str, json_log: str):
    """Fire-and-forget: generate end-of-session summary and emit it via callback."""
    def _worker():
        print(f"[pipeline] generating session summary...")
        prompt = build_session_summary_prompt(full_transcript, bot_responses)
        try:
            resp = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = resp["message"]["content"].strip()
            log_module.log_json(json_log, "session_summary", {"summary": summary})
            log_module.log_text(text_log, "session_summary", summary)
            print(f"[pipeline] session summary logged")
            return summary
        except Exception as e:
            print(f"[pipeline] session summary failed ({e})")
            return ""
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def log_summary_async(transcript: str, text_log: str, json_log: str):
    """Fire-and-forget: per-buffer structured log entry."""
    def _worker():
        print(f"[pipeline] generating buffer summary...")
        prompt = build_per_buffer_summary_prompt(transcript)
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = resp["message"]["content"]
        log_module.log_json(json_log, "structured_summary", {"summary": summary})
        log_module.log_text(text_log, "structured_summary", summary)
        print(f"[pipeline] buffer summary logged")
    threading.Thread(target=_worker, daemon=True).start()


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
    prompt = DECISION_PROMPT.format(transcript=transcript)
    print(f"[pipeline] checking whether to interject...")
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response["message"]["content"].strip().upper()
        decision = answer.startswith("Y")
        print(f"[pipeline] interject decision: {answer} → {'YES' if decision else 'NO'}")
        return decision
    except Exception as e:
        print(f"[pipeline] interject check failed ({e}), defaulting to YES")
        return True


# ── Cleanup ───────────────────────────────────────────────────────────────────

def cleanup_wav(wav_path: str):
    for p in [wav_path, wav_path + ".txt"]:
        if os.path.exists(p):
            os.remove(p)