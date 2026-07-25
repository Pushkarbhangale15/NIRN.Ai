"""
retrieval.py — semantic search over the GR corpus.

Integrated with Prasad's FAISS implementation.
"""

from typing import List, Optional
import os
import faiss
import pickle
import numpy as np

from config import settings
from schemas import CorpusHit

_model = None
_index = None
_chunks = None

def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _model

def _load_faiss():
    global _index, _chunks
    
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
    return model.encode([text], convert_to_numpy=True)[0].tolist()

def embed_batch(texts: List[str]) -> List[List[float]]:
    model = _load_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
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

def search(query: str, top_k: int = None) -> List[CorpusHit]:
    top_k = top_k or settings.TOP_K
    
    model = _load_model()
    _load_faiss()

    if _index is None or _chunks is None:
        return []

    query_embedding = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)
    
    distances, indices = _index.search(query_embedding, k=top_k)
    
    results = []
    for i, idx in enumerate(indices[0]):
        # Distance might be Euclidean distance or Inner Product depending on FAISS index.
        # Since it's normalized L2, score can be derived from distance.
        score = float(distances[0][i])
        
        chunk = _chunks[idx]
        
        # schemas.CorpusHit requires title. We mock it if absent.
        title = chunk.get("title", f"GR {chunk.get('gr_id', 'Unknown')}")
        
        hit = CorpusHit(
            gr_id=chunk.get("gr_id", "Unknown"),
            title=title,
            department=chunk.get("department", "Unknown"),
            issued_on=chunk.get("issued_on"),
            snippet=chunk.get("text", "")[:1000],  # Give a snippet of max 1000 chars
            score=min(max(score, 0.0), 1.0), # Ensure it fits in [0, 1] per schema
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

def is_connected() -> bool:
    _load_faiss()
    return _index is not None and _chunks is not None
