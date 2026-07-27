"""
retrieval.py — semantic search over the GR corpus.

Integrated with Prasad's FAISS implementation.
"""

from typing import List, Optional
import os
import faiss
import pickle
import numpy as np
import threading

from config import settings
from schemas import CorpusHit

_model = None
_index = None
_chunks = None

_model_lock = threading.Lock()
_faiss_lock = threading.Lock()

def _load_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("intfloat/multilingual-e5-base")
    return _model

def _load_faiss():
    global _index, _chunks
    with _faiss_lock:
        # We load them once lazily when first needed.
        if _index is None:
            index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db", "index.faiss")
            if os.path.exists(index_path):
                _index = faiss.read_index(index_path)
        
        if _chunks is None:
            chunks_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vector_db", "chunks.pkl")
            if os.path.exists(chunks_path):
                with open(chunks_path, "rb") as f:
                    _chunks = pickle.load(f)

# ---------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------

def embed(text: str) -> List[float]:
    model = _load_model()
    # ensure it's returned as a list of floats
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
# Search
# ---------------------------------------------------------------------

def search(query: str, top_k: int = None, min_score: float = 0.0) -> List[CorpusHit]:
    top_k = top_k or settings.TOP_K

    model = _load_model()
    _load_faiss()

    if _index is None or _chunks is None:
        return []

    with _model_lock:
        query_embedding = model.encode(["query: " + query], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)

    distances, indices = _index.search(query_embedding, k=top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        score = float(distances[0][i])
        norm_score = min(max(score, 0.0), 1.0)
        if norm_score < min_score:
            continue

        chunk = _chunks[idx]
        title = chunk.get("title", f"GR {chunk.get('gr_id', 'Unknown')}")

        hit = CorpusHit(
            gr_id=chunk.get("gr_id", "Unknown"),
            title=title,
            department=chunk.get("department", "Unknown"),
            issued_on=chunk.get("issued_on"),
            snippet=chunk.get("text", "")[:800],
            score=norm_score,
            source_url=f"https://gr.maharashtra.gov.in/{chunk.get('gr_id', '')}"
        )
        results.append(hit)

    return results

def lookup_by_gr_number(gr_number: str) -> Optional[CorpusHit]:
    # In FAISS we would need to iterate through chunks or have a separate metadata dict.
    _load_faiss()
    if _chunks is None:
        return None
        
    for chunk in _chunks:
        if chunk.get("gr_id") == gr_number:
            title = chunk.get("title", f"GR {chunk.get('gr_id', 'Unknown')}")
            return CorpusHit(
                gr_id=chunk.get("gr_id", "Unknown"),
                title=title,
                department=chunk.get("department", "Unknown"),
                issued_on=chunk.get("issued_on"),
                snippet=chunk.get("text", "")[:1000],
                score=1.0,
                source_url=f"https://gr.maharashtra.gov.in/{chunk.get('gr_id', '')}"
            )
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
    
    # Extract department and title from chunks if available
    department = "Unknown Department"
    title = f"GR {gr_id}"
    if gr_chunks:
        department = gr_chunks[0].get("department", department)
        title = gr_chunks[0].get("title", title)

    full_text = None
    if language:
        # First, check FAISS chunks for the language
        lang_chunks = [c for c in gr_chunks if c.get("language") == language]
        if lang_chunks:
            lang_chunks.sort(key=lambda x: x.get("chunk_id", 0))
            full_text = "\n\n".join(c.get("text", "") for c in lang_chunks)
        else:
            # Fallback: load directly from local disk txt files
            full_text = load_ocr_from_disk(gr_id, language)
    else:
        # No language specified, stitch whatever chunks we have
        if gr_chunks:
            gr_chunks.sort(key=lambda x: x.get("chunk_id", 0))
            full_text = "\n\n".join(c.get("text", "") for c in gr_chunks)

    # Absolute fallback: if still empty, check disk for either language
    if not full_text:
        for fallback_lang in ["mr", "en"]:
            full_text = load_ocr_from_disk(gr_id, fallback_lang)
            if full_text:
                break

    if not full_text:
        return None

    # Return a dictionary with metadata and full text
    return {
        "gr_id": gr_id,
        "department": department,
        "title": title,
        "text": full_text
    }

def is_connected() -> bool:
    _load_faiss()
    return _index is not None and _chunks is not None
