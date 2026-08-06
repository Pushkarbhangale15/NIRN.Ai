"""
db/repositories/workflow.py — SQL RULE: every query below is built with
select()/insert() from SQLAlchemy. Never an f-string, never string
concatenation. See backend/README.md, "SQL injection prevention".

draft_workflow_events is the audit trail for the three-tier draft
approval chain (Drafting Officer -> Reviewing Officer -> Approving
Authority). APPEND-ONLY: no function in this file ever updates or
deletes a row here — every handoff is a permanent record, by design.

The actual status-transition logic (validating the draft is in the
right state, snapshotting content, updating GeneratedDraft.status)
lives in db/repositories/drafts.py, which calls create_event() below in
the same transaction/session — this file only owns reading and writing
the event rows themselves.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import DraftWorkflowEvent


async def create_event(
    session: AsyncSession,
    *,
    draft_id: uuid.UUID,
    from_status: str,
    to_status: str,
    actor_id: uuid.UUID,
    actor_role: str,
    content_version_before: Optional[int],
    content_version_after: Optional[int],
    decision: Optional[str],
    note: Optional[str],
) -> DraftWorkflowEvent:
    event = DraftWorkflowEvent(
        generated_draft_id=draft_id,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        content_version_before=content_version_before,
        content_version_after=content_version_after,
        decision=decision,
        note=note,
    )
    session.add(event)
    await session.flush()
    return event


async def get_workflow_history(session: AsyncSession, draft_id: uuid.UUID) -> Sequence[DraftWorkflowEvent]:
    """Most-recent-first, with the acting officer eager-loaded so
    .actor_name never triggers a lazy load outside an async context."""
    stmt = (
        select(DraftWorkflowEvent)
        .where(DraftWorkflowEvent.generated_draft_id == draft_id)
        .options(selectinload(DraftWorkflowEvent.actor))
        .order_by(DraftWorkflowEvent.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def get_latest_reviewer_names(
    session: AsyncSession, draft_ids: Sequence[uuid.UUID]
) -> dict:
    """
    Batch lookup of "who most recently forwarded this draft to
    approval" for a page of draft ids — one query for the whole page,
    not one per row (used by the Approving Authority's queue, which
    otherwise has no direct FK to a reviewer).
    """
    if not draft_ids:
        return {}
    stmt = (
        select(DraftWorkflowEvent)
        .where(
            DraftWorkflowEvent.generated_draft_id.in_(draft_ids),
            DraftWorkflowEvent.decision.in_(["edited_and_forwarded", "forwarded_unchanged"]),
        )
        .options(selectinload(DraftWorkflowEvent.actor))
        .order_by(DraftWorkflowEvent.created_at.desc())
    )
    events = (await session.execute(stmt)).scalars().all()
    names: dict = {}
    for event in events:
        if event.generated_draft_id not in names:
            names[event.generated_draft_id] = event.actor.name if event.actor else None
    return names
