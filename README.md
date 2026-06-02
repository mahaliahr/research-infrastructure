# research-infrastructure

this repository holds the local AI infrastructure built alongside [PhD-Live](https://github.com/mahaliahr/phd-live) as part of my practice-based PhD.

This monorepo contains the local tools, bots, and shared knowledge layer built alongside the research, as instruments of and artefacts within the inquiry itself.

## components

| directory | description |
|---|---|
| `supervisor-bot/` | LLM-powered supervision support tool with rolling context and session summaries |
| `shared-knowledge-layer/` | ChromaDB vector store over the Obsidian research vault; shared context endpoint for all bots |
| `study-companion/` | Local LLM study support bot connected to the shared context layer |
| `confidence-bot/` | Agentic public presence tool; monitors PhD-Live for new content and proposes shareable framings |
| `learning-dashboard/` | Event-renderer based dashboard for visualising research activity and session state |

## running locally

Each component runs independently. Shared dependencies: Python 3.11+, Ollama, ChromaDB.

Start the shared knowledge layer first (all bots depend on it):

```bash
cd shared-knowledge-layer
python3 -m uvicorn main:app --port 8000
```

Then start whichever bot you need:

```bash
cd supervisor-bot
python3 -m uvicorn main:app --port 8001
```