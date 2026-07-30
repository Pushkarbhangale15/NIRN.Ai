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

import re
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from lookup import get_adapter
from config import settings
from rate_limit import limiter
from schemas import (
    Language,
    AnalysisReport,
    AnalysisSummary,
    ConflictHit,
    CorpusSearchResponse,
    DismissConflictRequest,
    DraftConflictOut,
    FullOCRResponse,
    LoginRequest,
    OfficerCreate,
    OfficerOut,
    OfficerUpdate,
    OfficialSourceResponse,
    DraftCreate,
    PaginatedDrafts,
    PersistedDraftCreate,
    PersistedDraftDetail,
    PersistedDraftOut,
    PersistedDraftStatus,
    PersistedDraftUpdate,
    ReferenceHit,
    Severity,
    TemplateIssue,
    TermMapping,
    TokenResponse,
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


# =====================================================================
# Auth
# =====================================================================

@router.post("/api/auth/register", response_model=OfficerOut,
             status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register_officer(
    payload: OfficerCreate, session: AsyncSession = Depends(get_session)
) -> OfficerOut:
    """
    Public, unauthenticated self-registration. Always creates a plain
    'officer' — any `role` the caller sends is ignored, otherwise an
    anonymous visitor could POST role: "admin" and grant themselves
    full access. Promotion to reviewer/admin only happens through
    PATCH /api/admin/officers/{id}, which requires an existing admin.
    """
    existing = await officers_repo.get_by_login_id(session, payload.login_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="login_id already registered")

    try:
        officer = await officers_repo.create_officer(
            session,
            name=payload.name,
            login_id=payload.login_id,
            password_hash=hash_password(payload.password),
            department=payload.department,
            designation=payload.designation,
            role="officer",
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not register officer")

    return OfficerOut.model_validate(officer)


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
# not just 'reviewer' (see deps.require_admin).
# =====================================================================

@router.get("/api/admin/officers", response_model=List[OfficerOut], tags=["admin"])
async def admin_list_officers(
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> List[OfficerOut]:
    officers = await officers_repo.list_officers(session)
    return [OfficerOut.model_validate(o) for o in officers]


@router.post("/api/admin/officers", response_model=OfficerOut,
             status_code=status.HTTP_201_CREATED, tags=["admin"])
async def admin_create_officer(
    payload: OfficerCreate,
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    """Unlike public /api/auth/register, an admin creating an officer here
    CAN set role directly — the caller is already authenticated as admin."""
    existing = await officers_repo.get_by_login_id(session, payload.login_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="login_id already registered")

    try:
        officer = await officers_repo.create_officer(
            session,
            name=payload.name,
            login_id=payload.login_id,
            password_hash=hash_password(payload.password),
            department=payload.department,
            designation=payload.designation,
            role=payload.role.value,
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create officer")

    return OfficerOut.model_validate(officer)


@router.patch("/api/admin/officers/{officer_id}", response_model=OfficerOut, tags=["admin"])
async def admin_update_officer(
    officer_id: UUID,
    payload: OfficerUpdate,
    _admin: Officer = Depends(deps.require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    officer = await officers_repo.get_by_id(session, officer_id)
    if officer is None:
        raise HTTPException(status_code=404, detail=f"Officer {officer_id} not found")

    if payload.is_active is not None:
        officer = await officers_repo.set_active(session, officer_id, payload.is_active)
    if payload.role is not None:
        officer = await officers_repo.set_role(session, officer_id, payload.role.value)

    return OfficerOut.model_validate(officer)


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


@router.get("/api/drafts", response_model=PaginatedDrafts, tags=["drafts"])
async def list_drafts(
    department: Optional[str] = Query(default=None, max_length=160),
    status_filter: Optional[PersistedDraftStatus] = Query(default=None, alias="status"),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> PaginatedDrafts:
    # sort_by is checked against a hardcoded allowlist inside the repo —
    # column names can never come from raw user input (PART 2 rule 4).
    try:
        items, total = await store.list_drafts(
            session,
            officer_id=current.officer_id,
            privileged=deps.is_privileged(current),
            department=department,
            status=status_filter.value if status_filter else None,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return PaginatedDrafts(
        items=[PersistedDraftOut.model_validate(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.delete("/api/drafts/{draft_id}",
               status_code=status.HTTP_204_NO_CONTENT, tags=["drafts"])
async def delete_draft(
    draft_id: UUID,
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft delete: sets status='archived'. Rows are never hard-deleted —
    audit history (versions, conflicts) must survive."""
    ok = await store.archive_draft(
        session, draft_id, officer_id=current.officer_id, privileged=deps.is_privileged(current)
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")


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

    candidates = []
    for clause in clauses[:settings.MAX_CLAUSES_ANALYSED]:
        candidates.extend(
            await run_in_threadpool(
                retrieval.search,
                clause,
                top_k=settings.CANDIDATES_PER_CLAUSE,
                draft_language=draft_lang,
            )
        )

    conflicts = await run_in_threadpool(
        llm.detect_conflicts, clauses, candidates, draft_language=draft_lang
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


def _conflict_report_to_row(item: ConflictReportItem) -> dict:
    gr_id = item.matched_gr.split(":", 1)[0].strip() if item.matched_gr else None
    return dict(
        source_of_conflict=(item.matched_gr or item.category)[:200],
        conflicting_text=item.matched_clause,
        draft_excerpt=item.draft_clause,
        conflicting_gr_id=gr_id[:64] if gr_id else None,
        severity=_SEVERITY_MAP.get(item.severity, "medium"),
        justification=f"{item.reason} Recommendation: {item.recommendation}"[:10000],
        detected_by=item.detected_by or "llm_verifier",
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
    current: Officer = Depends(deps.get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> DraftGenerateResponse:
    # 1. Retrieve similar GRs for styling/reference — trim snippets to save tokens
    hits = await run_in_threadpool(retrieval.search, payload.prompt, top_k=3)
    examples_str = ""
    for idx, hit in enumerate(hits):
        examples_str += f"--- EXAMPLE GR {idx+1} (Dept: {hit.department}) ---\n{hit.snippet[:400]}\n\n"

    # 2. LLM drafting call
    system_prompt = prompts.COPILOT_DRAFT
    dept = payload.department if payload.department else (hits[0].department if hits else "General_Administration_Department")
    dept_display = dept.replace("_", " ")

    user_msg = (
        f"Input:\n"
        f"- User Prompt: {payload.prompt}\n"
        f"- Issuing Department: {dept_display}\n"
        f"- Language: {payload.language}\n"
        f"- Retrieved Context:\n{examples_str}"
    )
    body_text = await run_in_threadpool(llm.call_model, system_prompt, user_msg)

    title = f"Draft GR: {payload.prompt[:50]}"
    lang_enum = Language.MARATHI if payload.language.lower() == "marathi" else Language.ENGLISH

    # 3. Objective 3 + Objective 1, run against the freshly generated text
    reference_hits = references.extract_references(body_text)
    conflict_items = await run_in_threadpool(detect_cross_department_conflicts, body_text)

    # 4. Persist draft + conflicts + references in ONE transaction — the
    # get_session dependency commits once at the end of the request and
    # rolls back everything here if any of these inserts fails.
    draft = await store.create_draft(
        session,
        title=title,
        language=lang_enum.value,
        drafted_by=current.officer_id,
        content=body_text,
        department=dept,
        content_plain=_strip_html(body_text),
        brief=payload.prompt,
    )
    if reference_hits:
        await store.add_references(
            session, draft.generated_draft_id, [_reference_hit_to_row(h) for h in reference_hits]
        )
    if conflict_items:
        await store.add_conflicts(
            session, draft.generated_draft_id, [_conflict_report_to_row(c) for c in conflict_items]
        )

    return DraftGenerateResponse(
        draft_id=str(draft.generated_draft_id),
        title=draft.title,
        department=draft.department,
        body_text=draft.content,
        references=hits
    )


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
    report = llm.call_model(system_prompt, user_msg)

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
    explanation = llm.call_model(system_prompt, user_msg)

    return ClauseExplanationResponse(explanation=explanation)


@router.post("/api/conflicts/detect", response_model=List[ConflictReportItem], tags=["conflicts"])
def detect_conflicts_endpoint(payload: DraftCreate) -> List[ConflictReportItem]:
    """
    Accepts a draft GR and returns a cross-departmental structured conflict report
    using the modular rule-engine and LLM two-stage pipeline.
    """
    return detect_cross_department_conflicts(payload.body_text)
