"""
retrieval.py — Clause-aware semantic search over the GR corpus for NIRN.Ai.

Multi-stage retrieval pipeline:
  1. Embed query with multilingual-e5-base
  2. FAISS Top-K vector retrieval
  3. Weighted metadata scoring (70% semantic, 15% department, 10% subject, 5% recency)
  4. Structural clause-level deduplication
  5. Header/boilerplate filtering
  6. Cross-encoder reranking
  7. Return Top-K operative clause CorpusHit objects with rich metadata
"""

from typing import List, Optional, Dict
import os
import re
import time
import pickle
import numpy as np
import threading
import logging
import faiss

from config import settings
from profiler import perf
from schemas import CorpusHit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection helper
# ---------------------------------------------------------------------------

_DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')

def is_marathi_text(text: str) -> bool:
    """Return True if the text contains enough Devanagari characters to be Marathi."""
    deva_count = len(_DEVANAGARI_RE.findall(text))
    return deva_count >= 5

_model = None
_index = None
_chunks = None
_metadata = None
_cross_encoder = None

_model_lock = threading.Lock()
_faiss_lock = threading.Lock()
_ce_lock = threading.Lock()


def _get_memory_usage_mb() -> float:
    """Estimate process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


def _load_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("intfloat/multilingual-e5-base")
    return _model


def _verify_vector_mapping(sample_size: int = 100) -> bool:
    """Validate that random FAISS vector IDs map back to correct clause objects in _chunks."""
    import random
    if _index is None or _chunks is None or _index.ntotal != len(_chunks):
        return False
    
    total = _index.ntotal
    indices = random.sample(range(total), min(sample_size, total))
    for idx in indices:
        chunk = _chunks[idx]
        if not isinstance(chunk, dict):
            return False
        # Verify required metadata fields
        for req in ("gr_id", "department", "language", "text", "clause_number", "clause_type"):
            if req not in chunk:
                logger.error("Chunk at index %d missing required key: %s", idx, req)
                return False
    return True


def _load_faiss():
    global _index, _chunks, _metadata
    with _faiss_lock:
        if _index is None:
            index_path = os.path.join(os.path.dirname(__file__), "data", "index.faiss")
            if not os.path.exists(index_path):
                index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db", "index.faiss")
            if not os.path.exists(index_path):
                raise RuntimeError(f"FAISS index file not found at {index_path}")
            _index = faiss.read_index(index_path)

        if _chunks is None:
            chunks_path = os.path.join(os.path.dirname(__file__), "data", "chunks.pkl")
            if not os.path.exists(chunks_path):
                chunks_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db", "chunks.pkl")
            if not os.path.exists(chunks_path):
                raise RuntimeError(f"Chunks file not found at {chunks_path}")
            with open(chunks_path, "rb") as f:
                _chunks = pickle.load(f)

        if _metadata is None:
            meta_path = os.path.join(os.path.dirname(__file__), "data", "metadata.json")
            if os.path.exists(meta_path):
                import json
                with open(meta_path, "r", encoding="utf-8") as f:
                    _metadata = json.load(f)

        # -------------------------------------------------------------------
        # Validation checks on startup / load
        # -------------------------------------------------------------------
        num_vectors = _index.ntotal
        num_clauses = len(_chunks)
        if num_vectors != num_clauses:
            raise RuntimeError(
                f"INDEX MISMATCH: FAISS index contains {num_vectors} vectors, "
                f"but chunks.pkl contains {num_clauses} clause records!"
            )

        # Check embedding dimension using _index.d against model dimension
        model = _load_model()
        model_dim = getattr(model, "get_embedding_dimension", getattr(model, "get_sentence_embedding_dimension", lambda: 768))()
        index_dim = _index.d
        if index_dim != model_dim:
            raise RuntimeError(
                f"DIMENSION MISMATCH: FAISS index dimension ({index_dim}) "
                f"does not match retrieval model dimension ({model_dim})!"
            )

        # Validate vector to clause mapping with 100 random samples
        if not _verify_vector_mapping(100):
            raise RuntimeError("VECTOR MAPPING VERIFICATION FAILED: FAISS vector indices do not map to valid clause metadata!")


def init_retrieval() -> dict:
    """
    Explicit startup initialization and health check report.
    Returns status dictionary and prints startup report.
    """
    t0 = time.perf_counter()
    _load_model()
    _load_faiss()
    cross_encoder = _load_cross_encoder()
    load_time = time.perf_counter() - t0

    index_path = os.path.join(os.path.dirname(__file__), "data", "index.faiss")
    chunks_path = os.path.join(os.path.dirname(__file__), "data", "chunks.pkl")
    index_size_bytes = os.path.getsize(index_path) if os.path.exists(index_path) else 0
    chunks_size_bytes = os.path.getsize(chunks_path) if os.path.exists(chunks_path) else 0
    total_size_mb = round((index_size_bytes + chunks_size_bytes) / (1024 * 1024), 2)
    total_size_gb = round(total_size_mb / 1024, 2)

    gr_count = len(_metadata) if _metadata else len(set(c.get("gr_id") for c in _chunks))
    avg_clauses_per_gr = round(len(_chunks) / max(gr_count, 1), 2)
    mem_mb = _get_memory_usage_mb()

    report = {
        "faiss_vector_count": _index.ntotal,
        "clause_count": len(_chunks),
        "gr_metadata_count": gr_count,
        "embedding_dimension": _index.d,
        "embedding_model": "intfloat/multilingual-e5-base",
        "cross_encoder_name": "cross-encoder/ms-marco-MiniLM-L-6-v2" if cross_encoder else "None",
        "avg_clauses_per_gr": avg_clauses_per_gr,
        "index_size_mb": total_size_mb,
        "index_size_gb": total_size_gb,
        "retrieval_model_status": "loaded",
        "cross_encoder_status": "loaded" if cross_encoder else "unavailable",
        "confidence_thresholds": {
            "AUTO": settings.CONFIDENCE_AUTO,
            "REVIEW": settings.CONFIDENCE_REVIEW,
            "FLOOR": settings.CONFLICT_CONFIDENCE_FLOOR,
        },
        "memory_usage_mb": mem_mb,
        "load_time_seconds": round(load_time, 3),
        "status": "successful_initialization",
    }

    # Print required startup validation block
    print("\n" + "=" * 72)
    print("  NIRN.Ai — CLAUSE-AWARE SEMANTIC INDEX STARTUP VALIDATION")
    print("=" * 72)
    print(f"  Indexed Clauses        : {report['clause_count']:,}")
    print(f"  FAISS Vectors Loaded   : {report['faiss_vector_count']:,}")
    print(f"  GR Documents Metadata : {report['gr_metadata_count']:,}")
    print(f"  Avg Clauses per GR     : {report['avg_clauses_per_gr']}")
    print(f"  Embedding Dimension    : {report['embedding_dimension']}d (matches model)")
    print(f"  Retrieval Model        : {report['embedding_model']}")
    print(f"  Cross-Encoder          : {report['cross_encoder_name']}")
    print(f"  Index File Size        : {total_size_mb:.1f} MB ({total_size_gb:.2f} GB)")
    print(f"  Process Memory Usage   : {mem_mb} MB")
    print(f"  Confidence Thresholds  : AUTO={settings.CONFIDENCE_AUTO}, REVIEW={settings.CONFIDENCE_REVIEW}, FLOOR={settings.CONFLICT_CONFIDENCE_FLOOR}")
    print(f"  Initialization Time    : {load_time:.3f} s")
    print(f"  Overall Status         : ✓ SUCCESSFUL INITIALIZATION")
    print("=" * 72)

    # Retrieval Sanity Check
    sanity_results = search("lateral entry intake capacity", top_k=3)
    if not sanity_results:
        raise RuntimeError("RETRIEVAL SANITY CHECK FAILED: Query returned 0 results!")
    print(f"  ✓ Sanity check query returned {len(sanity_results)} hits (Top score: {sanity_results[0].score:.3f})\n")

    return report


def _load_cross_encoder():
    """Lazily load a cross-encoder for reranking. Falls back to None if unavailable."""
    global _cross_encoder
    with _ce_lock:
        if _cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("Cross-encoder loaded successfully")
            except Exception as e:
                logger.warning("Cross-encoder unavailable (%s), using bi-encoder scores only", e)
                _cross_encoder = False  # sentinel: tried but failed
    return _cross_encoder if _cross_encoder is not False else None


# ---------------------------------------------------------------------------
# Boilerplate detection
# ---------------------------------------------------------------------------

_HEADER_MARKERS = [
    "# Page 1", "महाराष्ट्र शासन", "Government of Maharashtra",
    "Government Resolution", "शासन निर्णय क्रमांक", "मंत्रालय",
    "Mantralaya", "Hutatma Rajguru",
]
_FOOTER_MARKERS = [
    "Copy to", "प्रत", "By order", "सही/-", "(Signed)",
    "या शासन निर्णयाची सत्यप्रत", "This Government Resolution",
]
_READ_MARKERS = ["वाचा", "Read:-", "Read :-", "Reference:-", "संदर्भ"]


def _is_boilerplate(text: str) -> bool:
    """Return True if text is administrative boilerplate (header/footer/read section)."""
    first_100 = text[:100]
    text_lower = text.lower()

    for m in _HEADER_MARKERS:
        if m in first_100:
            return True
    for m in _FOOTER_MARKERS:
        if m.lower() in text_lower:
            if len(text) < 200 or m.lower() in text_lower[:150]:
                return True
    for m in _READ_MARKERS:
        if m in first_100:
            return True
    return False


# ---------------------------------------------------------------------------
# Weighted metadata scoring
# ---------------------------------------------------------------------------

def _weighted_score(
    semantic_score: float,
    query_dept: str,
    chunk_dept: str,
    query_subject: str,
    chunk_subject: str,
    chunk_year: int,
    current_year: int = 2026,
) -> float:
    """
    Combine semantic similarity with metadata signals.

    Weights:
      70% semantic similarity
      15% department similarity
      10% subject similarity
       5% recency
    """
    # Department similarity: exact match = 1.0, partial = 0.5, none = 0.0
    dept_score = 0.0
    if query_dept and chunk_dept:
        q_dept = query_dept.lower().replace("_", " ")
        c_dept = chunk_dept.lower().replace("_", " ")
        if q_dept == c_dept:
            dept_score = 1.0
        elif any(word in c_dept for word in q_dept.split() if len(word) > 3):
            dept_score = 0.5

    # Subject similarity: keyword overlap
    subj_score = 0.0
    if query_subject and chunk_subject:
        q_words = set(query_subject.lower().split())
        c_words = set(chunk_subject.lower().split())
        overlap = q_words & c_words
        if q_words:
            subj_score = min(len(overlap) / max(len(q_words), 1), 1.0)

    # Recency: newer GRs get higher scores
    recency_score = 0.0
    if chunk_year > 0:
        age = max(current_year - chunk_year, 0)
        recency_score = max(1.0 - (age / 20.0), 0.0)  # 20-year window

    combined = (
        0.70 * semantic_score
        + 0.15 * dept_score
        + 0.10 * subj_score
        + 0.05 * recency_score
    )
    return min(max(combined, 0.0), 1.0)


# ---------------------------------------------------------------------
# CorpusHit Builder
# ---------------------------------------------------------------------

def _build_corpus_hit(chunk: dict, score: float) -> CorpusHit:
    gr_id_str = str(chunk.get("gr_id", "Unknown"))

    # 1. Derive issued_on from metadata or GR ID
    issued_on = chunk.get("issued_on") or chunk.get("date")
    if not issued_on:
        if len(gr_id_str) >= 8 and gr_id_str[:8].isdigit():
            issued_on = f"{gr_id_str[:4]}-{gr_id_str[4:6]}-{gr_id_str[6:8]}"
        elif chunk.get("year", 0) > 0:
            issued_on = str(chunk.get("year"))

    # 2. Populate title from subject or GR ID
    subject = chunk.get("subject", "").strip()
    title = chunk.get("title") or (subject if subject else f"GR {gr_id_str}")
    chunk_lang = chunk.get("language", "en")
    lang_path = "English" if chunk_lang == "en" else "Marathi"
    chunk_text = chunk.get("text", "")

    return CorpusHit(
        gr_id=gr_id_str,
        title=title,
        department=chunk.get("department", "Unknown"),
        issued_on=issued_on,
        snippet=chunk_text,
        score=score,
        source_url=f"https://gr.maharashtra.gov.in/Site/Upload/Government%20Resolutions/{lang_path}/{gr_id_str}.pdf",
        subject=subject if subject else None,
        language=chunk_lang,
        clause_number=chunk.get("clause_number"),
        clause_type=chunk.get("clause_type"),
        year=chunk.get("year"),
        financial_flag=chunk.get("financial_flag"),
        authority_flag=chunk.get("authority_flag"),
        timeline_flag=chunk.get("timeline_flag"),
        keywords=chunk.get("keywords"),
    )


# ---------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------

def embed(text: str) -> List[float]:
    model = _load_model()
    with _model_lock:
        res = model.encode(["query: " + text], convert_to_numpy=True)[0].tolist()
    return res


def embed_batch(texts: List[str]) -> List[List[float]]:
    model = _load_model()
    prefixed_texts = ["query: " + t for t in texts]
    with _model_lock:
        embeddings = model.encode(prefixed_texts, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


def chunk_text(text: str, max_chars: int = None, overlap: int = None) -> List[str]:
    max_chars = max_chars or settings.CHUNK_CHARS
    overlap = overlap or settings.CHUNK_OVERLAP

    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + max_chars])
        start += max_chars - overlap
    return chunks


# ---------------------------------------------------------------------
# Search (single query)
# ---------------------------------------------------------------------

def search(
    query: str,
    top_k: int = None,
    min_score: float = 0.0,
    draft_language: Optional[str] = None,
    draft_department: str = "",
) -> List[CorpusHit]:
    """
    Semantic search over the clause-aware GR corpus.
    """
    top_k = top_k or settings.TOP_K
    fetch_k = min(top_k * 5, 50)

    model = _load_model()
    _load_faiss()

    if _index is None or _chunks is None:
        return []

    with _model_lock:
        query_embedding = model.encode(["query: " + query], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)

    distances, indices = _index.search(query_embedding, k=fetch_k)

    query_is_marathi = (
        draft_language == "mr"
        or (draft_language is None and is_marathi_text(query))
    )

    LANG_BOOST = 0.05

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(_chunks):
            continue
        score = float(distances[0][i])
        norm_score = min(max(score, 0.0), 1.0)
        if norm_score < min_score:
            continue

        chunk = _chunks[idx]
        chunk_lang = chunk.get("language", "en")

        # Apply language boost
        if query_is_marathi and chunk_lang == "mr":
            norm_score = min(norm_score + LANG_BOOST, 1.0)
        elif not query_is_marathi and chunk_lang == "en":
            norm_score = min(norm_score + LANG_BOOST, 1.0)

        # Filter boilerplate
        chunk_text_content = chunk.get("text", "")
        chunk_type = chunk.get("clause_type", "")
        if chunk_type in ("header", "footer", "read") or _is_boilerplate(chunk_text_content):
            continue

        weighted = _weighted_score(
            semantic_score=norm_score,
            query_dept=draft_department,
            chunk_dept=chunk.get("department", ""),
            query_subject="",
            chunk_subject=chunk.get("subject", ""),
            chunk_year=chunk.get("year", 0),
        )

        hit = _build_corpus_hit(chunk, weighted)
        results.append(hit)

    # Clause-level deduplication per GR
    seen_gr = {}
    for hit in results:
        if hit.gr_id not in seen_gr or hit.score > seen_gr[hit.gr_id].score:
            seen_gr[hit.gr_id] = hit

    deduped = sorted(seen_gr.values(), key=lambda h: h.score, reverse=True)
    return deduped[:top_k]


# ---------------------------------------------------------------------
# Batch search (multi-query) — main pipeline for conflict detection
# ---------------------------------------------------------------------

def search_batch(
    queries: List[str],
    top_k: int = None,
    min_score: float = 0.0,
    draft_language: Optional[str] = None,
    draft_department: str = "",
) -> List[List[CorpusHit]]:
    """
    Multi-stage retrieval pipeline for conflict detection.
    """
    if not queries:
        return []

    top_k = top_k or settings.TOP_K
    fetch_k = min(top_k * 6, 50)

    model = _load_model()
    _load_faiss()

    if _index is None or _chunks is None:
        return [[] for _ in queries]

    # Stage 1: Single encoder forward pass for all clauses
    with perf("Batch Embedding"):
        with _model_lock:
            all_embeddings = model.encode(
                ["query: " + q for q in queries],
                convert_to_numpy=True,
            )

    faiss.normalize_L2(all_embeddings)

    # Stage 2: Batch FAISS search
    with perf("FAISS Search"):
        all_distances, all_indices = _index.search(all_embeddings, k=fetch_k)

    LANG_BOOST = 0.05
    cross_encoder = _load_cross_encoder()

    output: List[List[CorpusHit]] = []
    with perf("CorpusHit creation + filtering"):
        for q_i, query in enumerate(queries):
            query_is_marathi = (
                draft_language == "mr"
                or (draft_language is None and is_marathi_text(query))
            )

            raw_hits = []
            for j, idx in enumerate(all_indices[q_i]):
                if idx < 0 or idx >= len(_chunks):
                    continue
                score = float(all_distances[q_i][j])
                norm_score = min(max(score, 0.0), 1.0)
                if norm_score < min_score:
                    continue

                chunk = _chunks[idx]
                chunk_lang = chunk.get("language", "en")

                # Stage 3: Filter boilerplate
                chunk_text_content = chunk.get("text", "")
                chunk_type = chunk.get("clause_type", "")
                if chunk_type in ("header", "footer", "read") or _is_boilerplate(chunk_text_content):
                    continue

                # Language boost
                if query_is_marathi and chunk_lang == "mr":
                    norm_score = min(norm_score + LANG_BOOST, 1.0)
                elif not query_is_marathi and chunk_lang == "en":
                    norm_score = min(norm_score + LANG_BOOST, 1.0)

                # Stage 4: Apply weighted metadata scoring
                weighted = _weighted_score(
                    semantic_score=norm_score,
                    query_dept=draft_department,
                    chunk_dept=chunk.get("department", ""),
                    query_subject="",
                    chunk_subject=chunk.get("subject", ""),
                    chunk_year=chunk.get("year", 0),
                )

                hit = _build_corpus_hit(chunk, weighted)
                raw_hits.append(hit)

            # Stage 5: Deduplication by gr_id — keep highest-scoring chunk per GR
            seen_gr: dict = {}
            for hit in raw_hits:
                if hit.gr_id not in seen_gr or hit.score > seen_gr[hit.gr_id].score:
                    seen_gr[hit.gr_id] = hit
            deduped = sorted(seen_gr.values(), key=lambda h: h.score, reverse=True)

            # Stage 6: Cross-encoder reranking (if available)
            if cross_encoder is not None and len(deduped) > top_k:
                try:
                    with perf(f"Cross-Encoder Rerank [Q{q_i}]"):
                        pairs = [(query, hit.snippet[:500]) for hit in deduped[:top_k * 3]]
                        ce_scores = cross_encoder.predict(pairs)
                        for k, hit in enumerate(deduped[:len(ce_scores)]):
                            ce_norm = float(ce_scores[k])
                            ce_norm = 1.0 / (1.0 + np.exp(-ce_norm))  # sigmoid
                            combined = 0.6 * ce_norm + 0.4 * hit.score
                            hit.score = min(max(combined, 0.0), 1.0)
                        deduped = sorted(deduped[:len(ce_scores)], key=lambda h: h.score, reverse=True)
                except Exception as e:
                    logger.warning("Cross-encoder reranking failed: %s", e)

            output.append(deduped[:top_k])

    return output


def lookup_by_gr_number(gr_number: str) -> Optional[CorpusHit]:
    _load_faiss()
    if _chunks is None:
        return None
        
    for chunk in _chunks:
        if chunk.get("gr_id") == gr_number:
            return _build_corpus_hit(chunk, score=1.0)
    return None


def load_ocr_from_disk(gr_id: str, language: str) -> Optional[str]:
    import glob
    workspace_root = os.path.dirname(os.path.dirname(__file__))
    search_pattern = os.path.join(workspace_root, "mahGRs-main", "GRs", "*", f"{gr_id}.pdf.{language}.txt")
    matching_files = glob.glob(search_pattern)
    if matching_files:
        try:
            with open(matching_files[0], "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return None


def get_full_ocr(gr_id: str, language: Optional[str] = None) -> Optional[dict]:
    _load_faiss()
    if _chunks is None:
        return None

    # Filter chunks belonging to this GR
    gr_chunks = [c for c in _chunks if c.get("gr_id") == gr_id]
    
    department = "Unknown Department"
    title = f"GR {gr_id}"
    if gr_chunks:
        department = gr_chunks[0].get("department", department)
        subject = gr_chunks[0].get("subject", "")
        title = gr_chunks[0].get("title") or (subject if subject else title)

    full_text = None
    if language:
        lang_chunks = [c for c in gr_chunks if c.get("language") == language]
        if lang_chunks:
            lang_chunks.sort(key=lambda x: x.get("chunk_id", x.get("clause_number", 0)))
            full_text = "\n\n".join(c.get("text", "") for c in lang_chunks)
        else:
            full_text = load_ocr_from_disk(gr_id, language)
    else:
        if gr_chunks:
            gr_chunks.sort(key=lambda x: x.get("chunk_id", x.get("clause_number", 0)))
            full_text = "\n\n".join(c.get("text", "") for c in gr_chunks)

    if not full_text:
        for fallback_lang in ["mr", "en"]:
            full_text = load_ocr_from_disk(gr_id, fallback_lang)
            if full_text:
                break

    if not full_text:
        return None

    return {
        "gr_id": gr_id,
        "department": department,
        "title": title,
        "text": full_text
    }


def is_connected() -> bool:
    try:
        _load_faiss()
        return _index is not None and _chunks is not None
    except Exception:
        return False
