"""
routes.py — every endpoint in NIRN.Ai.

Coming from Express, the mapping is:
    APIRouter()                 ->  express.Router()
    @router.post("/x")          ->  router.post("/x", handler)
    HTTPException(404, detail)  ->  res.status(404).json({...})

The difference in your favour: FastAPI validates the request body
against the schema automatically and returns 422 with a field-by-field
explanation, so you never write manual field checks.

RULE: every query against Postgres lives in db/repositories/*.py and
uses the SQLAlchemy ORM or select() — never string-built SQL. Route
handlers below only call repository functions (directly, or via the
thin async wrappers in store.py).
"""

import logging
import re
import secrets
import time
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

import deps
import llm
import prompts
import references
import retrieval
import store
import template_rules
import template_rules_marathi
from conflict_detection import detect_cross_department_conflicts
from conflict_detection.models import ConflictReportItem
from db.base import get_session
from db.models import Officer
from db.repositories import conflicts as conflicts_repo
from db.repositories import officers as officers_repo
from db.security import create_access_token, hash_password, verify_password
from document_extraction import extract_document
from document_extraction.errors import ExtractionError, OcrUnavailableError, UnsupportedFileTypeError
from lookup import get_adapter
from config import MAX_UPLOAD_SIZE_BYTES, OCR_LOW_CONFIDENCE_THRESHOLD, settings
from rate_limit import limiter
from profiler import perf, PROFILING_ENABLED
from schemas import (
    Language,
    AnalysisReport,
    AnalysisSummary,
    ConflictDetectedBy,
    ConflictDraftBrief,
    ConflictDraftDetail,
    ConflictHit,
    ConflictLookupOut,
    ConflictSeverity,
    ConflictWithDraftOut,
    CorpusSearchResponse,
    DismissConflictRequest,
    DraftConflictOut,
    DraftHistoryItem,
    DraftSource,
    FullOCRResponse,
    LoginRequest,
    OfficerCreate,
    OfficerEdit,
    OfficerOut,
    OfficerRole,
    OfficialSourceResponse,
    DraftCreate,
    PaginatedConflicts,
    PaginatedDraftHistory,
    PaginatedOfficers,
    PersistedDraftCreate,
    PersistedDraftDetail,
    PersistedDraftOut,
    PersistedDraftStatus,
    PersistedDraftUpdate,
    ReferenceHit,
    ReferenceScript,
    ResetPasswordResponse,
    Severity,
    TemplateIssue,
    TermMapping,
    TokenResponse,
    UploadDraftResponse,
    ChatRequest,
    ChatResponse,
    DraftGenerateRequest,
    DraftGenerateResponse,
    ComparisonRequest,
    ComparisonResponse,
    ClauseExplanationRequest,
    ClauseExplanationResponse,
)

router = APIRouter()
logger = logging.getLogger(settings.APP_NAME)


# =====================================================================
# Auth
#
# There is no public self-registration. Officer accounts are created by
# an admin only — see the /api/officers* section below. This is a
# deliberate access-control decision, not an oversight: the only path
# that creates an Officer row is admin_create_officer, which requires
# deps.require_admin AND has the caller's role re-checked inside
# officers_repo.create_officer_as_admin (defence in depth).
# =====================================================================

