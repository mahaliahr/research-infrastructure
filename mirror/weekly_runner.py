import os
import re
import sys
import time
import collections
from datetime import datetime, date, timedelta
from pathlib import Path

import ollama
import chromadb

from config import VAULT_PATH, SESSIONS_DB_PATH, OUTPUT_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
WEEKLY_OUTPUT_DIR = (SCRIPT_DIR / "../mirror-outputs/weekly").resolve()
DAILY_OUTPUT_DIR = (SCRIPT_DIR / "../mirror-outputs/daily").resolve()
CHROMA_DB_PATH = (SCRIPT_DIR / "../shared-knowledge-layer/chroma_db").resolve()
COLLECTION_NAME = "phd_notes"
OLLAMA_MODEL = "qwen2.5:32b"
OLLAMA_FALLBACK_MODEL = "llama3.3:70b-instruct-q4_K_M"

VAULT = Path(VAULT_PATH)
EXCLUDED_FOLDERS = {".trash", "templates"}

STOP_WORDS = {
    "a", "an", "the", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being",
    "in", "of", "on", "with", "for", "to", "and", "or",
    "but", "it", "its", "as", "at", "by", "from", "also",
    "which", "who", "when", "where", "not", "no", "nor",
    "has", "have", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must",
    "than", "rather", "such", "each", "all",
    "more", "most", "very", "just", "so", "if", "then",
    "there", "their", "they", "we", "i", "you", "he", "she",
    "what", "how", "about", "into", "through", "between",
    "while", "within", "without", "both", "any", "some",
    "can", "use", "used", "using", "make", "made", "making",
}

SYSTEM_PROMPT = (
    "you are a non-directive research mirror. your role is to observe and\n"
    "surface patterns, not to advise or evaluate. write in lowercase.\n"
    "do not use em dashes. be terse. do not explain what you are doing."
)


def _err(msg: str) -> None:
    print(f"[mirror-weekly] {msg}", file=sys.stderr)


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDED_FOLDERS for part in path.parts)


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text



# ---------------------------------------------------------------------------
# 1. LOAD DAILY FILES
# ---------------------------------------------------------------------------
def _parse_daily_file(path: Path) -> dict:
    """Return dict with keys: created, edited, sessions, orphans."""
    result = {"created": [], "edited": [], "sessions": [], "orphans": []}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return result

    section = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## notes created"):
            section = "created"
        elif line.startswith("## notes edited"):
            section = "edited"
        elif line.startswith("## sessions"):
            section = "sessions"
        elif line.startswith("## orphans"):
            section = "orphans"
        elif line.startswith("## "):
            section = None
        elif line.startswith("- ") and section and line != "- none":
            result[section].append(line[2:])
    return result


def _parse_note_entry(entry: str) -> tuple[str, str] | None:
    """Extract (name, path) from '[[name]] — path/ — HH:MM'."""
    m = re.match(r"\[\[(.+?)]].*?—\s*(.+?)\s*—", entry)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def _parse_session_entry(entry: str) -> tuple[str, str, str] | None:
    """Extract (topic, start, end) from 'topic — HH:MM → HH:MM'."""
    m = re.match(r"(.+?)\s+—\s+(\S+)\s+→\s+(\S+)", entry)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return None


def load_daily_files(today: date) -> dict:
    week_start = today - timedelta(days=6)
    days = [week_start + timedelta(days=i) for i in range(7)]

    all_notes_created: list[tuple[str, str, date]] = []
    all_notes_edited: list[tuple[str, str, date]] = []
    all_sessions: list[tuple[str, str, str, date]] = []
    orphan_first_seen: dict[str, date] = {}
    active_days: int = 0
    inactive_days: list[date] = []

    for day in days:
        fpath = DAILY_OUTPUT_DIR / f"{day.isoformat()}.md"
        parsed = _parse_daily_file(fpath)

        day_active = False

        for entry in parsed["created"]:
            result = _parse_note_entry(entry)
            if result:
                all_notes_created.append((*result, day))
                day_active = True

        for entry in parsed["edited"]:
            result = _parse_note_entry(entry)
            if result:
                all_notes_edited.append((*result, day))
                day_active = True

        for entry in parsed["sessions"]:
            result = _parse_session_entry(entry)
            if result:
                all_sessions.append((*result, day))
                day_active = True

        for entry in parsed["orphans"]:
            m = re.match(r"\[\[(.+?)]]", entry)
            if m:
                name = m.group(1).strip()
                if name not in orphan_first_seen:
                    orphan_first_seen[name] = day

        if day_active:
            active_days += 1
        else:
            inactive_days.append(day)

    all_orphans = [(name, first) for name, first in orphan_first_seen.items()]

    return {
        "days": days,
        "all_notes_created": all_notes_created,
        "all_notes_edited": all_notes_edited,
        "all_sessions": all_sessions,
        "all_orphans": all_orphans,
        "active_days": active_days,
        "inactive_days": inactive_days,
    }


# ---------------------------------------------------------------------------
# 2. FREQUENCY COUNTS
# ---------------------------------------------------------------------------
def _all_stop_words(phrase: str) -> bool:
    return all(w in STOP_WORDS for w in phrase.split())


