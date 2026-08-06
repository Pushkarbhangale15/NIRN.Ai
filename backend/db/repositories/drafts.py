"""
db/repositories/drafts.py — SQL RULE: every query below is built with
select()/insert()/update() from SQLAlchemy. Never an f-string, never
string concatenation. ORDER BY / sort fields that originate from a
client are mapped through the *_SORT_FIELDS allowlists below and never
touch a raw column name. See backend/README.md, "SQL injection
prevention".

Owns:
  - provisional GR-number / conflict-ref generation (atomic, race-free)
  - draft + conflicts + references creation as one unit of work
  - draft_versions snapshotting (the audit trail for Task 5c)
  - history listing (Task 6) with a single aggregate query for
    unresolved-conflict counts — no N+1
"""

import uuid
from datetime import date, datetime
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db.models import (
    DraftConflict,
    DraftReference,
    DraftStatus,
    DraftVersion,
    GeneratedDraft,
    NumberCounter,
    Officer,
    OfficerRole,
)

DRAFT_SORT_FIELDS = {
    "created_at": GeneratedDraft.created_at,
    "updated_at": GeneratedDraft.updated_at,
    "title": GeneratedDraft.title,
    "gr_number": GeneratedDraft.gr_number,
    "status": GeneratedDraft.status,
}


