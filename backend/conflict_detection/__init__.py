"""
conflict_detection/__init__.py

Semantic-first conflict detection pipeline for NIRN.Ai.

Pipeline:
  1. Structural clause extraction (headers stripped, only operative clauses)
  2. Batch embedding + FAISS retrieval with metadata weighting
  3. Boilerplate filtering + clause-level deduplication
  4. Cross-encoder reranking (if available)
  5. Semantic hint generation (replaces deterministic rule bypass)
  6. LLM semantic verification with hints injected
  7. Confidence band filtering

All conflicts are verified by the LLM. No deterministic bypass.
"""

from typing import List

import llm
import retrieval
from clause_numbering import clause_ref
from config import settings
from profiler import perf
from schemas import ConflictHit


def detect_cross_department_conflicts(
    body_text: str,
    draft_language: str = "en",
) -> List[ConflictHit]:
    """
    Detect cross-departmental conflicts in *body_text*.

    Returns a list of ConflictHit objects (same schema used by
    /api/analysis/{draft_id}/conflicts).  Items below the confidence
    floor defined in settings are excluded before returning.

    Parameters
    ----------
    body_text      : The full draft GR text to analyse.
    draft_language : 'mr' or 'en' — used to bias retrieval towards
                     same-language corpus chunks.
    """
    # Stage 1: Structural clause extraction
    with perf("Split Clauses"):
        clauses = llm.split_into_clauses(body_text)
        if not clauses:
            return []
        # Clamp to the configured limit (performance / cost guard).
        clauses = clauses[: settings.MAX_CLAUSES_ANALYSED]

    # ------------------------------------------------------------------
    # Stage 2: Batch-embed all clauses in ONE transformer forward pass.
    # ------------------------------------------------------------------
    with perf("Batch Embedding + FAISS + Reranking"):
        all_candidate_lists = retrieval.search_batch(
            queries=clauses,
            top_k=settings.CANDIDATES_PER_CLAUSE,
            draft_language=draft_language,
            min_score=0.40,
        )

    # Flatten for llm.detect_conflicts: it expects a flat list of
    # CorpusHit candidates and slices them per clause internally.
    with perf("Candidate Flatten"):
        flat_candidates: list = []
        for hits in all_candidate_lists:
            flat_candidates.extend(hits)

    if not flat_candidates:
        return []

    # ------------------------------------------------------------------
    # Stage 3: Semantic-first LLM verification
    # ------------------------------------------------------------------
    with perf("LLM Conflict Detection"):
        conflicts = llm.detect_conflicts(
            draft_clauses=clauses,
            candidates=flat_candidates,
            draft_language=draft_language,
        )

    # Apply the global confidence floor
    with perf("Confidence Filter"):
        result = [c for c in conflicts if c.confidence >= settings.CONFLICT_CONFIDENCE_FLOOR]

    return result
