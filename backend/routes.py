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