@router.post("/api/auth/login", response_model=TokenResponse, tags=["auth"])
@limiter.limit("5/minute")
async def login(
    request: Request, payload: LoginRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials")

    officer = await officers_repo.get_by_login_id(session, payload.login_id)
    # Same generic error whether the login_id is unknown or the password is
    # wrong — a different message here would let an attacker enumerate
    # valid officer ids (PART 3).
    if officer is None or not officer.is_active:
        raise generic_error
    if not verify_password(payload.password, officer.password_hash):
        raise generic_error

    await officers_repo.touch_last_login(session, officer.officer_id)
    token = create_access_token(officer.officer_id, officer.role)
    return TokenResponse(access_token=token, officer=OfficerOut.model_validate(officer))


@router.get("/api/officers/me", response_model=OfficerOut, tags=["auth"])
async def get_me(current: Officer = Depends(deps.get_current_officer)) -> OfficerOut:
    return OfficerOut.model_validate(current)


# =====================================================================
# Admin — officer management. Every route here requires role='admin',
# not just 'reviewer' (see deps.require_admin). This is the ONLY place
# officer accounts get created (see the Auth section above).
# =====================================================================

@router.get("/api/officers", response_model=PaginatedOfficers, tags=["admin"])
async def admin_list_officers(
    search: Optional[str] = Query(default=None, max_length=120, description="Matches name or login_id"),
    role: Optional[OfficerRole] = Query(default=None),
    department: Optional[str] = Query(default=None, max_length=160),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> PaginatedOfficers:
    try:
        officers, total = await officers_repo.list_officers(
            session,
            search=search,
            role=role.value if role else None,
            department=department,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return PaginatedOfficers(
        items=[OfficerOut.model_validate(o) for o in officers], total=total, limit=limit, offset=offset,
    )


@router.post("/api/officers", response_model=OfficerOut,
             status_code=status.HTTP_201_CREATED, tags=["admin"])
async def admin_create_officer(
    payload: OfficerCreate,
    admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    """The only endpoint that creates officer accounts. Unlike a public
    self-registration endpoint (which this app deliberately does not
    have), the caller here is already authenticated as admin, so `role`
    on the payload is honoured as-is."""
    existing = await officers_repo.get_by_login_id(session, payload.login_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="login_id already registered")

    try:
        officer = await officers_repo.create_officer_as_admin(
            session,
            creating_officer_role=admin.role,
            name=payload.name,
            login_id=payload.login_id,
            password_hash=hash_password(payload.password),
            department=payload.department,
            designation=payload.designation,
            role=payload.role.value,
        )
    except officers_repo.AdminRequiredError:
        # Belt-and-braces: deps.require_admin already rejected non-admins
        # before this ran. This is the repository's own defence-in-depth
        # check firing independently of the route dependency.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create officer")

    return OfficerOut.model_validate(officer)


@router.patch("/api/officers/{officer_id}", response_model=OfficerOut, tags=["admin"])
async def admin_edit_officer(
    officer_id: UUID,
    payload: OfficerEdit,
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    """login_id is not editable here by design — see OfficerEdit."""
    if payload.role is not None and payload.role != OfficerRole.ADMIN:
        target = await officers_repo.get_by_id(session, officer_id)
        if target is not None and target.role == "admin" and target.is_active:
            # Demoting an admin (including self-demotion, which nothing
            # else here blocks) can zero out active admins just as
            # surely as deactivating or deleting the last one — same
            # guard, same lock-based race protection.
            remaining = await officers_repo.count_active_admins(session, exclude_officer_id=officer_id, lock=True)
            if remaining == 0:
                raise HTTPException(status_code=400, detail="Cannot demote the last active admin")

    officer = await officers_repo.update_officer(
        session,
        officer_id,
        name=payload.name,
        department=payload.department,
        designation=payload.designation,
        role=payload.role.value if payload.role else None,
    )
    if officer is None:
        raise HTTPException(status_code=404, detail=f"Officer {officer_id} not found")
    return OfficerOut.model_validate(officer)


@router.patch("/api/officers/{officer_id}/deactivate", response_model=OfficerOut, tags=["admin"])
async def admin_deactivate_officer(
    officer_id: UUID,
    admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    if officer_id == admin.officer_id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    target = await officers_repo.get_by_id(session, officer_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Officer {officer_id} not found")

    if target.role == "admin" and target.is_active:
        # lock=True: two concurrent requests deactivating different
        # admins can't both read "1 remaining" and both proceed.
        remaining = await officers_repo.count_active_admins(session, exclude_officer_id=officer_id, lock=True)
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active admin")

    officer = await officers_repo.set_active(session, officer_id, False)
    return OfficerOut.model_validate(officer)


@router.patch("/api/officers/{officer_id}/activate", response_model=OfficerOut, tags=["admin"])
async def admin_activate_officer(
    officer_id: UUID,
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    officer = await officers_repo.set_active(session, officer_id, True)
    if officer is None:
        raise HTTPException(status_code=404, detail=f"Officer {officer_id} not found")
    return OfficerOut.model_validate(officer)


@router.post("/api/officers/{officer_id}/reset-password", response_model=ResetPasswordResponse, tags=["admin"])
async def admin_reset_password(
    officer_id: UUID,
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> ResetPasswordResponse:
    # 16 URL-safe chars comfortably clears the 10-char Password minimum
    # and never needs escaping when shown/copied in the admin UI.
    temporary_password = secrets.token_urlsafe(12)
    officer = await officers_repo.set_password(
        session, officer_id, hash_password(temporary_password), must_change_password=True
    )
    if officer is None:
        raise HTTPException(status_code=404, detail=f"Officer {officer_id} not found")
    return ResetPasswordResponse(temporary_password=temporary_password, must_change_password=True)


# Officer accounts are never hard-deleted — see officers_repo (no
# delete_officer function) and the note on GeneratedDraft.drafted_by
# (ON DELETE RESTRICT). Deactivate is the only removal path, which
# blocks login while preserving every draft they authored.


# =====================================================================
# Drafts — Postgres-backed, JWT-protected, owner-scoped
# =====================================================================

async def _load_draft(session: AsyncSession, draft_id: UUID, current: Officer, *, with_children: bool = False):
    """Fetch a draft the current officer is allowed to see, or raise a clean 404.
    Ownership is also enforced inside drafts_repo (defence in depth)."""
    draft = await store.get_draft(
        session,
        draft_id,
        officer_id=current.officer_id,
        privileged=deps.is_privileged(current),
        with_children=with_children,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    return draft


@router.post("/api/drafts", response_model=PersistedDraftOut,
             status_code=status.HTTP_201_CREATED, tags=["drafts"])
async def create_draft(
    payload: PersistedDraftCreate,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PersistedDraftOut:
    draft = await store.create_draft(
        session,
        title=payload.title,
        language=payload.language.value,
        drafted_by=current.officer_id,
        content=payload.content,
        department=payload.department,
        content_plain=payload.content_plain,
        brief=payload.brief,
        gr_number=payload.gr_number,
        template_score=payload.template_score,
    )
    return PersistedDraftOut.model_validate(draft)


@router.get("/api/drafts", response_model=PaginatedDraftHistory, tags=["drafts"])
async def list_drafts(
    department: Optional[str] = Query(default=None, max_length=160),
    status_filter: Optional[PersistedDraftStatus] = Query(default=None, alias="status"),
    source_filter: Optional[DraftSource] = Query(default=None, alias="source"),
    search: Optional[str] = Query(default=None, max_length=200, description="Free-text search: title + content"),
    author_id: Optional[UUID] = Query(default=None, description="Admin/reviewer only: narrow to one officer's drafts"),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PaginatedDraftHistory:
    # sort_by is checked against a hardcoded allowlist inside the repo —
    # column names can never come from raw user input (PART 2 rule 4).
    try:
        rows, total = await store.list_drafts(
            session,
            officer_id=current.officer_id,
            privileged=deps.is_privileged(current),
            department=department,
            status=status_filter.value if status_filter else None,
            source=source_filter.value if source_filter else None,
            search=search,
            author_id=author_id,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # rows is [(GeneratedDraft, unresolved_conflict_count), ...] — the
    # count came from one aggregate query in the repo, not a per-row loop.
    items = []
    for draft, conflict_count in rows:
        item = DraftHistoryItem.model_validate(draft)
        item.conflict_count = conflict_count
        item.officer_name = draft.officer.name if draft.officer else None
        item.officer_login_id = draft.officer.login_id if draft.officer else None
        items.append(item)

    return PaginatedDraftHistory(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/drafts/{draft_id}", response_model=PersistedDraftDetail, tags=["drafts"])
async def get_draft(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PersistedDraftDetail:
    draft = await _load_draft(session, draft_id, current, with_children=True)
    return PersistedDraftDetail.model_validate(draft)


@router.patch("/api/drafts/{draft_id}", response_model=PersistedDraftOut, tags=["drafts"])
async def patch_draft(
    draft_id: UUID,
    payload: PersistedDraftUpdate,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PersistedDraftOut:
    """Update a draft's content. Snapshots the previous version into
    draft_versions first, so every edit is auditable."""
    updated = await store.update_draft_content(
        session,
        draft_id,
        officer_id=current.officer_id,
        privileged=deps.is_privileged(current),
        new_content=payload.content,
        edited_by=current.officer_id,
        change_note=payload.change_note,
        new_content_plain=payload.content_plain,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    return PersistedDraftOut.model_validate(updated)


@router.patch("/api/drafts/{draft_id}/save", response_model=PersistedDraftOut, tags=["drafts"])
async def save_draft(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PersistedDraftOut:
    """Confirms a freshly generated/uploaded draft is worth keeping —
    flips is_saved so it starts showing up in GET /api/drafts (History).
    See the is_saved filter in db/repositories/drafts.py."""
    draft = await store.save_draft(
        session, draft_id, officer_id=current.officer_id, privileged=deps.is_privileged(current)
    )
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    return PersistedDraftOut.model_validate(draft)


@router.post("/api/drafts/upload", response_model=UploadDraftResponse,
             status_code=status.HTTP_201_CREATED, tags=["drafts"])
async def upload_draft(
    file: UploadFile = File(...),
    department: str = Form(..., min_length=2, max_length=160),
    language: Language = Form(...),
    title: Optional[str] = Form(default=None, max_length=400),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> UploadDraftResponse:
    """
    Upload an existing GR (Word/PDF/scan/photo) and load it into a draft.

    Routes to the cheapest, most accurate extraction path for the real
    file type (sniffed by content, not filename) — OCR is the last
    resort, not the default. Runs in a threadpool since OCR is
    CPU-bound and would otherwise block the event loop for every other
    request during a demo. Never stores the uploaded binary — the text
    is extracted, persisted, and the original bytes are discarded.
    """
    content = await file.read()

    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large — the maximum upload size is {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        result = await run_in_threadpool(extract_document, content)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except OcrUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Unhandled error extracting uploaded file %s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process this file. Try a different format or a clearer scan.",
        )

    if not result.plain_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text was found in this file. If it's a scanned document, try a clearer, higher-resolution scan.",
        )

    detected_script = ReferenceScript.DEVANAGARI if _is_devanagari(result.plain_text) else ReferenceScript.LATIN
    draft_title = (title or file.filename or "Uploaded GR")[:400]

    draft = await store.create_draft(
        session,
        title=draft_title,
        language=language.value,
        drafted_by=current.officer_id,
        content=result.html,
        department=department,
        content_plain=result.plain_text,
        brief=None,
        source="uploaded",
        original_filename=(file.filename or None),
    )

    low_confidence = result.ocr_confidence is not None and result.ocr_confidence < OCR_LOW_CONFIDENCE_THRESHOLD

    return UploadDraftResponse(
        generated_draft_id=draft.generated_draft_id,
        title=draft.title,
        content=draft.content,
        department=draft.department,
        language=Language(draft.language),
        gr_number=draft.gr_number,
        detected_script=detected_script,
        ocr_confidence=result.ocr_confidence,
        low_confidence=low_confidence,
    )


@router.patch("/api/conflicts/{conflict_id}/dismiss", response_model=DraftConflictOut, tags=["conflicts"])
async def dismiss_conflict(
    conflict_id: UUID,
    payload: DismissConflictRequest,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> DraftConflictOut:
    conflict = await conflicts_repo.dismiss_conflict(
        session,
        conflict_id,
        officer_id=current.officer_id,
        privileged=deps.is_privileged(current),
        reason=payload.reason,
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")
    return DraftConflictOut.model_validate(conflict)


# =====================================================================
# Conflict registry — CFL- codes make every detected conflict a
# first-class, addressable record (see Task list this section
# implements): a lookup endpoint by code or UUID, a per-draft list for
# the History expansion, and a cross-draft list for the officer's own
# conflict history.
# =====================================================================

_CONFLICT_REF_RE = re.compile(r"^CFL-\d{4}-\d{6}$")


def _conflict_draft_brief(draft) -> ConflictDraftBrief:
    return ConflictDraftBrief(draft_id=draft.generated_draft_id, gr_number=draft.gr_number, title=draft.title)


def _conflict_to_with_draft(conflict) -> ConflictWithDraftOut:
    return ConflictWithDraftOut(
        **DraftConflictOut.model_validate(conflict).model_dump(),
        draft=_conflict_draft_brief(conflict.draft),
    )


def _conflict_to_lookup(conflict) -> ConflictLookupOut:
    return ConflictLookupOut(
        **DraftConflictOut.model_validate(conflict).model_dump(),
        draft=ConflictDraftDetail(
            draft_id=conflict.draft.generated_draft_id,
            gr_number=conflict.draft.gr_number,
            title=conflict.draft.title,
            department=conflict.draft.department,
            language=conflict.draft.language,
            created_at=conflict.draft.created_at,
        ),
    )


@router.get("/api/conflicts/lookup", response_model=ConflictLookupOut, tags=["conflicts"])
async def lookup_conflict(
    ref: str = Query(..., min_length=1, max_length=64, description="A CFL-YYYY-NNNNNN code or a conflict UUID"),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> ConflictLookupOut:
    """Accepts either shape people might paste in: the CFL- code
    (case-insensitive, trimmed) or the raw conflict UUID. Anything that
    matches neither shape is rejected with 422 before it reaches the
    database. A conflict that exists but belongs to another officer
    returns the SAME 404 as one that doesn't exist at all — see
    conflicts_repo.lookup, which folds ownership into the query itself
    rather than checking it after the fact, so there's nothing here that
    could leak which codes are real."""
    normalised = ref.strip()
    conflict_id: Optional[UUID] = None
    conflict_ref: Optional[str] = None
    try:
        conflict_id = UUID(normalised)
    except ValueError:
        upper = normalised.upper()
        if _CONFLICT_REF_RE.match(upper):
            conflict_ref = upper
        else:
            raise HTTPException(
                status_code=422,
                detail="ref must be a CFL-YYYY-NNNNNN code or a valid conflict UUID",
            )

    conflict = await conflicts_repo.lookup(
        session,
        conflict_id=conflict_id,
        conflict_ref=conflict_ref,
        officer_id=current.officer_id,
        privileged=deps.is_privileged(current),
    )
    if conflict is None:
        raise HTTPException(status_code=404, detail="No conflict found with that reference.")
    return _conflict_to_lookup(conflict)


@router.get("/api/drafts/{draft_id}/conflicts", response_model=List[ConflictWithDraftOut], tags=["conflicts"])
async def list_draft_conflicts(
    draft_id: UUID,
    severity: Optional[ConflictSeverity] = Query(default=None),
    is_dismissed: Optional[bool] = Query(default=None),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[ConflictWithDraftOut]:
    """Every conflict on one draft — what the History page's expansion
    row fetches. _load_draft already 404s on a draft that doesn't exist
    or isn't this officer's (unless privileged), so no separate
    ownership check is needed for the conflicts themselves."""
    await _load_draft(session, draft_id, current)
    conflicts = await conflicts_repo.list_for_draft(
        session,
        draft_id,
        severity=severity.value if severity else None,
        is_dismissed=is_dismissed,
    )
    return [_conflict_to_with_draft(c) for c in conflicts]


@router.get("/api/conflicts", response_model=PaginatedConflicts, tags=["conflicts"])
async def list_conflicts(
    severity: Optional[ConflictSeverity] = Query(default=None),
    is_dismissed: Optional[bool] = Query(default=None),
    department: Optional[str] = Query(default=None, max_length=160),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    detected_by: Optional[ConflictDetectedBy] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=200, description="Free-text search: conflicting text + justification"),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PaginatedConflicts:
    """Cross-draft conflict list, scoped to the current officer's own
    drafts (or every officer's, if reviewer/admin) — sort_by is checked
    against a hardcoded allowlist inside the repo, never raw user input."""
    try:
        rows, total = await conflicts_repo.list_conflicts(
            session,
            officer_id=current.officer_id,
            privileged=deps.is_privileged(current),
            severity=severity.value if severity else None,
            is_dismissed=is_dismissed,
            department=department,
            date_from=date_from,
            date_to=date_to,
            detected_by=detected_by.value if detected_by else None,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return PaginatedConflicts(
        items=[_conflict_to_with_draft(c) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# =====================================================================
# Analysis — one route per objective, plus a combined one
# =====================================================================

@router.post("/api/analysis/{draft_id}/template",
             response_model=List[TemplateIssue], tags=["analysis"])
async def run_template_check(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[TemplateIssue]:
    """Objective 4: Manual of Office Procedure enforcement. Instant, no AI."""
    draft = await _load_draft(session, draft_id, current)
    if draft.language == "mr":
        return template_rules_marathi.check_template_marathi(draft.content)
    return template_rules.check_template(draft.content)


@router.post("/api/analysis/{draft_id}/references",
             response_model=List[ReferenceHit], tags=["analysis"])
async def run_reference_tracking(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[ReferenceHit]:
    """Objective 3: find and resolve every GR this draft cites."""
    draft = await _load_draft(session, draft_id, current)
    hits = references.extract_references(draft.content)
    return await run_in_threadpool(references.resolve_against_corpus, hits)


@router.post("/api/analysis/{draft_id}/conflicts",
             response_model=List[ConflictHit], tags=["analysis"])
async def run_conflict_detection(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[ConflictHit]:
    """
    Objective 1: cross-departmental conflict detection.

    The slowest route by far, since it makes model calls. The frontend
    should call it separately and show a spinner, rather than blocking
    the whole report on it.
    """
    draft = await _load_draft(session, draft_id, current)
    draft_lang = draft.language  # already "en" or "mr"

    clauses = await run_in_threadpool(llm.split_into_clauses, draft.content)
    if not clauses:
        return []

    target_clauses = clauses[:settings.MAX_CLAUSES_ANALYSED]
    all_candidates = await run_in_threadpool(
        retrieval.search_batch,
        queries=target_clauses,
        top_k=settings.CANDIDATES_PER_CLAUSE,
        draft_language=draft_lang,
        draft_department=draft.department,
    )

    conflicts = await run_in_threadpool(
        llm.detect_conflicts, target_clauses, all_candidates, draft_language=draft_lang
    )
    return [c for c in conflicts
            if c.confidence >= settings.CONFLICT_CONFIDENCE_FLOOR]


@router.post("/api/analysis/{draft_id}/terminology",
             response_model=List[TermMapping], tags=["analysis"])
async def run_terminology(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> List[TermMapping]:
    """Objective 2: bilingual legal terminology consistency."""
    draft = await _load_draft(session, draft_id, current)
    return await run_in_threadpool(llm.map_terminology, draft.content, Language(draft.language))


@router.post("/api/analysis/{draft_id}",
             response_model=AnalysisReport, tags=["analysis"])
async def run_full_analysis(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> AnalysisReport:
    """
    Run all four objectives and return one report.
    THIS IS THE ENDPOINT THE MAIN SCREEN CALLS.
    """
    draft = await _load_draft(session, draft_id, current)

    if draft.language == "mr":
        template_issues = template_rules_marathi.check_template_marathi(draft.content)
    else:
        template_issues = template_rules.check_template(draft.content)

    reference_hits = await run_in_threadpool(
        references.resolve_against_corpus, references.extract_references(draft.content)
    )
    conflicts = await run_conflict_detection(draft_id, current, session)
    terms = await run_in_threadpool(llm.map_terminology, draft.content, Language(draft.language))

    errors = sum(1 for i in template_issues if i.severity == Severity.ERROR)
    warnings = sum(1 for i in template_issues if i.severity == Severity.WARNING)
    unresolved = sum(1 for r in reference_hits if not r.found_in_corpus)
    top_confidence = max((c.confidence for c in conflicts), default=0.0)

    # A template error or any conflict blocks issue of the GR.
    # A warning or an unresolvable citation only needs a human look.
    if errors or conflicts:
        overall = "blocked"
    elif warnings or unresolved:
        overall = "needs_review"
    else:
        overall = "clean"

    return AnalysisReport(
        draft_id=str(draft.generated_draft_id),
        generated_at=datetime.now(timezone.utc),
        summary=AnalysisSummary(
            template_error_count=errors,
            template_warning_count=warnings,
            reference_count=len(reference_hits),
            unresolved_reference_count=unresolved,
            conflict_count=len(conflicts),
            highest_conflict_confidence=top_confidence,
            overall_status=overall,
        ),
        template_issues=template_issues,
        references=reference_hits,
        conflicts=conflicts,
        terms=terms,
    )


# =====================================================================
# Corpus search
# =====================================================================

@router.get("/api/corpus/{gr_id}/ocr", response_model=FullOCRResponse, tags=["corpus"])
def get_corpus_ocr(gr_id: str, language: str = Query(None, description="Filter by language 'mr' or 'en'")) -> FullOCRResponse:
    """
    Fetch the full OCR text reconstructed from chunks.
    """
    res = retrieval.get_full_ocr(gr_id, language)
    if not res:
        raise HTTPException(status_code=404, detail=f"GR {gr_id} not found in corpus")
    return FullOCRResponse(**res)


@router.get("/api/official-source/{gr_number}", response_model=OfficialSourceResponse, tags=["corpus"])
def get_official_source(
    gr_number: str,
    department: str = Query(..., description="Department name for lookup routing"),
    date: str = Query(None, description="Optional date string"),
    subject: str = Query(None, description="Optional subject string")
) -> OfficialSourceResponse:
    # 1. Check Cache
    cached = store.get_cached_official_url(gr_number)
    if cached and cached.get("official_url"):
        return OfficialSourceResponse(status="found", url=cached["official_url"])

    # 2. Get Adapter and look up
    adapter = get_adapter(department)
    url = adapter.find_pdf(gr_number, date, subject)

    # 3. Store result in Cache if found
    if url:
        store.set_cached_official_url(gr_number, department, url)
        return OfficialSourceResponse(status="found", url=url)

    return OfficialSourceResponse(status="not_found", url=None)


@router.get("/api/official-gr/{gr_number}", response_model=OfficialSourceResponse, tags=["corpus"])
def get_official_gr(
    gr_number: str,
    department: str = Query(..., description="Department name for lookup routing"),
    date: str = Query(None, description="Optional date string"),
    subject: str = Query(None, description="Optional subject string")
) -> OfficialSourceResponse:
    """
    Locate the exact Government Resolution hosted on the official portal.
    Checks the local cache first, otherwise triggers resolver.
    """
    # 1. Check Cache
    cached = store.get_cached_official_url(gr_number)
    if cached and cached.get("official_url"):
        return OfficialSourceResponse(status="found", url=cached["official_url"])

    # 2. Get Adapter and look up
    from lookup import get_adapter
    adapter = get_adapter(department)
    url = adapter.find_pdf(gr_number, date, subject)

    # 3. Store result in Cache if found
    if url:
        store.set_cached_official_url(gr_number, department, url)
        return OfficialSourceResponse(status="found", url=url)

    return OfficialSourceResponse(status="not_found", url=None)


@router.get("/api/corpus/search",
            response_model=CorpusSearchResponse, tags=["corpus"])
def search_corpus(
    q: str = Query(..., min_length=3, description="Natural language query"),
    top_k: int = Query(default=None, ge=1, le=50),
) -> CorpusSearchResponse:
    """
    Search past GRs by meaning rather than keyword.

    Useful on its own, and the safest fallback demo if conflict
    detection misbehaves in front of the judges.
    """
    started = time.perf_counter()
    hits = retrieval.search(q, top_k=top_k or settings.TOP_K)
    took_ms = int((time.perf_counter() - started) * 1000)
    return CorpusSearchResponse(query=q, hits=hits, took_ms=took_ms)


@router.post("/api/copilot/chat", response_model=ChatResponse, tags=["copilot"])
def copilot_chat(payload: ChatRequest) -> ChatResponse:
    session_id = payload.session_id or uuid.uuid4().hex[:12]
    history = store.get_session_history(session_id)

    # 1. Build search query from last user turn if history exists
    if history:
        last_user = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"), ""
        )
        search_query = f"{last_user} {payload.query}".strip()[-200:]
    else:
        search_query = payload.query

    # 2. Retrieval grounding — filter out noise below similarity score 0.81
    hits = retrieval.search(search_query, top_k=3, min_score=0.81)
    if hits:
        context_str = "\n\n".join(
            f"Source GR {hit.gr_id} ({hit.department}):\n{hit.snippet[:300]}"
            for hit in hits
        )
    else:
        context_str = "No specific GR chunks found for this general query."

    # 3. Compact system & conversation context
    system_prompt = (
        "You are NIRN.AI Copilot, expert administrative assistant for Government of Maharashtra. "
        "Answer professional administrative questions using GR context when available. "
        "Maintain a helpful, bilingual (Marathi/English) administrative tone."
    )
    history_context = "\n".join(
        f"{m['role']}: {m['content'][:120]}" for m in history[-2:]
    )
    user_msg = (
        f"GR CONTEXT:\n{context_str}\n\n"
        f"RECENT CHAT:\n{history_context}\n\n"
        f"QUERY: {payload.query}"
    )

    # 4. Single combined call: answer + suggestions in one round-trip
    answer, suggestions = llm.call_chat(system_prompt, user_msg)

    # 5. Save history
    store.add_message(session_id, {"role": "user", "content": payload.query})
    store.add_message(session_id, {"role": "model", "content": answer})

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        references=hits,
        follow_up_suggestions=suggestions,
    )


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    """Rough HTML->plain-text for the content_plain full-text-search column."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


def _is_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


_SEVERITY_MAP = {"Low": "low", "Medium": "medium", "High": "high", "Critical": "high"}

_GR_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y")


def _parse_gr_date(raw: Optional[str]) -> Optional[date]:
    """Best-effort parse of the FAISS chunk's free-form issued_on string.
    Returns None rather than guessing when it doesn't match a known
    format — never fabricate a date the corpus didn't actually give us."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _GR_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _conflict_hit_to_row(item: ConflictHit) -> dict:
    """
    Convert a ConflictHit (returned by the unified conflict pipeline) into
    the dict shape expected by store.add_conflicts().
    """
    return dict(
        source_of_conflict=(
            f"{item.existing_gr_id}: {item.existing_gr_title}"
        )[:200],
        conflicting_text=item.existing_clause,
        draft_excerpt=item.draft_clause,
        conflicting_gr_id=item.existing_gr_id[:64] if item.existing_gr_id else None,
        severity=_SEVERITY_MAP.get(item.severity or "High", "medium"),
        justification=item.justification[:10000],
        detected_by="llm_verifier",
    )


def _conflict_report_to_row(item: ConflictReportItem) -> dict:
    """Legacy helper kept for the /api/conflicts/detect standalone endpoint."""
    gr_id = item.matched_gr.split(":", 1)[0].strip() if item.matched_gr else None
    return dict(
        source_of_conflict=(item.matched_gr or item.category)[:200],
        conflicting_text=item.matched_clause,
        draft_excerpt=item.draft_clause,
        conflicting_gr_id=gr_id[:64] if gr_id else None,
        severity=_SEVERITY_MAP.get(item.severity, "medium"),
        justification=f"{item.reason} Recommendation: {item.recommendation}"[:10000],
        detected_by=item.detected_by or "llm_verifier",
        draft_clause_ref=item.draft_clause_ref,
        draft_clause_index=item.draft_clause_index,
        source_clause_ref=item.source_clause_ref,
        source_gr_title=item.source_gr_title[:400] if item.source_gr_title else None,
        source_gr_date=_parse_gr_date(item.source_gr_date),
    )


def _reference_hit_to_row(hit: ReferenceHit) -> dict:
    return dict(
        reference_text=hit.raw_text,
        extracted_gr_number=hit.gr_number,
        reference_date=None,
        script="devanagari" if _is_devanagari(hit.raw_text) else "latin",
        resolved=hit.found_in_corpus,
    )


@router.post("/api/copilot/draft", response_model=DraftGenerateResponse, tags=["copilot"])
async def copilot_draft(
    payload: DraftGenerateRequest,
    response: Response,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> DraftGenerateResponse:
    with perf("REQUEST /api/copilot/draft"):

        # 1. Retrieve similar GRs for styling/reference — trim snippets to save tokens
        with perf("Retrieval Search"):
            hits = await run_in_threadpool(retrieval.search, payload.prompt, top_k=3)
        examples_str = ""
        for idx, hit in enumerate(hits):
            examples_str += f"--- EXAMPLE GR {idx+1} (Dept: {hit.department}) ---\n{hit.snippet[:400]}\n\n"

        # 2. LLM drafting call — use language-specific prompt to avoid
        # injecting the unused language template (~260 token saving).
        with perf("Prompt Construction"):
            system_prompt = prompts.build_draft_prompt(payload.language)
            dept = payload.department if payload.department else (hits[0].department if hits else "General_Administration_Department")
            dept_display = dept.replace("_", " ")

            user_msg = (
                f"Input:\n"
                f"- User Prompt: {payload.prompt}\n"
                f"- Issuing Department: {dept_display}\n"
                f"- Language: {payload.language}\n"
                f"- Retrieved Context:\n{examples_str}"
            )
            
        with perf("Draft Generation"):
            body_text = await run_in_threadpool(llm.call_model, system_prompt, user_msg, purpose="draft_generation")

        title = f"Draft GR: {payload.prompt[:50]}"
        lang_enum = Language.MARATHI if payload.language.lower() == "marathi" else Language.ENGLISH

        # 3. Objective 3 + Objective 1, run against the freshly generated text.
        # detect_cross_department_conflicts now returns List[ConflictHit] (same
        # schema as the analysis route) using the batched pipeline.
        draft_lang = lang_enum.value  # "en" or "mr"

        with perf("Reference Extraction"):
            reference_hits = references.extract_references(body_text)

        with perf("Conflict Detection"):
            conflict_items = await run_in_threadpool(
                detect_cross_department_conflicts, body_text, draft_lang
            )

        # 3.5 Assemble final GR with deterministic header/footer
        import datetime
        current_date_str = datetime.datetime.now().strftime("%d %B, %Y")
        current_year = datetime.datetime.now().year
        
        if draft_lang == "mr":
            final_body_text = prompts.MARATHI_GR_HEADER_TEMPLATE.format(
                department=dept_display,
                year=current_year,
                date=current_date_str
            ) + body_text + prompts.MARATHI_GR_FOOTER_TEMPLATE
        else:
            final_body_text = prompts.ENGLISH_GR_HEADER_TEMPLATE.format(
                department=dept_display,
                year=current_year,
                date=current_date_str
            ) + body_text + prompts.ENGLISH_GR_FOOTER_TEMPLATE

        # 4. Persist draft + conflicts + references in ONE transaction — the
        # get_session dependency commits once at the end of the request and
        # rolls back everything here if any of these inserts fails.
        with perf("Database"):
            with perf("Draft Insert"):
                draft = await store.create_draft(
                    session,
                    title=title,
                    language=lang_enum.value,
                    drafted_by=current.officer_id,
                    content=final_body_text,
                    department=dept,
                    content_plain=_strip_html(final_body_text),
                    brief=payload.prompt,
                )
            if reference_hits:
                with perf("Reference Insert"):
                    await store.add_references(
                        session, draft.generated_draft_id, [_reference_hit_to_row(h) for h in reference_hits]
                    )
            if conflict_items:
                with perf("Conflict Insert"):
                    await store.add_conflicts(
                        session,
                        draft.generated_draft_id,
                        [_conflict_hit_to_row(c) for c in conflict_items],
                    )

        result_payload = DraftGenerateResponse(
            draft_id=str(draft.generated_draft_id),
            title=draft.title,
            department=draft.department,
            body_text=draft.content,
            references=hits
        )

    # Print timing report to terminal as before
    perf.report()
    
    # Also attach it to the HTTP response header as Base64 so the frontend can read it
    report_str = perf.get_report_string()
    if report_str and settings.ENABLE_TELEMETRY:
        import base64
        import json
        import uuid
        encoded = base64.b64encode(report_str.encode("utf-8")).decode("ascii")
        response.headers["X-Performance-Profile"] = encoded
        
        meta_list = perf.get_all_meta()
        if meta_list:
            payload = {
                "version": 1,
                "request_id": str(uuid.uuid4()),
                "calls": meta_list
            }
            meta_json = json.dumps(payload)
            response.headers["X-NIRN-Metrics"] = base64.b64encode(meta_json.encode("utf-8")).decode("ascii")

    perf.reset()
    return result_payload


@router.post("/api/copilot/compare", response_model=ComparisonResponse, tags=["copilot"])
def copilot_compare(payload: ComparisonRequest) -> ComparisonResponse:
    # 1. Look up GR chunks — trim snippets to reduce token usage
    hits1 = retrieval.search(payload.gr_id_1, top_k=3)
    hits2 = retrieval.search(payload.gr_id_2, top_k=3)

    text1 = "\n\n".join(h.snippet[:350] for h in hits1)
    text2 = "\n\n".join(h.snippet[:350] for h in hits2)

    # 2. LLM Comparison
    system_prompt = (
        "You are a policy analyst for the Government of Maharashtra. "
        "Compare the two provided Government Resolutions (GRs) side-by-side. "
        "Create a clean comparative analysis highlighting:\n"
        "1. Eligibility Criteria\n"
        "2. Financial Limits / Allocations\n"
        "3. Departmental Jurisdictions\n"
        "4. Scope of Amendments or applicability\n"
        "Present the output as a clean Markdown table comparing the two, followed by a brief summary of key differences."
    )
    user_msg = f"GOVERNMENT RESOLUTION 1 ({payload.gr_id_1}):\n{text1}\n\nGOVERNMENT RESOLUTION 2 ({payload.gr_id_2}):\n{text2}"
    report = llm.call_model(system_prompt, user_msg, purpose="compare_versions")

    return ComparisonResponse(
        gr_id_1=payload.gr_id_1,
        gr_id_2=payload.gr_id_2,
        comparison_report=report
    )


@router.post("/api/copilot/explain-clause", response_model=ClauseExplanationResponse, tags=["copilot"])
def copilot_explain_clause(payload: ClauseExplanationRequest) -> ClauseExplanationResponse:
    system_prompt = (
        "You are a legal advisor. Explain the provided Government Resolution clause in simple terms. "
        "Avoid heavy administrative jargon. Translate or write your explanation in the requested language."
    )
    lang_name = "Marathi" if payload.language == Language.MARATHI else "English"
    user_msg = f"EXPLAIN THIS CLAUSE IN SIMPLE {lang_name}:\n{payload.clause_text}"
    explanation = llm.call_model(system_prompt, user_msg, purpose="explain_policy")

    return ClauseExplanationResponse(explanation=explanation)


@router.post("/api/conflicts/detect", response_model=List[ConflictReportItem], tags=["conflicts"])
def detect_conflicts_endpoint(payload: DraftCreate) -> List[ConflictReportItem]:
    """
    Accepts a draft GR and returns a cross-departmental structured conflict report
    using the modular rule-engine and LLM two-stage pipeline.
    """
    return detect_cross_department_conflicts(payload.body_text)
