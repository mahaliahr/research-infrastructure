import os
import re
import sqlite3
from datetime import datetime, date
from pathlib import Path

from config import VAULT_PATH, SESSIONS_DB_PATH, OUTPUT_DIR, DAILY_NOTES_SUBFOLDER

SCRIPT_DIR = Path(__file__).parent
VAULT = Path(VAULT_PATH)
DB_PATH = (SCRIPT_DIR / SESSIONS_DB_PATH).resolve()
OUT_DIR = (SCRIPT_DIR / OUTPUT_DIR).resolve()

EXCLUDED_FOLDERS = {".trash", "templates"}


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDED_FOLDERS for part in path.parts)


def _relative_folder(path: Path) -> str:
    rel = path.relative_to(VAULT)
    parent = str(rel.parent)
    return "" if parent == "." else parent + "/"


def _today_bounds():
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_ts = day_start.timestamp()
    day_end_ts = now.timestamp()
    today = day_start.date()
    return day_start_ts, day_end_ts, today


# ---------------------------------------------------------------------------
# 1. NOTES CREATED
# ---------------------------------------------------------------------------
def collect_created(today_start: float, today_end: float) -> list[dict]:
    created = []
    for md in VAULT.rglob("*.md"):
        if _excluded(md.relative_to(VAULT)):
            continue
        ctime = os.path.getctime(md)
        if today_start <= ctime <= today_end:
            created.append({
                "name": md.stem,
                "folder": _relative_folder(md),
                "timestamp": datetime.fromtimestamp(ctime),
            })
    return created


# ---------------------------------------------------------------------------
# 2. NOTES EDITED
# ---------------------------------------------------------------------------
def collect_edited(today_start: float, today_end: float, created_names: set[str]) -> list[dict]:
    edited = []
    for md in VAULT.rglob("*.md"):
        if _excluded(md.relative_to(VAULT)):
            continue
        if md.stem in created_names:
            continue
        mtime = os.path.getmtime(md)
        if today_start <= mtime <= today_end:
            ctime = os.path.getctime(md)
            if mtime - ctime > 60:
                edited.append({
                    "name": md.stem,
                    "folder": _relative_folder(md),
                    "timestamp": datetime.fromtimestamp(mtime),
                })
    return edited


# ---------------------------------------------------------------------------
# 3. SESSIONS
# ---------------------------------------------------------------------------
def collect_sessions(today: date) -> list[dict]:
    sessions = []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT type, started, ended, duration FROM sessions "
            "WHERE date(started) = ? ORDER BY started",
            (today.isoformat(),),
        )
        for row in cur.fetchall():
            started_dt = datetime.fromisoformat(row["started"]) if row["started"] else None
            ended_dt = datetime.fromisoformat(row["ended"]) if row["ended"] else None
            sessions.append({
                "topic": row["type"] or "unknown",
                "started": started_dt,
                "ended": ended_dt,
                "duration": row["duration"],
            })
        conn.close()
    except Exception:
        pass
    return sessions


# ---------------------------------------------------------------------------
# 4. ORPHANS
# ---------------------------------------------------------------------------
def collect_orphans(today_start: float, today_end: float) -> list[dict]:
    all_md = [md for md in VAULT.rglob("*.md") if not _excluded(md.relative_to(VAULT))]

    # Build backlink index: stem -> set of stems that link to it
    backlink_pattern = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+?)?\]\]")
    linked_names: set[str] = set()
    for md in all_md:
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in backlink_pattern.finditer(content):
            target = Path(match.group(1)).stem
            linked_names.add(target)

    orphans = []
    for md in all_md:
        mtime = os.path.getmtime(md)
        if today_start <= mtime <= today_end:
            if md.stem not in linked_names:
                orphans.append({
                    "name": md.stem,
                    "folder": _relative_folder(md),
                })
    return orphans


# ---------------------------------------------------------------------------
# 5. WRITE OUTPUT
# ---------------------------------------------------------------------------
def _fmt_time(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "?"


def write_output(today: date, created, edited, sessions, orphans):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{today.isoformat()}.md"
    now = datetime.now().strftime("%H:%M")

    lines = [
        "---",
        f"date: {today.isoformat()}",
        f"generated: {now}",
        "---",
        "",
        "## notes created",
    ]
    if created:
        for n in created:
            folder = n["folder"] or f"{DAILY_NOTES_SUBFOLDER}/"
            lines.append(f"- [[{n['name']}]] — {folder} — {_fmt_time(n['timestamp'])}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## notes edited")
    if edited:
        for n in edited:
            folder = n["folder"] or f"{DAILY_NOTES_SUBFOLDER}/"
            lines.append(f"- [[{n['name']}]] — {folder} — {_fmt_time(n['timestamp'])}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## sessions")
    if sessions:
        for s in sessions:
            lines.append(f"- {s['topic']} — {_fmt_time(s['started'])} → {_fmt_time(s['ended'])}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## orphans flagged")
    if orphans:
        for o in orphans:
            lines.append(f"- [[{o['name']}]] — no backlinks")
    else:
        lines.append("- none")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {out_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    today_start, today_end, today = _today_bounds()

    created = collect_created(today_start, today_end)
    edited = collect_edited(today_start, today_end, {n["name"] for n in created})
    sessions = collect_sessions(today)
    orphans = collect_orphans(today_start, today_end)

    write_output(today, created, edited, sessions, orphans)
