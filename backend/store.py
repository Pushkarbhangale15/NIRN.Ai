"""
store.py — persistence entry point used by routes.py.

Two backends live here side by side:

  * GR drafts, conflicts and references now live in Postgres (see
    backend/db/models.py + backend/db/repositories/). The functions
    below are thin async wrappers around those repositories — routes.py
    calls store.create_draft(...) etc. instead of touching SQLAlchemy
    directly, keeping the repository pattern's "no queries outside
    db/repositories/" rule intact.

  * Chat sessions and the official-source URL cache are unrelated to
    officer/draft persistence and stay on the lightweight SQLite store
    at backend/data/nirn_store.db.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import drafts as drafts_repo

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


# ---------------------------------------------------------------------
# GR drafts (Postgres) — thin wrappers around db/repositories/drafts.py
# ---------------------------------------------------------------------

async def create_draft(
    session: AsyncSession,
    *,
    title: str,
    language: str,
    drafted_by: UUID,
    content: str,
    department: str,
    content_plain: Optional[str] = None,
    brief: Optional[str] = None,
    gr_number: Optional[str] = None,
    template_score: Optional[float] = None,
):
    return await drafts_repo.create_draft(
        session,
        title=title,
        language=language,
        drafted_by=drafted_by,
        content=content,
        department=department,
        content_plain=content_plain,
        brief=brief,
        gr_number=gr_number,
        template_score=template_score,
    )


async def get_draft(
    session: AsyncSession,
    draft_id: UUID,
    *,
    officer_id: UUID,
    privileged: bool,
    with_children: bool = True,
):
    return await drafts_repo.get_draft(
        session, draft_id, officer_id=officer_id, privileged=privileged, with_children=with_children
    )


async def list_drafts(
    session: AsyncSession,
    *,
    officer_id: UUID,
    privileged: bool,
    department: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
):
    return await drafts_repo.list_drafts(
        session,
        officer_id=officer_id,
        privileged=privileged,
        department=department,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


async def update_draft_content(
    session: AsyncSession,
    draft_id: UUID,
    *,
    officer_id: UUID,
    privileged: bool,
    new_content: str,
    edited_by: UUID,
    change_note: Optional[str] = None,
    new_content_plain: Optional[str] = None,
):
    return await drafts_repo.update_content(
        session,
        draft_id,
        officer_id=officer_id,
        privileged=privileged,
        new_content=new_content,
        edited_by=edited_by,
        change_note=change_note,
        new_content_plain=new_content_plain,
    )


async def archive_draft(session: AsyncSession, draft_id: UUID, *, officer_id: UUID, privileged: bool) -> bool:
    return await drafts_repo.archive_draft(session, draft_id, officer_id=officer_id, privileged=privileged)


async def add_conflicts(session: AsyncSession, draft_id: UUID, conflicts: Iterable[dict]):
    return await drafts_repo.add_conflicts(session, draft_id, conflicts)


async def add_references(session: AsyncSession, draft_id: UUID, references: Iterable[dict]):
    return await drafts_repo.add_references(session, draft_id, references)


# ---------------------------------------------------------------------
# Chat sessions (SQLite)
# ---------------------------------------------------------------------

def get_session_history(session_id: str) -> List[dict]:
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