def build_frequency_counts(today: date) -> dict:
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    week_ago_ts = week_ago.timestamp()

    tag_counts: collections.Counter = collections.Counter()
    link_counts: collections.Counter = collections.Counter()
    phrase_counts: collections.Counter = collections.Counter()

    tag_re = re.compile(r"#([a-zA-Z][a-zA-Z0-9_/]*)")
    link_re = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+?)?\]\]")
    word_re = re.compile(r"\b([a-z][a-z\-']*)\b")

    corpus_words_per_file: list[list[str]] = []

    for root, dirs, files in os.walk(VAULT_PATH):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            try:
                mt = os.path.getmtime(p)
            except OSError:
                continue
            if mt > week_ago_ts:
                try:
                    raw = open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue

                content = strip_frontmatter(raw)

                for m in tag_re.finditer(content):
                    tag_counts[m.group(1)] += 1

                for m in link_re.finditer(content):
                    target = Path(m.group(1)).stem.strip()
                    if target:
                        link_counts[target] += 1

                words = [w for w in word_re.findall(content.lower()) if w not in STOP_WORDS]
                corpus_words_per_file.append(words)

    # 2-3 word phrases across all files combined
    all_words = [w for words in corpus_words_per_file for w in words]
    for i in range(len(all_words) - 1):
        bigram = f"{all_words[i]} {all_words[i+1]}"
        phrase_counts[bigram] += 1
    for i in range(len(all_words) - 2):
        trigram = f"{all_words[i]} {all_words[i+1]} {all_words[i+2]}"
        phrase_counts[trigram] += 1

    # filter phrases below threshold and all-stop-word phrases
    phrase_counts = collections.Counter(
        {k: v for k, v in phrase_counts.items() if v >= 3 and not _all_stop_words(k)}
    )

    top_tags = tag_counts.most_common(10)
    top_links = link_counts.most_common(10)
    top_phrases = phrase_counts.most_common(10)

    # combine into overall top 15 by count
    combined: collections.Counter = collections.Counter()
    for term, count in top_tags:
        combined[f"#{term}"] += count
    for term, count in top_links:
        combined[f"[[{term}]]"] += count
    for term, count in top_phrases:
        combined[term] += count

    top_15 = combined.most_common(15)

    return {
        "top_tags": top_tags,
        "top_links": top_links,
        "top_phrases": top_phrases,
        "top_15": top_15,
    }


# ---------------------------------------------------------------------------
# 3. CHROMADB SEMANTIC PASS
# ---------------------------------------------------------------------------
def semantic_pass(top_15: list[tuple[str, int]]) -> list[str]:
    semantic_chunks: list[str] = []
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collection = client.get_or_create_collection(COLLECTION_NAME)

        query_terms = [term for term, _ in top_15[:3]]
        seen_ids: set[str] = set()

        for term in query_terms:
            try:
                results = collection.query(query_texts=[term], n_results=5)
                docs = results.get("documents", [[]])[0]
                ids = results.get("ids", [[]])[0]
                for doc_id, doc in zip(ids, docs):
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        semantic_chunks.append(doc)
                        if len(semantic_chunks) >= 15:
                            break
            except Exception as e:
                _err(f"chromadb query failed for '{term}': {e}")
            if len(semantic_chunks) >= 15:
                break
    except Exception as e:
        _err(f"chromadb connection failed: {e}")

    return semantic_chunks


# ---------------------------------------------------------------------------
# 4 & 5. LLM PASSES
# ---------------------------------------------------------------------------
def _call_llm(messages: list[dict]) -> str | None:
    for model in (OLLAMA_MODEL, OLLAMA_FALLBACK_MODEL):
        try:
            response = ollama.chat(model=model, messages=messages)
            return response["message"]["content"].strip()
        except Exception as e:
            _err(f"ollama call failed ({model}): {e}")
    return None


