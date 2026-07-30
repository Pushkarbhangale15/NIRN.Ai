"""
repositories/conflicts.py — every query against draft_conflicts.

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens. If raw
SQL is ever unavoidable, use `text()` with bound (:named) parameters,
never interpolation.

Ownership is enforced HERE via a join back to generated_drafts, not just
in routes.py (defence in depth).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DraftConflict, GeneratedDraft


async def dismiss_conflict(
    session: AsyncSession,
    conflict_id: UUID,
    *,
    officer_id: UUID,
    privileged: bool,
    reason: Optional[str] = None,
) -> Optional[DraftConflict]:
    stmt = (
        select(DraftConflict)
        .join(GeneratedDraft, DraftConflict.generated_draft_id == GeneratedDraft.generated_draft_id)
        .where(DraftConflict.conflict_id == conflict_id)
    )
    if not privileged:
        stmt = stmt.where(GeneratedDraft.drafted_by == officer_id)

    result = await session.execute(stmt)
    conflict = result.scalar_one_or_none()
    if conflict is None:
        return None

    conflict.is_dismissed = True
    conflict.dismissed_reason = reason
    await session.flush()
    return conflict
