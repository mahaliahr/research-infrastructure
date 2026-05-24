# Supervisor-Bot

An experimental LLM co-supervision tool, built as part of my practice-based PhD at the Creative Computing Institute, UAL.

The bot listens to supervision meetings in short audio snippets, transcribes them locally using whisper.cpp, and interjects with brief reflective responses via a locally-running LLM (Ollama). Everything runs on-device — no audio or transcripts leave the machine.

This is a research prototype, not a finished tool. It is designed to probe how a bespoke LLM tool might participate in academic supervision, and what it does to the dynamics of the conversation.

---

## How it works

1. Records audio in short snippets (default: 5 seconds)
2. Transcribes each snippet locally with whisper.cpp
3. Buffers several snippets (default: 4), then prompts the LLM
4. Streams a short response into the browser interface
5. Logs the full session as plain text and structured JSONL

---

## Setup

**Dependencies**

```bash
pip install -r requirements.txt
```

You will also need:
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) built locally
- [Ollama](https://ollama.com) running with your chosen model pulled

**Configuration**

Edit `config.py` to set your paths, or use environment variables:

```bash
export WHISPER_CLI=/path/to/whisper-cli
export WHISPER_MODEL=/path/to/ggml-base.en.bin
export OLLAMA_MODEL=zephyr:7b
```

**Context file**

Create `context/phd-context.txt` with background on your research — this is loaded into every prompt to ground the bot's responses.

---

## Running

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. Press **Begin** to start a session.

A terminal fallback is also available:

```bash
python run_terminal.py
```

---

## File structure

```
├── config.py          — settings (paths, model, duration, buffer size)
├── pipeline.py        — audio, transcription, and LLM logic
├── server.py          — FastAPI backend + SSE event stream
├── logger.py          — session logging
├── run_terminal.py    — terminal-only fallback
├── static/
│   └── index.html     — browser UI
├── context/
│   └── phd-context.txt   — research background (create this)
└── logs/              — generated at runtime
```

---

## v1 → v1.5

The core processing logic is unchanged. v1.5 restructures the codebase and adds a browser interface:

- `main.py` (single script) split into `pipeline.py`, `server.py`, `config.py`
- All hardcoded paths moved to `config.py` / environment variables
- FastAPI backend exposes the pipeline via HTTP endpoints
- Browser UI replaces terminal output — single scrolling feed of transcripts and bot responses
- Session logs now accessible via API (`GET /sessions`, `GET /sessions/{id}`)

---

## Notes

This is an evolving research instrument. Latency is noticeable (model warmup + transcription time). Turn-taking is approximate. These constraints are part of what the prototype is designed to surface.

All participants should be aware the session is being recorded and transcribed.

