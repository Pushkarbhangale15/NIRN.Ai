"""
repositories/conflicts.py — every query against draft_conflicts.

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens. If raw
SQL is ever unavoidable, use `text()` with bound (:named) parameters,
never interpolation.

Ownership is enforced HERE via a join back to generated_drafts, not just
in routes.py (defence in depth). For the conflict-registry lookup this
matters doubly: a conflict that exists but belongs to someone else must
come back exactly like a conflict that doesn't exist at all (both
scalar_one_or_none() -> None -> the route's 404) — never a 403, which
would leak which codes are real to someone probing them.

Column names for ORDER BY can never come from raw user input — sort_by
is checked against ALLOWED_SORT_FIELDS, a hardcoded allowlist, before it
ever reaches a query (see list_conflicts).
"""

from datetime import date as date_type
from typing import Optional
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import DraftConflict, GeneratedDraft

ALLOWED_SORT_FIELDS = {
    "created_at": DraftConflict.created_at,
    "severity": DraftConflict.severity,
}


def _scope_to_owner(stmt: Select, *, officer_id: UUID, privileged: bool) -> Select:
    if privileged:
        return stmt
    return stmt.where(GeneratedDraft.drafted_by == officer_id)


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
    stmt = _scope_to_owner(stmt, officer_id=officer_id, privileged=privileged)

    result = await session.execute(stmt)
    conflict = result.scalar_one_or_none()
    if conflict is None:
        return None

    conflict.is_dismissed = True
    conflict.dismissed_reason = reason
    await session.flush()
    return conflict


async def lookup(
    session: AsyncSession,
    *,
    conflict_id: Optional[UUID] = None,
    conflict_ref: Optional[str] = None,
    officer_id: UUID,
    privileged: bool,
) -> Optional[DraftConflict]:
    """Exactly one of conflict_id / conflict_ref must be given — the
    route decides which, based on the shape of what was typed in. One
    joined query (draft eager-loaded), ownership folded into the same
    WHERE so an existing-but-not-yours conflict looks identical to a
    nonexistent one to the caller."""
    stmt = (
        select(DraftConflict)
        .join(GeneratedDraft, DraftConflict.generated_draft_id == GeneratedDraft.generated_draft_id)
        .options(joinedload(DraftConflict.draft))
    )
    if conflict_id is not None:
        stmt = stmt.where(DraftConflict.conflict_id == conflict_id)
    else:
        stmt = stmt.where(DraftConflict.conflict_ref == conflict_ref)
    stmt = _scope_to_owner(stmt, officer_id=officer_id, privileged=privileged)

    result = await session.execute(stmt)
    return result.unique().scalar_one_or_none()


async def list_for_draft(
    session: AsyncSession,
    generated_draft_id: UUID,
    *,
    severity: Optional[str] = None,
    is_dismissed: Optional[bool] = None,
) -> list[DraftConflict]:
    """Every conflict for one draft. Ownership of the draft itself is
    already checked by the caller (routes.py reuses _load_draft, which
    goes through drafts_repo's own ownership-scoped query) — this just
    fetches its children, eager-loading `draft` too so the response
    schema's nested object needs no extra query."""
    stmt = (
        select(DraftConflict)
        .options(joinedload(DraftConflict.draft))
        .where(DraftConflict.generated_draft_id == generated_draft_id)
    )
    if severity is not None:
        stmt = stmt.where(DraftConflict.severity == severity)
    if is_dismissed is not None:
        stmt = stmt.where(DraftConflict.is_dismissed == is_dismissed)
    # severity DESC sorts high -> medium -> low because the Postgres enum
    # conflict_severity was declared low/medium/high, in that order —
    # native enum comparison follows declaration order.
    stmt = stmt.order_by(DraftConflict.severity.desc(), DraftConflict.created_at)

    result = await session.execute(stmt)
    return list(result.unique().scalars().all())


async def list_conflicts(
    session: AsyncSession,
    *,
    officer_id: UUID,
    privileged: bool,
    severity: Optional[str] = None,
    is_dismissed: Optional[bool] = None,
    department: Optional[str] = None,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    detected_by: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DraftConflict], int]:
    """Cross-draft conflict list for the current officer (or every
    officer's, if privileged)."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    if sort_dir not in ("asc", "desc"):
        raise ValueError(f"Unsupported sort direction: {sort_dir}")

    base = select(DraftConflict).join(
        GeneratedDraft, DraftConflict.generated_draft_id == GeneratedDraft.generated_draft_id
    )
    base = _scope_to_owner(base, officer_id=officer_id, privileged=privileged)
    if severity is not None:
        base = base.where(DraftConflict.severity == severity)
    if is_dismissed is not None:
        base = base.where(DraftConflict.is_dismissed == is_dismissed)
    if department is not None:
        base = base.where(GeneratedDraft.department == department)
    if date_from is not None:
        base = base.where(DraftConflict.created_at >= date_from)
    if date_to is not None:
        base = base.where(DraftConflict.created_at <= date_to)
    if detected_by is not None:
        base = base.where(DraftConflict.detected_by == detected_by)
    if search:
        like = f"%{search}%"
        base = base.where(
            or_(DraftConflict.conflicting_text.ilike(like), DraftConflict.justification.ilike(like))
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    column = ALLOWED_SORT_FIELDS[sort_by]
    order = column.asc() if sort_dir == "asc" else column.desc()
    page_stmt = (
        base.options(joinedload(DraftConflict.draft))
        .order_by(order)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(page_stmt)).unique().scalars().all()
    return list(rows), total
