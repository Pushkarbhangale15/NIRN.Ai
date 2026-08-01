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

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import DraftConflict, DraftReference, DraftVersion, GeneratedDraft
from db.repositories.conflict_refs import get_next_conflict_ref
from db.repositories.gr_numbers import get_next_gr_number

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
    source: str = "generated",
    original_filename: Optional[str] = None,
) -> GeneratedDraft:
    # Real GR numbers are assigned by the issuing department, which we
    # can't do — mint a clearly-provisional one instead (see PART 3b).
    if gr_number is None:
        gr_number = await get_next_gr_number(session, department)

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
        source=source,
        original_filename=original_filename,
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


def _apply_search(stmt: Select, search: Optional[str]) -> Select:
    if not search:
        return stmt
    # content_plain side uses the GIN full-text index already defined in
    # the migration (to_tsvector('english', coalesce(content_plain, ''))).
    # Title is short enough that a plain ILIKE is fine — it isn't part of
    # that index.
    tsquery = func.plainto_tsquery("english", search)
    tsvector = func.to_tsvector("english", func.coalesce(GeneratedDraft.content_plain, ""))
    return stmt.where(or_(tsvector.op("@@")(tsquery), GeneratedDraft.title.ilike(f"%{search}%")))


async def list_drafts(
    session: AsyncSession,
    *,
    officer_id: UUID,
    privileged: bool,
    department: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    author_id: Optional[UUID] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[GeneratedDraft, int]], int]:
    """Returns (rows, total) where each row is (draft, unresolved_conflict_count).
    The count comes from one aggregate query (a correlated subquery joined
    in below) — never an N+1 loop of per-draft COUNT queries.

    `author_id` narrows to drafts written by one officer — meant for the
    admin "view this officer's history" panel. Harmless for non-privileged
    callers too: _scope_to_owner already restricts them to their own
    drafts, so an author_id for someone else just yields zero rows."""
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    if sort_dir not in ("asc", "desc"):
        raise ValueError(f"Unsupported sort direction: {sort_dir}")

    base = select(GeneratedDraft).options(selectinload(GeneratedDraft.officer))
    base = _scope_to_owner(base, officer_id=officer_id, privileged=privileged)
    # History only ever shows drafts the officer explicitly saved — a
    # freshly generated/uploaded draft stays hidden here until PATCH
    # .../save flips is_saved, so accidental generations don't clutter it.
    base = base.where(GeneratedDraft.is_saved.is_(True))
    if department is not None:
        base = base.where(GeneratedDraft.department == department)
    if status is not None:
        base = base.where(GeneratedDraft.status == status)
    if source is not None:
        base = base.where(GeneratedDraft.source == source)
    if author_id is not None:
        base = base.where(GeneratedDraft.drafted_by == author_id)
    base = _apply_search(base, search)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    conflict_counts = (
        select(
            DraftConflict.generated_draft_id.label("draft_id"),
            func.count().label("unresolved_count"),
        )
        .where(DraftConflict.is_dismissed.is_(False))
        .group_by(DraftConflict.generated_draft_id)
        .subquery()
    )

    column = ALLOWED_SORT_FIELDS[sort_by]
    order = asc(column) if sort_dir == "asc" else desc(column)

    page_stmt = (
        base.add_columns(func.coalesce(conflict_counts.c.unresolved_count, 0))
        .outerjoin(conflict_counts, conflict_counts.c.draft_id == GeneratedDraft.generated_draft_id)
        .order_by(order)
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(page_stmt)).all()
    return [(row[0], row[1]) for row in rows], total


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


async def save_draft(
    session: AsyncSession, draft_id: UUID, *, officer_id: UUID, privileged: bool
) -> Optional[GeneratedDraft]:
    """Flips is_saved so this draft starts showing up in History (see the
    filter in list_drafts). Idempotent — saving an already-saved draft is
    a no-op, not an error."""
    draft = await get_draft(
        session, draft_id, officer_id=officer_id, privileged=privileged, with_children=False
    )
    if draft is None:
        return None
    draft.is_saved = True
    await session.flush()
    await session.refresh(draft)
    return draft


async def add_conflicts(
    session: AsyncSession, draft_id: UUID, conflicts: Iterable[dict]
) -> list[DraftConflict]:
    """Each row gets a conflict_ref minted in THIS transaction (same
    session, not yet committed) — see get_next_conflict_ref. One call per
    row rather than reserving a block up front: correctness under
    concurrency matters here far more than shaving a handful of queries
    off a batch that's at most a few dozen conflicts."""
    rows = []
    for c in conflicts:
        ref = await get_next_conflict_ref(session)
        rows.append(DraftConflict(generated_draft_id=draft_id, conflict_ref=ref, **c))
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
