"""
store.py — persistent SQLite store for drafts and chat sessions.

Replaces the temporary in-memory dictionary with a lightweight SQLite database
stored at backend/data/nirn_store.db. Surges survival across backend restarts.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from schemas import Draft, DraftCreate

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "nirn_store.db")


def _get_conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                department TEXT NOT NULL,
                body_text TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
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


def create_draft(payload: DraftCreate) -> Draft:
    """Store a new draft in SQLite and return it with an id and timestamp."""
    draft_id = uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).isoformat()
    
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO drafts (id, title, department, body_text, language, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (draft_id, payload.title, payload.department, payload.body_text, payload.language.value, now_iso)
        )
        conn.commit()

    return Draft(
        id=draft_id,
        created_at=datetime.fromisoformat(now_iso),
        **payload.model_dump()
    )


def get_draft(draft_id: str) -> Optional[Draft]:
    """Return the draft from SQLite, or None if it does not exist."""
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if not row:
            return None
        return Draft(
            id=row["id"],
            title=row["title"],
            department=row["department"],
            body_text=row["body_text"],
            language=row["language"],
            created_at=datetime.fromisoformat(row["created_at"])
        )


def list_drafts() -> List[Draft]:
    """All drafts, newest first."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM drafts ORDER BY created_at DESC").fetchall()
        return [
            Draft(
                id=r["id"],
                title=r["title"],
                department=r["department"],
                body_text=r["body_text"],
                language=r["language"],
                created_at=datetime.fromisoformat(r["created_at"])
            )
            for r in rows
        ]


def delete_draft(draft_id: str) -> bool:
    """Returns True if something was deleted, False if the id was unknown."""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
        conn.commit()
        return cur.rowcount > 0


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