def llm_synthesis(top_15: list, orphan_names: list[str], daily: dict,
                  semantic_chunks: list[str]) -> str:
    terms_block = "\n".join(f"  {term} ×{count}" for term, count in top_15)
    orphans_block = "\n".join(f"  {n}" for n in orphan_names) or "  none"
    chunks_block = "\n\n".join(c[:500] for c in semantic_chunks[:8]) or "  none"

    user_prompt = (
        "given the following data from this week's research activity, write\n"
        "a short paragraph (3-5 sentences) describing what the notes seem to\n"
        "be circling around. name specific terms and patterns you can see in\n"
        "the data. do not give advice. do not ask questions. observe only.\n\n"
        f"terms this week (frequency):\n{terms_block}\n\n"
        f"orphan notes:\n{orphans_block}\n\n"
        "activity summary:\n"
        f"{len(daily['all_notes_created'])} notes created, "
        f"{len(daily['all_notes_edited'])} notes edited, "
        f"{len(daily['all_sessions'])} sessions, "
        f"{daily['active_days']} active days\n\n"
        f"relevant vault excerpts:\n{chunks_block}"
    )

    result = _call_llm([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return result if result is not None else "[synthesis unavailable]"


def llm_generated_prompt(synthesis: str, top_15: list,
                         orphan_names: list[str]) -> str:
    terms_block = "\n".join(f"  {term} ×{count}" for term, count in top_15)
    orphans_block = "\n".join(f"  {n}" for n in orphan_names) or "  none"

    user_prompt = (
        "given the synthesis statement below and the data it was grounded in,\n"
        "generate exactly one specific question. the question must name actual\n"
        "terms, note titles, or patterns visible in the data. do not ask\n"
        "generic reflective questions. do not ask more than one question.\n\n"
        f"synthesis:\n{synthesis}\n\n"
        f"terms this week (frequency):\n{terms_block}\n\n"
        f"orphan notes:\n{orphans_block}"
    )

    result = _call_llm([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])

    if result is None:
        return "[prompt unavailable]"

    # keep only the first question if multiple are returned
    questions = [s.strip() for s in result.split("?") if s.strip()]
    return (questions[0] + "?") if questions else result


# ---------------------------------------------------------------------------
# 6. WRITE OUTPUT
# ---------------------------------------------------------------------------
_DAY_ABBRS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def write_output(today: date, daily: dict, freq: dict,
                 synthesis: str, generated_prompt: str) -> None:
    WEEKLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    iso_week = today.strftime("%G-W%V")
    week_start = daily["days"][0]
    week_end = daily["days"][-1]
    now = datetime.now().strftime("%H:%M")
    out_path = WEEKLY_OUTPUT_DIR / f"{iso_week}.md"

    # per-day activity tallies
    day_notes: dict[date, int] = collections.defaultdict(int)
    day_sessions: dict[date, int] = collections.defaultdict(int)
    for *_, d in daily["all_notes_created"]:
        day_notes[d] += 1
    for *_, d in daily["all_notes_edited"]:
        day_notes[d] += 1
    for *_, d in daily["all_sessions"]:
        day_sessions[d] += 1

    lines = [
        "---",
        f"week: {iso_week}",
        f"period: {week_start.isoformat()} → {week_end.isoformat()}",
        f"generated: {now}",
        "---",
        "",
        "## summary",
        f"- notes created: {len(daily['all_notes_created'])}",
        f"- notes edited: {len(daily['all_notes_edited'])}",
        f"- sessions: {len(daily['all_sessions'])}",
        f"- active days: {daily['active_days']}/7",
        "",
        "## activity by day",
    ]

    for day in daily["days"]:
        abbr = _DAY_ABBRS[day.weekday()]
        dd = day.strftime("%d")
        notes = day_notes.get(day, 0)
        sessions = day_sessions.get(day, 0)
        if notes == 0 and sessions == 0:
            lines.append(f"- {abbr} {dd}: no activity")
        else:
            lines.append(f"- {abbr} {dd}: {notes} notes · {sessions} sessions")

    lines.append("")
    lines.append("## recurring terms")
    if freq["top_15"]:
        for term, count in freq["top_15"]:
            lines.append(f"- {term} — {count}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## orphans this week")
    if daily["all_orphans"]:
        for name, first_date in daily["all_orphans"]:
            lines.append(f"- [[{name}]] — first flagged {first_date.isoformat()}")
    else:
        lines.append("- none")

    # grounded-in summary line
    top3 = freq["top_15"][:3]
    grounded_terms = ", ".join(f"{t} ×{c}" for t, c in top3)
    n_orphans = len(daily["all_orphans"])
    n_created = len(daily["all_notes_created"])
    n_sessions = len(daily["all_sessions"])

    lines += [
        "",
        "## synthesis",
        "",
        synthesis,
        "",
        f"grounded in: {grounded_terms}, {n_orphans} orphan notes, "
        f"{n_created} notes created, {n_sessions} sessions",
        "",
        "## generated prompt",
        generated_prompt,
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {out_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    chroma_abs = os.path.abspath(CHROMA_DB_PATH)
    print(f"[mirror-weekly] chromadb path: {chroma_abs}")
    print(f"[mirror-weekly] chromadb exists: {os.path.exists(chroma_abs)}")

    today = date.today()

    try:
        daily = load_daily_files(today)
    except Exception as e:
        _err(f"load_daily_files failed: {e}")
        daily = {
            "days": [today - timedelta(days=6 - i) for i in range(7)],
            "all_notes_created": [],
            "all_notes_edited": [],
            "all_sessions": [],
            "all_orphans": [],
            "active_days": 0,
            "inactive_days": [],
        }

    try:
        freq = build_frequency_counts(today)
    except Exception as e:
        _err(f"build_frequency_counts failed: {e}")
        freq = {"top_tags": [], "top_links": [], "top_phrases": [], "top_15": []}

    semantic_chunks = semantic_pass(freq["top_15"])

    orphan_names = [name for name, _ in daily["all_orphans"]]

    synthesis = llm_synthesis(freq["top_15"], orphan_names, daily, semantic_chunks)
    generated_prompt = llm_generated_prompt(synthesis, freq["top_15"], orphan_names)

    write_output(today, daily, freq, synthesis, generated_prompt)
