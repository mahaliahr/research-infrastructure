# research-context-layer

Shared context layer for the PhD-Live AI bot ecosystem. Watches an Obsidian
vault, embeds notes into a local vector store, and exposes a query API for
use by the supervisor bot, confidence bot, and study companion.

## what it does

- Chunks markdown notes by heading and embeds them using `nomic-embed-text`
  via Ollama
- Stores vectors locally in ChromaDB
- Serves relevant note chunks via a FastAPI endpoint
- Watches the vault for changes and re-embeds individual files automatically

## requirements

- Python 3.13+
- Ollama running locally with `nomic-embed-text` pulled
- Dependencies: `pip3 install chromadb fastapi uvicorn watchdog requests ollama`

## setup

1. Clone the repo
2. Update `VAULT_PATH` in both `embedder.py` and `watcher.py` to point to
   your Obsidian vault
3. Run the initial embed: `python3 embedder.py`
4. Start the watcher and API in separate terminal tabs:

```bash
# tab 1
python3 watcher.py

# tab 2
python3 -m uvicorn api:app --reload
```

## querying

```bash
curl -X POST http://localhost:8000/context \
  -H "Content-Type: application/json" \
  -d '{"query": "your query here", "top_k": 5}'
```

## health check

```bash
curl http://localhost:8000/health
```

## notes

- `chroma_db/` is gitignored -- rebuild it locally by running `embedder.py`
- The vault is the source of truth, not the embeddings
- `top_k` controls how many chunks are returned (default: 5)