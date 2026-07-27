"""
routes.py — every endpoint in NIRN.Ai.

Coming from Express, the mapping is:
    APIRouter()                 ->  express.Router()
    @router.post("/x")          ->  router.post("/x", handler)
    HTTPException(404, detail)  ->  res.status(404).json({...})

The difference in your favour: FastAPI validates the request body
against the schema automatically and returns 422 with a field-by-field
explanation, so you never write manual field checks.
"""

import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query, status

import llm
import references
import retrieval
import store
import template_rules
from config import settings
from schemas import (
    AnalysisReport,
    AnalysisSummary,
    ConflictHit,
    CorpusSearchResponse,
    Draft,
    DraftCreate,
    ReferenceHit,
    Severity,
    TemplateIssue,
    TermMapping,
    ChatMessage,
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


def _load(draft_id: str) -> Draft:
    """Fetch a draft or raise a clean 404. Used by every analysis route."""
    draft = store.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    return draft


# =====================================================================
# Drafts — plain CRUD
# =====================================================================

@router.post("/api/drafts", response_model=Draft,
             status_code=status.HTTP_201_CREATED, tags=["drafts"])
def create_draft(payload: DraftCreate) -> Draft:
    """Submit a draft GR. Returns it with a server-assigned id."""
    return store.create_draft(payload)


@router.get("/api/drafts", response_model=List[Draft], tags=["drafts"])
def list_drafts() -> List[Draft]:
    """All drafts, newest first."""
    return store.list_drafts()


@router.get("/api/drafts/{draft_id}", response_model=Draft, tags=["drafts"])
def get_draft(draft_id: str) -> Draft:
    return _load(draft_id)


@router.delete("/api/drafts/{draft_id}",
               status_code=status.HTTP_204_NO_CONTENT, tags=["drafts"])
def delete_draft(draft_id: str) -> None:
    if not store.delete_draft(draft_id):
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")


# =====================================================================
# Analysis — one route per objective, plus a combined one
# =====================================================================

@router.post("/api/analysis/{draft_id}/template",
             response_model=List[TemplateIssue], tags=["analysis"])
def run_template_check(draft_id: str) -> List[TemplateIssue]:
    """Objective 4: Manual of Office Procedure enforcement. Instant, no AI."""
    return template_rules.check_template(_load(draft_id).body_text)


@router.post("/api/analysis/{draft_id}/references",
             response_model=List[ReferenceHit], tags=["analysis"])
def run_reference_tracking(draft_id: str) -> List[ReferenceHit]:
    """Objective 3: find and resolve every GR this draft cites."""
    hits = references.extract_references(_load(draft_id).body_text)
    return references.resolve_against_corpus(hits)


@router.post("/api/analysis/{draft_id}/conflicts",
             response_model=List[ConflictHit], tags=["analysis"])
def run_conflict_detection(draft_id: str) -> List[ConflictHit]:
    """
    Objective 1: cross-departmental conflict detection.

    The slowest route by far, since it makes model calls. The frontend
    should call it separately and show a spinner, rather than blocking
    the whole report on it.
    """
    draft = _load(draft_id)
    clauses = llm.split_into_clauses(draft.body_text)

    candidates = []
    for clause in clauses[:settings.MAX_CLAUSES_ANALYSED]:
        candidates.extend(
            retrieval.search(clause, top_k=settings.CANDIDATES_PER_CLAUSE)
        )

    conflicts = llm.detect_conflicts(clauses, candidates)
    return [c for c in conflicts
            if c.confidence >= settings.CONFLICT_CONFIDENCE_FLOOR]


@router.post("/api/analysis/{draft_id}/terminology",
             response_model=List[TermMapping], tags=["analysis"])
def run_terminology(draft_id: str) -> List[TermMapping]:
    """Objective 2: bilingual legal terminology consistency."""
    draft = _load(draft_id)
    return llm.map_terminology(draft.body_text, draft.language)


@router.post("/api/analysis/{draft_id}",
             response_model=AnalysisReport, tags=["analysis"])
def run_full_analysis(draft_id: str) -> AnalysisReport:
    """
    Run all four objectives and return one report.
    THIS IS THE ENDPOINT THE MAIN SCREEN CALLS.
    """
    draft = _load(draft_id)

    template_issues = template_rules.check_template(draft.body_text)
    reference_hits = references.resolve_against_corpus(
        references.extract_references(draft.body_text)
    )
    conflicts = run_conflict_detection(draft_id)
    terms = llm.map_terminology(draft.body_text, draft.language)

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
        draft_id=draft.id,
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


import uuid
from schemas import Language

@router.post("/api/copilot/chat", response_model=ChatResponse, tags=["copilot"])
def copilot_chat(payload: ChatRequest) -> ChatResponse:
    session_id = payload.session_id or uuid.uuid4().hex[:12]
    history = store.get_session(session_id)

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


@router.post("/api/copilot/draft", response_model=DraftGenerateResponse, tags=["copilot"])
def copilot_draft(payload: DraftGenerateRequest) -> DraftGenerateResponse:
    # 1. Retrieve similar GRs for styling/reference — trim snippets to save tokens
    hits = retrieval.search(payload.prompt, top_k=3)
    examples_str = ""
    for idx, hit in enumerate(hits):
        examples_str += f"--- EXAMPLE GR {idx+1} (Dept: {hit.department}) ---\n{hit.snippet[:400]}\n\n"

    # 2. LLM drafting call
    system_prompt = (
        "You are an expert drafting officer for the Government of Maharashtra. "
        "Draft a professional Government Resolution based on the user's prompt. "
        "Incorporate the format, style, formal register (e.g. 'shall'), and conventions of "
        "the provided example GRs. Make sure to structure the output with clear headers:\n"
        "- GOVERNMENT OF MAHARASHTRA\n"
        "- DEPARTMENT\n"
        "- GR REFERENCE NUMBER & DATE\n"
        "- PREAMBLE / प्रस्तावना\n"
        "- GOVERNMENT RESOLUTION / शासन निर्णय (with numbered operative clauses)\n"
        "Cite the GR IDs from the examples that influenced this draft."
    )
    user_msg = f"USER PROMPT: {payload.prompt}\n\nSIMILAR GR EXAMPLES IN CORPUS:\n{examples_str}"
    body_text = llm.call_model(system_prompt, user_msg)
    
    title = f"Draft GR: {payload.prompt[:50]}"
    dept = hits[0].department if hits else "General Administration Department"
    
    # 3. Save as a draft so the user can run standard template / conflict checks
    draft = store.create_draft(DraftCreate(
        title=title,
        department=dept,
        body_text=body_text,
        language=Language.ENGLISH
    ))
    
    return DraftGenerateResponse(
        draft_id=draft.id,
        title=draft.title,
        department=draft.department,
        body_text=draft.body_text,
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
