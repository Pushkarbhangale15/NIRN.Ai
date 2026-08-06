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
from db.integrity import hash_content
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
from db.repositories import workflow as workflow_repo


class InvalidWorkflowStateError(Exception):
    """Raised when a workflow action is attempted from the wrong
    generated_drafts.status — mapped to HTTP 400 by the route."""


class DraftImmutableError(Exception):
    """Raised when content edits are attempted against an approved
    (immutable) draft — mapped to HTTP 409 by the route."""


# POST .../approve's request body uses present tense ('accept_reviewer_version'
# | 'keep_original'); draft_workflow_events.decision (workflow_decision enum)
# records the past-tense audit form ('accepted_reviewer_version' |
# 'kept_original') — see approve_draft below.
_EVENT_DECISION = {
    "accept_reviewer_version": "accepted_reviewer_version",
    "keep_original": "kept_original",
}


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
    """Snapshots the CURRENT content into draft_versions, then overwrites.

    Raises DraftImmutableError if the draft is already approved — from
    that point on, a real government resolution is treated as final;
    the only further action is Archive (see archive_draft)."""
    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    if draft.status == DraftStatus.APPROVED:
        raise DraftImmutableError(
            "This draft has been approved and is final; content can no longer be edited."
        )

    session.add(
        DraftVersion(
            generated_draft_id=draft.generated_draft_id,
            version_number=draft.version,
            content=draft.content,
            content_plain=draft.content_plain,
            content_sha256=hash_content(draft.content),
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


# =====================================================================
# Three-tier draft approval workflow — Drafting Officer -> Reviewing
# Officer -> Approving Authority. Every transition below writes exactly
# one append-only draft_workflow_events row (via workflow_repo) in the
# same transaction as the status/content change, so the two can never
# drift apart.
# =====================================================================

async def get_version_snapshot(
    session: AsyncSession, draft: GeneratedDraft, version_number: int
) -> tuple[str, str, str]:
    """
    Returns (content_html, content_plain, content_sha256) for a specific
    version_number of a draft: the live row if it IS the draft's current
    version, otherwise the frozen draft_versions snapshot.

    Raises ValueError if version_number doesn't exist for this draft at
    all — mapped to HTTP 404 by the route.
    """
    if version_number == draft.version:
        return draft.content, (draft.content_plain or draft.content), hash_content(draft.content)
    stmt = select(DraftVersion).where(
        DraftVersion.generated_draft_id == draft.generated_draft_id,
        DraftVersion.version_number == version_number,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise ValueError(f"Version {version_number} does not exist for this draft.")
    return row.content, (row.content_plain or row.content), row.content_sha256


async def submit_for_review(
    session: AsyncSession, draft_id: uuid.UUID, *, officer_id: uuid.UUID, officer_role: OfficerRole
) -> Optional[GeneratedDraft]:
    """Drafting Officer only, and only their own draft. Content is
    untouched — this just moves the draft into the Reviewing Officer's
    queue, so content_version_before == content_version_after."""
    if officer_role != OfficerRole.OFFICER:
        raise PermissionError("Only a drafting officer may submit a draft for review.")

    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    if draft.drafted_by != officer_id:
        raise PermissionError("You may only submit your own drafts for review.")
    if draft.status != DraftStatus.DRAFT:
        raise InvalidWorkflowStateError(
            f"Draft must be in 'draft' status to submit for review (currently '{draft.status.value}')."
        )

    draft.status = DraftStatus.SUBMITTED
    draft.returned_reason = None
    await session.flush()
    await workflow_repo.create_event(
        session,
        draft_id=draft.generated_draft_id,
        from_status=DraftStatus.DRAFT.value,
        to_status=DraftStatus.SUBMITTED.value,
        actor_id=officer_id,
        actor_role=officer_role.value,
        content_version_before=draft.version,
        content_version_after=draft.version,
        decision="submitted",
        note=None,
    )
    return draft


async def forward_to_approval(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    officer_id: uuid.UUID,
    officer_role: OfficerRole,
    new_content: Optional[str],
    new_content_plain: Optional[str] = None,
) -> Optional[GeneratedDraft]:
    """Reviewing Officer (or admin) only. Draft must be 'submitted'.

    If new_content is provided and differs from the current stored
    content, snapshots a new draft_versions row for what's being
    replaced (with its content_sha256) and records
    decision='edited_and_forwarded'. Otherwise records
    decision='forwarded_unchanged' — no pointless version row when
    nothing changed."""
    if officer_role not in (OfficerRole.REVIEWER, OfficerRole.ADMIN):
        raise PermissionError("Only a reviewing officer or admin may forward a draft to approval.")

    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    if draft.status != DraftStatus.SUBMITTED:
        raise InvalidWorkflowStateError(
            f"Draft must be 'submitted' to forward to approval (currently '{draft.status.value}')."
        )

    version_before = draft.version
    content_changed = new_content is not None and new_content != draft.content
    if content_changed:
        session.add(
            DraftVersion(
                generated_draft_id=draft.generated_draft_id,
                version_number=draft.version,
                content=draft.content,
                content_plain=draft.content_plain,
                content_sha256=hash_content(draft.content),
                edited_by=officer_id,
                change_note="Reviewing officer's edits before forwarding to approval",
            )
        )
        draft.content = new_content
        draft.content_plain = new_content_plain if new_content_plain is not None else new_content
        draft.version += 1
        decision = "edited_and_forwarded"
    else:
        decision = "forwarded_unchanged"

    draft.status = DraftStatus.REVIEWED
    await session.flush()
    await workflow_repo.create_event(
        session,
        draft_id=draft.generated_draft_id,
        from_status=DraftStatus.SUBMITTED.value,
        to_status=DraftStatus.REVIEWED.value,
        actor_id=officer_id,
        actor_role=officer_role.value,
        content_version_before=version_before,
        content_version_after=draft.version,
        decision=decision,
        note=None,
    )
    return draft


async def approve_draft(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    admin_id: uuid.UUID,
    admin_role: OfficerRole,
    decision: str,
) -> Optional[GeneratedDraft]:
    """Admin only. Draft must be 'reviewed'.

    decision='accept_reviewer_version': content stays as the reviewer
    left it. decision='keep_original': content is reverted to the
    Drafting Officer's originally-submitted version for THIS review
    cycle (found via the most recent 'submitted' workflow event, so a
    prior returned-and-resubmitted cycle's submission is never used) —
    a new draft_versions snapshot records the reversion itself, so it's
    also auditable. Either way, this is where the draft becomes
    immutable (see patch_draft_content).

    `decision` here is the present-tense request value
    ('accept_reviewer_version' | 'keep_original'); the
    draft_workflow_events.decision column stores the past-tense audit
    record ('accepted_reviewer_version' | 'kept_original') — see
    _EVENT_DECISION below for the mapping."""
    if admin_role != OfficerRole.ADMIN:
        raise PermissionError("Only an approving authority (admin) may approve a draft.")
    if decision not in ("accept_reviewer_version", "keep_original"):
        raise ValueError(f"Unknown approval decision '{decision}'.")

    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    if draft.status != DraftStatus.REVIEWED:
        raise InvalidWorkflowStateError(
            f"Draft must be 'reviewed' to approve (currently '{draft.status.value}')."
        )

    version_before = draft.version

    if decision == "keep_original":
        events = await workflow_repo.get_workflow_history(session, draft.generated_draft_id)
        submit_event = next((e for e in events if e.decision == "submitted"), None)
        submitted_version_number = submit_event.content_version_after if submit_event else version_before
        orig_content, _orig_plain, _orig_hash = await get_version_snapshot(
            session, draft, submitted_version_number
        )
        session.add(
            DraftVersion(
                generated_draft_id=draft.generated_draft_id,
                version_number=draft.version,
                content=draft.content,
                content_plain=draft.content_plain,
                content_sha256=hash_content(draft.content),
                edited_by=admin_id,
                change_note="Reverted to the drafting officer's originally submitted version on approval",
            )
        )
        draft.content = orig_content
        # content_plain has no historical mirror before this migration's
        # backfill was written for every row going forward; best-effort
        # fallback keeps the field non-empty rather than blanking it.
        draft.content_plain = _orig_plain
        draft.version += 1

    draft.status = DraftStatus.APPROVED
    await session.flush()
    await workflow_repo.create_event(
        session,
        draft_id=draft.generated_draft_id,
        from_status=DraftStatus.REVIEWED.value,
        to_status=DraftStatus.APPROVED.value,
        actor_id=admin_id,
        actor_role=admin_role.value,
        content_version_before=version_before,
        content_version_after=draft.version,
        decision=_EVENT_DECISION[decision],
        note=None,
    )
    return draft


async def return_draft(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    officer_id: uuid.UUID,
    officer_role: OfficerRole,
    reason: str,
) -> Optional[GeneratedDraft]:
    """Reviewer or admin. Draft must be 'submitted' or 'reviewed'.

    Goes straight back to 'draft' (rather than lingering in the
    'returned' status) with returned_reason set, so the drafting
    officer's own view can surface it immediately — see
    db.models.DraftStatus for why this is the simpler, chosen path."""
    if officer_role not in (OfficerRole.REVIEWER, OfficerRole.ADMIN):
        raise PermissionError("Only a reviewing officer or admin may return a draft.")

    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None
    if draft.status not in (DraftStatus.SUBMITTED, DraftStatus.REVIEWED):
        raise InvalidWorkflowStateError(
            f"Draft must be 'submitted' or 'reviewed' to return (currently '{draft.status.value}')."
        )

    from_status = draft.status.value
    draft.status = DraftStatus.DRAFT
    draft.returned_reason = reason
    await session.flush()
    await workflow_repo.create_event(
        session,
        draft_id=draft.generated_draft_id,
        from_status=from_status,
        to_status=DraftStatus.DRAFT.value,
        actor_id=officer_id,
        actor_role=officer_role.value,
        content_version_before=draft.version,
        content_version_after=draft.version,
        decision="returned",
        note=reason,
    )
    return draft


def _workflow_queue_conflict_counts_subquery():
    return (
        select(
            DraftConflict.generated_draft_id.label("draft_id"),
            func.count().label("cnt"),
        )
        .where(DraftConflict.is_dismissed == False)  # noqa: E712
        .group_by(DraftConflict.generated_draft_id)
        .subquery()
    )


async def list_review_queue(
    session: AsyncSession, *, page: int, page_size: int, department: Optional[str] = None
) -> tuple[list[tuple[GeneratedDraft, int]], int]:
    """Drafts with status='submitted' — the Reviewing Officer's queue.
    One aggregate query for unresolved-conflict counts — no N+1."""
    conflict_counts = _workflow_queue_conflict_counts_subquery()
    stmt = (
        select(GeneratedDraft, func.coalesce(conflict_counts.c.cnt, 0))
        .outerjoin(conflict_counts, GeneratedDraft.generated_draft_id == conflict_counts.c.draft_id)
        .where(GeneratedDraft.status == DraftStatus.SUBMITTED)
        .options(selectinload(GeneratedDraft.officer))
    )
    count_stmt = select(func.count()).select_from(GeneratedDraft).where(
        GeneratedDraft.status == DraftStatus.SUBMITTED
    )
    if department:
        stmt = stmt.where(GeneratedDraft.department == department)
        count_stmt = count_stmt.where(GeneratedDraft.department == department)

    stmt = stmt.order_by(GeneratedDraft.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows], total


async def list_approval_queue(
    session: AsyncSession, *, page: int, page_size: int, department: Optional[str] = None
) -> tuple[list[tuple[GeneratedDraft, int, Optional[str]]], int]:
    """Drafts with status='reviewed' — the Approving Authority's queue.
    Reviewer names are resolved with one extra batched query for the
    whole page (see workflow_repo.get_latest_reviewer_names), not one
    per row, since there's no direct FK from a draft to "who reviewed
    it" (only the workflow event trail)."""
    conflict_counts = _workflow_queue_conflict_counts_subquery()
    stmt = (
        select(GeneratedDraft, func.coalesce(conflict_counts.c.cnt, 0))
        .outerjoin(conflict_counts, GeneratedDraft.generated_draft_id == conflict_counts.c.draft_id)
        .where(GeneratedDraft.status == DraftStatus.REVIEWED)
        .options(selectinload(GeneratedDraft.officer))
    )
    count_stmt = select(func.count()).select_from(GeneratedDraft).where(
        GeneratedDraft.status == DraftStatus.REVIEWED
    )
    if department:
        stmt = stmt.where(GeneratedDraft.department == department)
        count_stmt = count_stmt.where(GeneratedDraft.department == department)

    stmt = stmt.order_by(GeneratedDraft.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).all()
    draft_rows = [(r[0], r[1]) for r in rows]

    reviewer_names = await workflow_repo.get_latest_reviewer_names(
        session, [d.generated_draft_id for d, _ in draft_rows]
    )
    return [(d, count, reviewer_names.get(d.generated_draft_id)) for d, count in draft_rows], total


async def get_approval_view(session: AsyncSession, draft_id: uuid.UUID) -> Optional[dict]:
    """
    Everything the Approving Authority's review screen needs in one
    call: the version the Drafting Officer submitted, the version the
    Reviewing Officer forwarded (may be identical), both content_sha256
    values, and the full workflow event trail. The diff between the two
    versions is computed by the caller (routes layer) via diffing.py —
    that's presentation logic, not a data-access concern.
    """
    draft = await get_draft_by_id(session, draft_id)
    if draft is None:
        return None

    events = await workflow_repo.get_workflow_history(session, draft_id)
    submit_event = next((e for e in events if e.decision == "submitted"), None)
    review_event = next(
        (e for e in events if e.decision in ("edited_and_forwarded", "forwarded_unchanged")), None
    )

    submitted_version_number = submit_event.content_version_after if submit_event else draft.version
    reviewed_version_number = review_event.content_version_after if review_event else draft.version

    submitted_content, submitted_plain, submitted_hash = await get_version_snapshot(
        session, draft, submitted_version_number
    )
    reviewed_content, reviewed_plain, reviewed_hash = await get_version_snapshot(
        session, draft, reviewed_version_number
    )

    return {
        "draft": draft,
        "submitted_version_number": submitted_version_number,
        "submitted_content": submitted_content,
        "submitted_content_plain": submitted_plain,
        "submitted_content_sha256": submitted_hash,
        "reviewed_version_number": reviewed_version_number,
        "reviewed_content": reviewed_content,
        "reviewed_content_plain": reviewed_plain,
        "reviewed_content_sha256": reviewed_hash,
        "events": events,
        "submitted_by_name": draft.officer.name if draft.officer else None,
        "reviewed_by_name": review_event.actor.name if review_event and review_event.actor else None,
    }
