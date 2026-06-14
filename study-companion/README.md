# study-companion

a local study companion bot.

runs entirely on-device. vault context is provided by the shared `research-context-layer` — no separate indexing needed here.

---

## dependencies

- `research-context-layer` running at `localhost:8000` (handles vault embedding + retrieval)
- Ollama running with `gemma3:12b` pulled
- `nomic-embed-text` pulled in Ollama (used by the context layer)

---

## setup

```bash
pip install -r requirements.txt
```

## running

start the context layer first (in its own terminal):
```bash
cd research-context-layer
python3 watcher.py       # tab 1 — watches vault for changes
uvicorn api:app          # tab 2 — serves /context endpoint
```

then start the study companion:
```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```

open `http://localhost:8001`

---

## configuration

`config.py` is the only file you should need to edit:

- `OLLAMA_MODEL` — model to use (default: `gemma3:12b`)
- `CONTEXT_API_URL` — where the context layer is running (default: `http://localhost:8000`)
- `TOP_K` — how many vault chunks to inject per turn (default: 5)
- `SYSTEM_PROMPT` — the thinking-partner persona and instructions

---

## file structure

```
study-companion/
├── config.py          — model, context layer URL, system prompt
├── retrieval.py       — calls research-context-layer /context endpoint
├── pipeline.py        — conversation history, RAG injection, Ollama streaming
├── server.py          — FastAPI backend
├── requirements.txt
└── static/
    └── index.html     — browser UI
```

---

## open questions (from research)

- can a local model grounded in vault context approximate the calibration function, or does that require something closer to the full project understanding?
- what does "holding the research frame" require technically — is it system prompt, retrieval context, or something about how the model reasons?
- which functions are most degraded by lower capability models, and which survive?
- is dialogic quality (thinking against output rather than receiving it) something that can be designed for, or does it emerge?
