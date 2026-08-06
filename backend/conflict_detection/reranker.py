"""
reranker.py — cross-encoder reranking for conflict detection candidates.

Lazy-loads BAAI/bge-reranker-v2-m3 (or whatever RERANKER_MODEL_NAME is set to)
on first use.  The model is multilingual (English + Marathi Devanagari) and
small enough to run comfortably on CPU for 15-20 candidates per clause.

Public API
----------
rerank_candidates(clause, candidates, top_k) -> List[CorpusHit]
    Returns a new list of up to `top_k` candidates, re-sorted by the cross-encoder's
    relevance score (descending).  The original `candidates` list is not mutated.
"""

import logging
import threading
from typing import List

from schemas import CorpusHit

logger = logging.getLogger("nirn.conflict_detection.reranker")

_reranker = None
_reranker_lock = threading.Lock()


def _load_reranker():
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            from sentence_transformers import CrossEncoder
            from config import settings
            logger.info("Loading cross-encoder reranker: %s", settings.RERANKER_MODEL_NAME)
            _reranker = CrossEncoder(settings.RERANKER_MODEL_NAME)
            logger.info("Reranker loaded.")
    return _reranker


def rerank_candidates(
    clause: str,
    candidates: List[CorpusHit],
    top_k: int,
) -> List[CorpusHit]:
    """
    Score each candidate's snippet against the draft clause using a cross-encoder
    and return the top `top_k` candidates sorted by reranker score (descending).

    Falls back to the original order (bi-encoder score) if:
    - the candidate list is empty
    - the reranker fails for any reason (logged as a warning, not raised)

    Parameters
    ----------
    clause     : The draft clause text (query side of the cross-encoder pair).
    candidates : Full retrieval pool from vector search + jurisdiction hits.
    top_k      : How many to return after reranking (typically CANDIDATES_PER_CLAUSE).

    Returns
    -------
    A new list of up to `top_k` CorpusHit objects in reranker-score order.
    """
    if not candidates:
        return []

    try:
        model = _load_reranker()
        # CrossEncoder expects list of [query, document] pairs.
        pairs = [[clause, hit.snippet] for hit in candidates]
        scores = model.predict(pairs)  # numpy array, one float per pair

        ranked = sorted(
            zip(scores, candidates),
            key=lambda x: x[0],
            reverse=True,
        )
        return [hit for _, hit in ranked[:top_k]]

    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Reranker failed (%s); falling back to bi-encoder order for this clause.", exc
        )
        return candidates[:top_k]
