"""
store.py — persistent SQLite store for chat sessions and the official-URL
cache only.

Draft persistence (create/list/get/update/delete, plus conflicts and
references) moved to the local PostgreSQL database — see
db/repositories/drafts.py and db/repositories/conflicts.py. Chat
sessions and the official-URL cache stay here because they aren't part
of the officers/drafts schema (Task 1) and don't need officer
attribution, an audit trail, or relational integrity.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "nirn_store.db")


def _get_conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_sessions(session_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS official_url_cache (
                gr_number TEXT PRIMARY KEY,
                department TEXT,
                official_url TEXT,
                last_verified TEXT,
                status TEXT
            )
        """)
        conn.commit()


_init_db()


def get_session(session_id: str) -> List[dict]:
    """Get all messages for a chat session from SQLite."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_sessions WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def add_message(session_id: str, message: dict):
    """Add a message turn to a chat session in SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_sessions (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, message.get("role", "user"), message.get("content", ""), now_iso)
        )
        conn.commit()

def get_cached_official_url(gr_number: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM official_url_cache WHERE gr_number = ?", (gr_number,)).fetchone()
        if not row:
            return None
        return dict(row)

def set_cached_official_url(gr_number: str, department: str, official_url: str, status: str = "verified"):
    now_iso = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO official_url_cache (gr_number, department, official_url, last_verified, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(gr_number) DO UPDATE SET
                official_url=excluded.official_url,
                last_verified=excluded.last_verified,
                status=excluded.status
            """,
            (gr_number, department, official_url, now_iso, status)
        )
        conn.commit()
