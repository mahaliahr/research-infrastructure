"""
retrieval.py
Queries the shared research-context-layer API.
Assumes the context layer is running at CONTEXT_API_URL.
"""

import requests
from config import CONTEXT_API_URL, TOP_K


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Return relevant vault chunks from the context layer.
    Each result: { text, source, heading, score }
    """
    try:
        res = requests.post(
            f"{CONTEXT_API_URL}/context",
            json={"query": query, "top_k": top_k},
            timeout=10
        )
        res.raise_for_status()
        data = res.json()

        chunks = []
        for r in data.get("results", []):
            chunks.append({
                "text": r["text"],
                "source": r["source"],
                "title": r.get("heading", r["source"]),
                "score": round(1 - r["distance"], 3),
            })
        return chunks

    except requests.exceptions.ConnectionError:
        print(f"[retrieval] context layer not reachable at {CONTEXT_API_URL} — continuing without vault context")
        return []
    except Exception as e:
        print(f"[retrieval] query failed: {e}")
        return []


def format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["--- relevant notes from vault ---"]
    for chunk in chunks:
        lines.append(f"\n[{chunk['title']}]")
        lines.append(chunk["text"])
    lines.append("\n--- end of vault context ---")
    return "\n".join(lines)


def is_available() -> bool:
    """Check whether the context layer is up."""
    try:
        res = requests.get(f"{CONTEXT_API_URL}/health", timeout=3)
        data = res.json()
        return data.get("chunks", 0) > 0
    except Exception:
        return False