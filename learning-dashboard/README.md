# learning-dashboard

Local dashboard for the PhD-Live research infrastructure. Houses the activity
logger, bot interfaces, and Mirror. Built with React + Vite.

## requires

- `research-context-layer` running on port 8000 (start that first)
- Node.js

## running

```bash
# tab 1 — backend (in shared-knowledge-layer folder)
python3 -m uvicorn api:app --reload

# tab 2 — dashboard (in this folder)
npm run dev
```

Then open `http://localhost:5173`

## current features

- Activity log — start/end sessions, writes to SQLite + appends to Obsidian daily note
- Navigation shell for Supervisor Bot, Study Companion, Confidence Bot, Mirror (placeholder pages)

## notes

- Sessions persist in SQLite via the backend, not localStorage
- Active session survives page refresh via localStorage