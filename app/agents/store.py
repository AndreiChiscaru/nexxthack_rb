"""Session storage in SQLite. Each session is split into parts (profile, game, chats) saved independently,
so a long agent call on one part does not overwrite concurrent changes to another."""
import json
import os
import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(os.getenv("DEMO_DB", Path(__file__).resolve().parents[2] / "data" / "demo.sqlite3"))


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("CREATE TABLE IF NOT EXISTS parts (session TEXT, part TEXT, data TEXT, PRIMARY KEY (session, part))")
    return conn


def new_session() -> str:
    session_id = uuid.uuid4().hex[:16]
    save(session_id, "meta", {"created": True})
    return session_id


def exists(session_id: str) -> bool:
    with _conn() as conn:
        return conn.execute("SELECT 1 FROM parts WHERE session = ? AND part = 'meta'", (session_id,)).fetchone() is not None


def load(session_id: str, part: str, default=None):
    with _conn() as conn:
        row = conn.execute("SELECT data FROM parts WHERE session = ? AND part = ?", (session_id, part)).fetchone()
    return json.loads(row[0]) if row else default


def save(session_id: str, part: str, value) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO parts (session, part, data) VALUES (?, ?, ?)",
                     (session_id, part, json.dumps(value, ensure_ascii=False, default=str)))


def delete(session_id: str, part: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM parts WHERE session = ? AND part = ?", (session_id, part))
