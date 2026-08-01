from typing import List, Optional
import llm
import retrieval
from clause_numbering import clause_ref
from config import settings

from .models import ConflictReportItem
from .rule_engine import check_deterministic_conflicts
from .llm_verifier import verify_conflict_with_llm


def _attach_clause_location(
    item: ConflictReportItem, *, clause_index: int, draft_clause_text: str, hit
) -> None:
    """Fills in where-in-our-draft / where-in-the-existing-GR this
    conflict came from, at the moment of detection — never reconstructed
    later. Both clause refs fall back to None (not a guess) when the
    text doesn't open with a recognisable numbered marker."""
    item.draft_clause_index = clause_index
    item.draft_clause_ref = clause_ref(draft_clause_text)
    item.source_clause_ref = clause_ref(hit.snippet)
    item.source_gr_title = hit.title
    item.source_gr_date = hit.issued_on


def detect_cross_department_conflicts(body_text: str) -> List[ConflictReportItem]:
    """
    Two-stage pipeline to detect policy, funding, authority, timeline, and operational
    conflicts between the draft GR text and existing GRs in the corpus.

    1. Splits the draft GR into clauses.
    2. Retrieves Top-K similar clauses from the vector DB.
    3. Runs Rule Engine for deterministic matches.
    4. Runs LLM Verification Layer for remaining semantic/ambiguous relations.
    """
    clauses = llm.split_into_clauses(body_text)
    if not clauses:
        return []

    conflicts: List[ConflictReportItem] = []

    # Process each clause to locate conflicts
    for clause_index, clause in enumerate(clauses[:settings.MAX_CLAUSES_ANALYSED]):
        # Search for semantically similar candidates across all departments
        candidates = retrieval.search(clause, top_k=settings.CANDIDATES_PER_CLAUSE)

        for hit in candidates:
            # Stage 1: Deterministic Rule Engine
            det_conflict = check_deterministic_conflicts(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet
            )

            if det_conflict:
                det_conflict.detected_by = "rule_engine"
                _attach_clause_location(det_conflict, clause_index=clause_index, draft_clause_text=clause, hit=hit)
                conflicts.append(det_conflict)
                continue

            # Stage 2: LLM Verification for semantic ambiguity
            llm_conflict = verify_conflict_with_llm(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet
            )

            if llm_conflict:
                llm_conflict.detected_by = "llm_verifier"
                _attach_clause_location(llm_conflict, clause_index=clause_index, draft_clause_text=clause, hit=hit)
                conflicts.append(llm_conflict)

    return conflicts
