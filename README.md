# Supervisor-Bot v1

An experimental LLM co-supervision tool for academic meetings. Records, transcribes locally using whisper.cpp, and generates reflective responses via Ollama.

## Setup

**Dependencies**

```bash
pip install sounddevice soundfile numpy ollama
```

**Requirements**
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) built and model downloaded
- [Ollama](https://ollama.com) running with a model (e.g., `ollama pull zephyr:7b`)

**Configuration**

Edit paths in `main.py`:
- `WHISPER_CLI` — path to whisper-cli binary
- `MODEL_PATH` — path to whisper model (.bin file)
- `OLLAMA_MODEL` — ollama model name

Create `context/phd-context.txt` with background about your research.

## Run

```bash
python main.py
```

Records 5-second snippets continuously. After 4 snippets (20 seconds), generates a brief response.

Press `Ctrl+C` to stop.

## Logs

Session logs saved to `logs/`:
- `.txt` — plain text conversation
- `.jsonl` — structured JSON events
- `whisper_debug.log` — whisper.cpp diagnostics

## Files

```
main.py              — core loop: record → transcribe → respond
logger.py            — session logging
context/phd-context.txt  — research background (create this)
logs/                — generated at runtime
```

## Notes

All processing happens locally — no data leaves your machine. This is a research prototype exploring AI participation in academic supervision.