async def next_sequence_value(session: AsyncSession, scope_key: str) -> int:
    """
    Atomic INSERT ... ON CONFLICT DO UPDATE ... RETURNING. Two concurrent
    requests hitting the same scope_key serialise on the row lock Postgres
    takes for the upsert, so neither can observe or return the same
    value — unlike a `SELECT COUNT(*) + 1`, which races.
    """
    stmt = (
        pg_insert(NumberCounter)
        .values(scope_key=scope_key, last_value=1)
        .on_conflict_do_update(
            index_elements=[NumberCounter.scope_key],
            set_={"last_value": NumberCounter.last_value + 1},
        )
        .returning(NumberCounter.last_value)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def generate_gr_number(session: AsyncSession, department: str, year: Optional[int] = None) -> str:
    year = year or datetime.utcnow().year
    dept_code = settings.DEPARTMENT_CODES.get(department, "GEN")
    seq = await next_sequence_value(session, f"GR:{dept_code}:{year}")
    return f"NIRN/{dept_code}/{year}/{seq:06d}"


async def generate_conflict_ref(session: AsyncSession, year: Optional[int] = None) -> str:
    year = year or datetime.utcnow().year
    seq = await next_sequence_value(session, f"CFL:{year}")
    return f"CFL-{year}-{seq:06d}"


async def create_draft_with_analysis(
    session: AsyncSession,
    *,
    title: str,
    language: str,
    drafted_by: uuid.UUID,
    content: str,
    content_plain: Optional[str],
    department: str,
    brief: Optional[str],
    conflicts: Sequence[dict] = (),
    references: Sequence[dict] = (),
) -> GeneratedDraft:
    """
    Persists the draft row, every detected conflict, and every extracted
    reference in one unit of work. Nothing here calls session.commit() —
    the get_session dependency commits once the route returns, so a
    failure partway through (e.g. a bad conflict row) rolls back the
    entire insert, draft included.
    """
    gr_number = await generate_gr_number(session, department)

    draft = GeneratedDraft(
        title=title,
        language=language,
        drafted_by=drafted_by,
        content=content,
        content_plain=content_plain,
        department=department,
        brief=brief,
        gr_number=gr_number,
        status=DraftStatus.DRAFT,
    )
    session.add(draft)
    await session.flush()  # assigns generated_draft_id

    await _insert_conflicts(session, draft.generated_draft_id, conflicts)
    await _insert_references(session, draft.generated_draft_id, references)

    await session.flush()
    return draft


async def _insert_conflicts(session: AsyncSession, draft_id: uuid.UUID, conflicts: Sequence[dict]) -> list["DraftConflict"]:
    rows = []
    for c in conflicts:
        conflict_ref = await generate_conflict_ref(session)
        row = DraftConflict(
            generated_draft_id=draft_id,
            conflict_ref=conflict_ref,
            source_of_conflict=c["source_of_conflict"],
            conflicting_text=c["conflicting_text"],
            draft_excerpt=c.get("draft_excerpt"),
            draft_clause_ref=c.get("draft_clause_ref"),
            source_clause_ref=c.get("source_clause_ref"),
            conflicting_gr_id=c.get("conflicting_gr_id"),
            source_gr_title=c.get("source_gr_title"),
            source_gr_date=c.get("source_gr_date"),
            severity=c.get("severity", "medium"),
            justification=c["justification"],
            detected_by=c.get("detected_by", "llm_verifier"),
            source_ocr_low_confidence=c.get("source_ocr_low_confidence", False),
        )
        session.add(row)
        rows.append(row)
    return rows


async def persist_conflicts_for_draft(
    session: AsyncSession, draft_id: uuid.UUID, conflicts: Sequence[dict]
) -> list["DraftConflict"]:
    """Public entry point for persisting conflicts outside of initial draft
    creation — used by the live /api/analysis/{draft_id}/conflicts route so
    each detected conflict gets a real conflict_id that the Resolve Conflict
    feature can reference."""
    rows = await _insert_conflicts(session, draft_id, conflicts)
    await session.flush()
    return rows


async def _insert_references(session: AsyncSession, draft_id: uuid.UUID, references: Sequence[dict]) -> None:
    for r in references:
        session.add(
            DraftReference(
                generated_draft_id=draft_id,
                reference_text=r["reference_text"],
                extracted_gr_number=r.get("extracted_gr_number"),
                reference_date=r.get("reference_date"),
                script=r.get("script", "latin"),
                resolved=r.get("resolved", False),
            )
        )


async def has_analysis_results(session: AsyncSession, draft_id: uuid.UUID) -> bool:
    """True once this draft already has at least one persisted conflict
    or reference row — used to avoid re-inserting duplicates when the
    frontend re-runs analysis on a draft it already analysed."""
    conflict_stmt = select(func.count()).select_from(DraftConflict).where(
        DraftConflict.generated_draft_id == draft_id
    )
    ref_stmt = select(func.count()).select_from(DraftReference).where(
        DraftReference.generated_draft_id == draft_id
    )
    conflict_count = (await session.execute(conflict_stmt)).scalar_one()
    ref_count = (await session.execute(ref_stmt)).scalar_one()
    return conflict_count > 0 or ref_count > 0


async def attach_analysis_results(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    conflicts: Sequence[dict] = (),
    references: Sequence[dict] = (),
) -> None:
    """
    Persists conflicts + references detected by a POST /api/analysis/{id}
    call against an already-existing draft, in the same transaction as
    each other (both flush before the request's get_session commit).
    """
    await _insert_conflicts(session, draft_id, conflicts)
    await _insert_references(session, draft_id, references)
    await session.flush()


async def get_draft_by_id(session: AsyncSession, draft_id: uuid.UUID) -> Optional[GeneratedDraft]:
    stmt = (
        select(GeneratedDraft)
        .where(GeneratedDraft.generated_draft_id == draft_id)
        .options(
            selectinload(GeneratedDraft.conflicts),
            selectinload(GeneratedDraft.references),
            selectinload(GeneratedDraft.officer),
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def patch_draft_content(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    new_content: str,
    new_content_plain: Optional[str],
    edited_by: uuid.UUID,
    change_note: Optional[str] = None,
) -> Optional[GeneratedDraft]:
    """Snapshots the CURRENT content into draft_versions, then overwrites."""
    draft = await get_draft_by_id(session, draft_id)
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
    draft.content_plain = new_content_plain
    draft.version += 1
    await session.flush()
    return draft


async def archive_draft(session: AsyncSession, draft_id: uuid.UUID) -> Optional[GeneratedDraft]:
    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    draft.status = DraftStatus.ARCHIVED
    await session.flush()
    return draft


def _apply_common_filters(stmt, *, status: Optional[str], department: Optional[str], search: Optional[str]):
    if status:
        stmt = stmt.where(GeneratedDraft.status == status)
    if department:
        stmt = stmt.where(GeneratedDraft.department == department)
    if search:
        pattern = f"%{search}%"
        ts_match = func.to_tsvector("english", func.coalesce(GeneratedDraft.content_plain, "")).op("@@")(
            func.plainto_tsquery("english", search)
        )
        stmt = stmt.where(or_(GeneratedDraft.title.ilike(pattern), ts_match))
    return stmt


async def list_drafts(
    session: AsyncSession,
    *,
    requesting_officer_id: uuid.UUID,
    requesting_role: OfficerRole,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_desc: bool = True,
    filter_officer_id: Optional[uuid.UUID] = None,
) -> tuple[list[tuple[GeneratedDraft, int]], int]:
    """
    Returns [(draft, unresolved_conflict_count), ...] and a total count.
    A reviewer/admin sees every draft; an officer sees only their own —
    enforced here, not just in the route, so a route-level bug can't leak
    another officer's drafts.

    filter_officer_id is the admin "All Drafts" tab's filter-by-officer
    control; it's independent of the ownership restriction above (an
    admin may narrow to any one officer, an officer's own view is
    already narrowed to themselves and this would be redundant there).
    """
    conflict_counts = (
        select(
            DraftConflict.generated_draft_id.label("draft_id"),
            func.count().label("cnt"),
        )
        .where(DraftConflict.is_dismissed == False)  # noqa: E712
        .group_by(DraftConflict.generated_draft_id)
        .subquery()
    )

    stmt = select(GeneratedDraft, func.coalesce(conflict_counts.c.cnt, 0)).outerjoin(
        conflict_counts, GeneratedDraft.generated_draft_id == conflict_counts.c.draft_id
    )
    count_stmt = select(func.count()).select_from(GeneratedDraft)

    if requesting_role not in (OfficerRole.REVIEWER, OfficerRole.ADMIN):
        stmt = stmt.where(GeneratedDraft.drafted_by == requesting_officer_id)
        count_stmt = count_stmt.where(GeneratedDraft.drafted_by == requesting_officer_id)
    elif filter_officer_id is not None:
        stmt = stmt.where(GeneratedDraft.drafted_by == filter_officer_id)
        count_stmt = count_stmt.where(GeneratedDraft.drafted_by == filter_officer_id)

    stmt = _apply_common_filters(stmt, status=status, department=department, search=search)
    count_stmt = _apply_common_filters(count_stmt, status=status, department=department, search=search)

    sort_col = DRAFT_SORT_FIELDS.get(sort_by, GeneratedDraft.created_at)
    stmt = stmt.order_by(sort_col.desc() if sort_desc else sort_col.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows], total


async def list_drafts_for_officer_admin_view(
    session: AsyncSession, officer_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[tuple[GeneratedDraft, int]], int]:
    """Used by GET /api/officers/{id}/drafts — always scoped to one officer, admin-only."""
    conflict_counts = (
        select(DraftConflict.generated_draft_id.label("draft_id"), func.count().label("cnt"))
        .where(DraftConflict.is_dismissed == False)  # noqa: E712
        .group_by(DraftConflict.generated_draft_id)
        .subquery()
    )
    stmt = (
        select(GeneratedDraft, func.coalesce(conflict_counts.c.cnt, 0))
        .outerjoin(conflict_counts, GeneratedDraft.generated_draft_id == conflict_counts.c.draft_id)
        .where(GeneratedDraft.drafted_by == officer_id)
        .order_by(GeneratedDraft.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    count_stmt = (
        select(func.count()).select_from(GeneratedDraft).where(GeneratedDraft.drafted_by == officer_id)
    )
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows], total


async def admin_summary_counts(session: AsyncSession) -> dict:
    from datetime import timedelta, timezone as _tz

    total_drafts = (await session.execute(select(func.count()).select_from(GeneratedDraft))).scalar_one()
    total_unresolved = (
        await session.execute(
            select(func.count()).select_from(DraftConflict).where(DraftConflict.is_dismissed == False)  # noqa: E712
        )
    ).scalar_one()
    active_officers = (
        await session.execute(select(func.count()).select_from(Officer).where(Officer.is_active == True))  # noqa: E712
    ).scalar_one()

    # Computed in Python and bound as a parameter rather than built with
    # a raw `interval '7 days'` string, keeping this on the same
    # parametrised-query footing as every other query in this file.
    cutoff = datetime.now(_tz.utc) - timedelta(days=7)
    recent_count = (
        await session.execute(
            select(func.count()).select_from(GeneratedDraft).where(GeneratedDraft.created_at >= cutoff)
        )
    ).scalar_one()

    return {
        "total_drafts": total_drafts,
        "total_unresolved_conflicts": total_unresolved,
        "active_officers": active_officers,
        "drafts_last_7_days": recent_count,
    }
