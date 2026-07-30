"""
repositories/drafts.py — every query against generated_drafts and its
child tables (draft_conflicts, draft_references, draft_versions).

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens. If raw
SQL is ever unavoidable, use `text()` with bound (:named) parameters,
never interpolation.

Ownership is enforced HERE, not just in routes.py (defence in depth):
every read/write takes `officer_id` + `privileged` and, unless the
caller is a reviewer/admin, filters to `drafted_by == officer_id`.

Column names for ORDER BY can never come from raw user input — sort_by
is checked against ALLOWED_SORT_FIELDS, a hardcoded allowlist, before
it ever reaches a query.
"""

from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import DraftConflict, DraftReference, DraftVersion, GeneratedDraft

ALLOWED_SORT_FIELDS = {
    "created_at": GeneratedDraft.created_at,
    "updated_at": GeneratedDraft.updated_at,
    "title": GeneratedDraft.title,
    "status": GeneratedDraft.status,
}


def _scope_to_owner(stmt: Select, *, officer_id: UUID, privileged: bool) -> Select:
    if privileged:
        return stmt
    return stmt.where(GeneratedDraft.drafted_by == officer_id)


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
) -> GeneratedDraft:
    draft = GeneratedDraft(
        title=title,
        language=language,
        drafted_by=drafted_by,
        content=content,
        content_plain=content_plain,
        department=department,
        brief=brief,
        gr_number=gr_number,
        template_score=template_score,
    )
    session.add(draft)
    await session.flush()
    await session.refresh(draft)
    return draft


async def get_draft(
    session: AsyncSession,
    draft_id: UUID,
    *,
    officer_id: UUID,
    privileged: bool,
    with_children: bool = True,
) -> Optional[GeneratedDraft]:
    stmt = select(GeneratedDraft).where(GeneratedDraft.generated_draft_id == draft_id)
    stmt = _scope_to_owner(stmt, officer_id=officer_id, privileged=privileged)
    if with_children:
        stmt = stmt.options(
            selectinload(GeneratedDraft.conflicts),
            selectinload(GeneratedDraft.references),
        )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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
) -> tuple[list[GeneratedDraft], int]:
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    if sort_dir not in ("asc", "desc"):
        raise ValueError(f"Unsupported sort direction: {sort_dir}")

    column = ALLOWED_SORT_FIELDS[sort_by]
    order = asc(column) if sort_dir == "asc" else desc(column)

    base = select(GeneratedDraft)
    base = _scope_to_owner(base, officer_id=officer_id, privileged=privileged)
    if department is not None:
        base = base.where(GeneratedDraft.department == department)
    if status is not None:
        base = base.where(GeneratedDraft.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    page_stmt = base.order_by(order).limit(limit).offset(offset)
    rows = (await session.execute(page_stmt)).scalars().all()
    return list(rows), total


async def update_content(
    session: AsyncSession,
    draft_id: UUID,
    *,
    officer_id: UUID,
    privileged: bool,
    new_content: str,
    edited_by: UUID,
    change_note: Optional[str] = None,
    new_content_plain: Optional[str] = None,
) -> Optional[GeneratedDraft]:
    draft = await get_draft(
        session, draft_id, officer_id=officer_id, privileged=privileged, with_children=False
    )
    if draft is None:
        return None

    session.add(
        DraftVersion(
            generated_draft_id=draft.generated_draft_id,
            version_number=draft.version,
            content=draft.content,
            edited_by=edited_by,
            change_note=change_note,
        )
    )
    draft.content = new_content
    if new_content_plain is not None:
        draft.content_plain = new_content_plain
    draft.version += 1
    await session.flush()
    await session.refresh(draft)
    return draft


async def archive_draft(
    session: AsyncSession, draft_id: UUID, *, officer_id: UUID, privileged: bool
) -> bool:
    draft = await get_draft(
        session, draft_id, officer_id=officer_id, privileged=privileged, with_children=False
    )
    if draft is None:
        return False
    draft.status = "archived"
    await session.flush()
    return True


async def add_conflicts(
    session: AsyncSession, draft_id: UUID, conflicts: Iterable[dict]
) -> list[DraftConflict]:
    rows = [DraftConflict(generated_draft_id=draft_id, **c) for c in conflicts]
    session.add_all(rows)
    await session.flush()
    return rows


async def add_references(
    session: AsyncSession, draft_id: UUID, references: Iterable[dict]
) -> list[DraftReference]:
    rows = [DraftReference(generated_draft_id=draft_id, **r) for r in references]
    session.add_all(rows)
    await session.flush()
    return rows
