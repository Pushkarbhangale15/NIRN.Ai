"""
conflict_detection/__init__.py

Two-stage pipeline to detect policy, funding, authority, timeline, and
operational conflicts between the draft GR text and existing GRs.

PERFORMANCE NOTES
-----------------
The previous implementation called ``verify_conflict_with_llm`` once per
(clause, candidate) pair inside a nested Python loop, producing up to
MAX_CLAUSES × CANDIDATES_PER_CLAUSE = 10 × 4 = 40 sequential Ollama
requests per document.

This version replaces that with:
  1. ``retrieval.search_batch`` — embeds ALL clause strings in ONE
     SentenceTransformer forward pass and fans out FAISS results.
  2. ``llm.detect_conflicts``  — for each clause sends ONE batched LLM
     prompt covering all of its candidates, reducing LLM calls from 40
     to at most 10 (one per clause).

Functional output is identical: same ConflictHit schema, same
confidence threshold, same rule-engine logic, same detected_by tag.
"""

from typing import List

import llm
import retrieval
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
    with perf("Split Clauses"):
        clauses = llm.split_into_clauses(body_text)
        if not clauses:
            return []
        # Clamp to the configured limit (performance / cost guard).
        clauses = clauses[: settings.MAX_CLAUSES_ANALYSED]

    # ------------------------------------------------------------------
    # Stage 1: Batch-embed all clauses in ONE transformer forward pass.
    # The previous code called retrieval.search() per clause, which
    # called model.encode() per clause — N separate forward passes.
    # search_batch() reduces that to a single model.encode() call for
    # all clauses simultaneously.
    # ------------------------------------------------------------------
    with perf("Batch Embedding + FAISS"):
        all_candidate_lists = retrieval.search_batch(
            queries=clauses,
            top_k=settings.CANDIDATES_PER_CLAUSE,
            draft_language=draft_language,
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
    # Stage 2: Batched LLM verification — at most ONE call per clause.
    # llm.detect_conflicts() runs the deterministic rule-engine first
    # and only sends a batched prompt for candidates that pass through.
    # ------------------------------------------------------------------
    with perf("LLM Conflict Detection"):
        conflicts = llm.detect_conflicts(
            draft_clauses=clauses,
            candidates=flat_candidates,
            draft_language=draft_language,
        )

    # Apply the global confidence floor (same filter as the analysis route).
    with perf("Confidence Filter"):
        result = [c for c in conflicts if c.confidence >= settings.CONFLICT_CONFIDENCE_FLOOR]

    return result
