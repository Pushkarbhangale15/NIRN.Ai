"""
db/repositories/conflicts.py — SQL RULE: every query below is built with
select()/update() from SQLAlchemy. Never an f-string, never string
concatenation. See backend/README.md, "SQL injection prevention".

Draft creation also writes DraftConflict rows (see
db/repositories/drafts.create_draft_with_analysis, which needs them in
the same transaction as the draft insert) — this file covers reads and
the dismiss action used by the History page (Task 6).
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DraftConflict


async def get_conflicts_for_draft(
    session: AsyncSession, draft_id: uuid.UUID, *, include_dismissed: bool = True
) -> Sequence[DraftConflict]:
    stmt = select(DraftConflict).where(DraftConflict.generated_draft_id == draft_id)
    if not include_dismissed:
        stmt = stmt.where(DraftConflict.is_dismissed == False)  # noqa: E712
    stmt = stmt.order_by(DraftConflict.created_at.asc())
    return (await session.execute(stmt)).scalars().all()


async def get_by_id(session: AsyncSession, conflict_id: uuid.UUID) -> Optional[DraftConflict]:
    stmt = select(DraftConflict).where(DraftConflict.conflict_id == conflict_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def dismiss_conflict(
    session: AsyncSession, conflict_id: uuid.UUID, *, reason: Optional[str]
) -> Optional[DraftConflict]:
    conflict = await get_by_id(session, conflict_id)
    if conflict is None:
        return None
    conflict.is_dismissed = True
    conflict.dismissed_reason = reason
    await session.flush()
    return conflict


async def resolve_conflict(
    session: AsyncSession,
    conflict_id: uuid.UUID,
    *,
    reason: Optional[str],
    resolved_clause_text: str,
) -> Optional[DraftConflict]:
    """Mark a conflict resolved (clause was revised and re-verified clean),
    as distinct from dismiss_conflict (flagged as a false positive).

    Persists resolution_status + resolved_clause_text so this survives a
    page reload or a fresh analysis run — previously only is_resolved was
    set and the revised text lived nowhere but the draft's content blob,
    so a repeat resolve attempt had no durable signal to skip on and
    re-generated a revision against stale original text, which then
    failed the accept step's content-match check.
    """
    conflict = await get_by_id(session, conflict_id)
    if conflict is None:
        return None
    conflict.is_resolved = True
    conflict.resolved_reason = reason
    conflict.resolution_status = "resolved"
    conflict.resolved_clause_text = resolved_clause_text
    await session.flush()
    return conflict


async def record_resolve_attempt(
    session: AsyncSession, conflict_id: uuid.UUID, *, status: str, reason: Optional[str] = None
) -> Optional[DraftConflict]:
    """Persist the outcome of a /resolve call that did NOT result in an
    accepted resolution — status is 'attempted_still_conflicting' (the
    revision didn't clear re-verification) or 'attempted_error' (the
    resolve pipeline itself failed). Never overwrites an already-'resolved'
    row — a stale retry response can't un-resolve a conflict.

    reason, when given, is a one-sentence explanation of why the attempt
    didn't clear (see prompts.STILL_CONFLICTING_REASON) — persisted into
    resolved_reason so it survives a page reload, not just the one-shot
    /resolve response.
    """
    conflict = await get_by_id(session, conflict_id)
    if conflict is None or conflict.resolution_status == "resolved":
        return conflict
    conflict.resolution_status = status
    if reason is not None:
        conflict.resolved_reason = reason
    await session.flush()
    return conflict
