"""
workflow_routes.py — three-tier draft approval workflow: Drafting
Officer -> Reviewing Officer -> Approving Authority.

Reuses the existing officer_role enum (officer/reviewer/admin) with
display-label mapping only (see role_labels.py) — no new role values.

SQL RULE: this file never builds a query itself — every read/write goes
through db.repositories.drafts / db.repositories.workflow. See
backend/README.md, "SQL injection prevention".

Every route below wraps repository calls in try/except and returns
clean JSON — never a 500 traceback (this runs live in a demo). Ownership
and role checks are enforced a second time inside the repository layer
itself (see db/repositories/drafts.py), independent of the Depends()
used here.
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import diffing
from config import settings
from db.base import get_session
from db.integrity import verify_content
from db.models import Officer, OfficerRole
from db.repositories import drafts as drafts_repo
from db.repositories import workflow as workflow_repo
from deps import get_current_officer, require_admin, require_reviewer_or_admin
from role_labels import role_display_label
from schemas import (
    ApprovalViewResponse,
    ApproveDraftRequest,
    DiffSegmentOut,
    DraftDiffResponse,
    ForwardToApprovalRequest,
    PaginatedWorkflowQueue,
    ReturnDraftRequest,
    VerifyVersionResponse,
    WorkflowActionResponse,
    WorkflowEventOut,
    WorkflowQueueItem,
)

logger = logging.getLogger("nirn.workflow")

router = APIRouter()


def _ensure_can_access_draft(draft_row, officer: Officer) -> None:
    if officer.role in (OfficerRole.ADMIN, OfficerRole.REVIEWER):
        return
    if draft_row.drafted_by != officer.officer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this draft.")


def _to_event_schema(event) -> WorkflowEventOut:
    return WorkflowEventOut(
        event_id=event.event_id,
        from_status=event.from_status,
        to_status=event.to_status,
        actor_id=event.actor_id,
        actor_name=event.actor_name,
        actor_role=event.actor_role,
        content_version_before=event.content_version_before,
        content_version_after=event.content_version_after,
        decision=event.decision,
        note=event.note,
        created_at=event.created_at,
    )


def _to_queue_item(draft, unresolved_count: int, reviewer_name: Optional[str] = None) -> WorkflowQueueItem:
    return WorkflowQueueItem(
        generated_draft_id=draft.generated_draft_id,
        gr_number=draft.gr_number,
        title=draft.title,
        department=draft.department,
        status=draft.status.value if hasattr(draft.status, "value") else draft.status,
        drafted_by_name=draft.officer.name if draft.officer else None,
        reviewed_by_name=reviewer_name,
        unresolved_conflict_count=unresolved_count,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _to_diff_schema(draft_id: uuid.UUID, from_version: int, to_version: int, before_plain: str,
                     after_plain: str, before_hash: str, after_hash: str) -> DraftDiffResponse:
    segments = diffing.compute_diff(before_plain, after_plain)
    summary = diffing.diff_summary(segments)
    return DraftDiffResponse(
        draft_id=draft_id,
        from_version=from_version,
        to_version=to_version,
        unchanged=(from_version == to_version) or (before_plain == after_plain),
        segments=[DiffSegmentOut(type=s["type"], text=s["text"]) for s in segments],
        additions=summary["additions"],
        deletions=summary["deletions"],
        from_content_sha256=before_hash,
        to_content_sha256=after_hash,
    )


# =====================================================================
# Drafting Officer -> Reviewing Officer
# =====================================================================

@router.post(
    "/api/drafts/{draft_id}/submit-for-review", response_model=WorkflowActionResponse, tags=["workflow"]
)
async def submit_for_review(
    draft_id: uuid.UUID,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> WorkflowActionResponse:
    try:
        draft = await drafts_repo.submit_for_review(
            session, draft_id, officer_id=officer.officer_id, officer_role=officer.role
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except drafts_repo.InvalidWorkflowStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("Database error submitting draft %s for review", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    logger.info(
        "Draft %s submitted for review by %s (%s)",
        draft_id, officer.name, role_display_label(officer.role),
    )
    return WorkflowActionResponse(
        generated_draft_id=draft.generated_draft_id,
        status=draft.status.value,
        version=draft.version,
    )


@router.get("/api/review-queue", response_model=PaginatedWorkflowQueue, tags=["workflow"])
async def review_queue(
    department: Optional[str] = Query(None, max_length=160),
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
    officer: Officer = Depends(require_reviewer_or_admin),
    session: AsyncSession = Depends(get_session),
) -> PaginatedWorkflowQueue:
    size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    try:
        rows, total = await drafts_repo.list_review_queue(
            session, page=page, page_size=size, department=department
        )
    except SQLAlchemyError:
        logger.exception("Database error listing review queue")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    items = [_to_queue_item(d, count) for d, count in rows]
    return PaginatedWorkflowQueue(items=items, total=total, page=page, page_size=size)


@router.post(
    "/api/drafts/{draft_id}/forward-to-approval", response_model=WorkflowActionResponse, tags=["workflow"]
)
async def forward_to_approval(
    draft_id: uuid.UUID,
    payload: ForwardToApprovalRequest,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> WorkflowActionResponse:
    try:
        draft = await drafts_repo.forward_to_approval(
            session,
            draft_id,
            officer_id=officer.officer_id,
            officer_role=officer.role,
            new_content=payload.content,
            new_content_plain=payload.content_plain,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except drafts_repo.InvalidWorkflowStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("Database error forwarding draft %s to approval", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    logger.info(
        "Draft %s forwarded to approval by %s (%s)",
        draft_id, officer.name, role_display_label(officer.role),
    )
    return WorkflowActionResponse(
        generated_draft_id=draft.generated_draft_id,
        status=draft.status.value,
        version=draft.version,
    )


# =====================================================================
# Reviewing Officer -> Approving Authority
# =====================================================================

@router.get("/api/approval-queue", response_model=PaginatedWorkflowQueue, tags=["workflow"])
async def approval_queue(
    department: Optional[str] = Query(None, max_length=160),
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PaginatedWorkflowQueue:
    size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    try:
        rows, total = await drafts_repo.list_approval_queue(
            session, page=page, page_size=size, department=department
        )
    except SQLAlchemyError:
        logger.exception("Database error listing approval queue")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    items = [_to_queue_item(d, count, reviewer_name) for d, count, reviewer_name in rows]
    return PaginatedWorkflowQueue(items=items, total=total, page=page, page_size=size)


@router.get(
    "/api/drafts/{draft_id}/approval-view", response_model=ApprovalViewResponse, tags=["workflow"]
)
async def approval_view(
    draft_id: uuid.UUID,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ApprovalViewResponse:
    try:
        view = await drafts_repo.get_approval_view(session, draft_id)
    except SQLAlchemyError:
        logger.exception("Database error loading approval view for draft %s", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    if view is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    draft = view["draft"]
    diff_resp = _to_diff_schema(
        draft.generated_draft_id,
        view["submitted_version_number"], view["reviewed_version_number"],
        view["submitted_content_plain"], view["reviewed_content_plain"],
        view["submitted_content_sha256"], view["reviewed_content_sha256"],
    )
    return ApprovalViewResponse(
        generated_draft_id=draft.generated_draft_id,
        gr_number=draft.gr_number,
        title=draft.title,
        department=draft.department,
        status=draft.status.value,
        submitted_by_name=view["submitted_by_name"],
        reviewed_by_name=view["reviewed_by_name"],
        submitted_version_number=view["submitted_version_number"],
        submitted_content=view["submitted_content"],
        submitted_content_plain=view["submitted_content_plain"],
        submitted_content_sha256=view["submitted_content_sha256"],
        reviewed_version_number=view["reviewed_version_number"],
        reviewed_content=view["reviewed_content"],
        reviewed_content_plain=view["reviewed_content_plain"],
        reviewed_content_sha256=view["reviewed_content_sha256"],
        diff=diff_resp,
        workflow_history=[_to_event_schema(e) for e in view["events"]],
        returned_reason=draft.returned_reason,
    )


@router.post("/api/drafts/{draft_id}/approve", response_model=WorkflowActionResponse, tags=["workflow"])
async def approve_draft(
    draft_id: uuid.UUID,
    payload: ApproveDraftRequest,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> WorkflowActionResponse:
    try:
        draft = await drafts_repo.approve_draft(
            session,
            draft_id,
            admin_id=admin.officer_id,
            admin_role=admin.role,
            decision=payload.decision,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except drafts_repo.InvalidWorkflowStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("Database error approving draft %s", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    logger.info(
        "Draft %s approved (%s) by %s (%s)",
        draft_id, payload.decision, admin.name, role_display_label(admin.role),
    )
    return WorkflowActionResponse(
        generated_draft_id=draft.generated_draft_id,
        status=draft.status.value,
        version=draft.version,
    )


# =====================================================================
# Return-for-rework (reviewer or admin -> back to Drafting Officer)
# =====================================================================

@router.post("/api/drafts/{draft_id}/return", response_model=WorkflowActionResponse, tags=["workflow"])
async def return_draft(
    draft_id: uuid.UUID,
    payload: ReturnDraftRequest,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> WorkflowActionResponse:
    try:
        draft = await drafts_repo.return_draft(
            session,
            draft_id,
            officer_id=officer.officer_id,
            officer_role=officer.role,
            reason=payload.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except drafts_repo.InvalidWorkflowStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("Database error returning draft %s", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    logger.info(
        "Draft %s returned for rework by %s (%s)",
        draft_id, officer.name, role_display_label(officer.role),
    )
    return WorkflowActionResponse(
        generated_draft_id=draft.generated_draft_id,
        status=draft.status.value,
        version=draft.version,
    )


# =====================================================================
# Shared: history / hash verification / diff — available to anyone with
# access to the draft (owner, reviewer, admin), not just the two ends
# of whichever handoff is active.
# =====================================================================

@router.get(
    "/api/drafts/{draft_id}/workflow-history", response_model=List[WorkflowEventOut], tags=["workflow"]
)
async def workflow_history(
    draft_id: uuid.UUID,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[WorkflowEventOut]:
    row = await drafts_repo.get_draft_by_id(session, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    _ensure_can_access_draft(row, officer)

    try:
        events = await workflow_repo.get_workflow_history(session, draft_id)
    except SQLAlchemyError:
        logger.exception("Database error loading workflow history for draft %s", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    return [_to_event_schema(e) for e in events]


@router.get(
    "/api/drafts/{draft_id}/versions/{version_number}/verify",
    response_model=VerifyVersionResponse,
    tags=["workflow"],
)
async def verify_version(
    draft_id: uuid.UUID,
    version_number: int,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> VerifyVersionResponse:
    row = await drafts_repo.get_draft_by_id(session, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    _ensure_can_access_draft(row, officer)

    try:
        content, _plain, stored_hash = await drafts_repo.get_version_snapshot(session, row, version_number)
    except ValueError:
        raise HTTPException(
            status_code=404, detail=f"Version {version_number} does not exist for this draft."
        )
    except SQLAlchemyError:
        logger.exception("Database error verifying draft %s version %s", draft_id, version_number)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return VerifyVersionResponse(verified=verify_content(content, stored_hash), hash=stored_hash)


@router.get("/api/drafts/{draft_id}/diff", response_model=DraftDiffResponse, tags=["workflow"])
async def draft_diff(
    draft_id: uuid.UUID,
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1),
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> DraftDiffResponse:
    row = await drafts_repo.get_draft_by_id(session, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    _ensure_can_access_draft(row, officer)

    try:
        _, before_plain, before_hash = await drafts_repo.get_version_snapshot(session, row, from_version)
        _, after_plain, after_hash = await drafts_repo.get_version_snapshot(session, row, to_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("Database error diffing draft %s", draft_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return _to_diff_schema(draft_id, from_version, to_version, before_plain, after_plain, before_hash, after_hash)
