"""
retrieval.py — semantic search over the GR corpus.

PRASAD OWNS THIS FILE. It is a STUB: it returns believable fake results
so that everyone else's work runs today.

Two jobs live here, deliberately merged into one file so that one person
owns one file:
    1. embedding  — turning text into vectors
    2. searching  — asking Qdrant for the nearest vectors

An "embedding" is a list of numbers representing the meaning of a piece
of text. Two texts about the same thing produce similar number lists,
which is what makes search-by-meaning work — a query about "late
admission" finds a passage saying "delayed enrolment procedure" even
though no word matches.

THE CONTRACT — do not change these signatures, everything else depends
on them:

    embed(text)                  -> List[float]
    embed_batch(texts)           -> List[List[float]]
    search(query, top_k)         -> List[CorpusHit]
    is_connected()               -> bool
"""

from typing import List

from config import settings
from schemas import CorpusHit

# Loaded once at module level on Day 2, never inside a function —
# reloading a sentence-transformer per request costs seconds.
_model = None


# ---------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------

def embed(text: str) -> List[float]:
    """
    Turn one piece of text into a vector.

    TODO (Prasad, Day 2):
        global _model
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return _model.encode(text).tolist()

    Suggested model (already in config): paraphrase-multilingual-MiniLM-L12-v2
    — 384 dimensions, handles Marathi and English, runs on CPU.

    Whatever model you pick, settings.EMBEDDING_DIMENSION must match its
    output size or every insert into Qdrant is rejected with a size error.
    """
    return [0.0] * settings.EMBEDDING_DIMENSION


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Batch version. Far faster than looping over embed() — the model can
    process many texts in one pass. Use this when ingesting the corpus.
    """
    return [embed(text) for text in texts]


def chunk_text(text: str,
               max_chars: int = None,
               overlap: int = None) -> List[str]:
    """
    Split a long GR into overlapping pieces before embedding.

    Overlap matters: if a clause happens to land exactly on a chunk
    boundary, the overlap ensures it still appears whole inside one of
    the chunks. Without it, retrieval silently misses clauses.
    """
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

_FAKE_CORPUS = [
    {
        "gr_id": "gr-2019-0252",
        "title": "Revision of lateral entry intake in technical institutions",
        "department": "Higher and Technical Education Department",
        "issued_on": "2019-07-02",
        "snippet": (
            "Lateral entry seats shall be fixed at ten percent of the sanctioned "
            "intake of the corresponding first-year course."
        ),
    },
    {
        "gr_id": "gr-2021-0088",
        "title": "Tuition Fee Waiver Scheme eligibility criteria",
        "department": "Higher and Technical Education Department",
        "issued_on": "2021-03-15",
        "snippet": (
            "Eligibility under the Tuition Fee Waiver Scheme shall be restricted "
            "to candidates whose annual family income does not exceed the "
            "prescribed limit."
        ),
    },
    {
        "gr_id": "gr-2022-0431",
        "title": "Scholarship disbursement procedure for backward class students",
        "department": "Social Justice and Special Assistance Department",
        "issued_on": "2022-09-08",
        "snippet": (
            "Scholarship amounts shall be credited directly to the beneficiary's "
            "account following verification by the head of the institution."
        ),
    },
    {
        "gr_id": "gr-2023-0117",
        "title": "Reservation of seats in professional courses",
        "department": "General Administration Department",
        "issued_on": "2023-01-24",
        "snippet": (
            "The category-wise reservation percentages notified herein shall "
            "apply to all professional courses conducted in the State."
        ),
    },
]


def search(query: str, top_k: int = None) -> List[CorpusHit]:
    """
    Find GR passages semantically similar to `query`.

    Note the fake corpus deliberately spans three different departments.
    Cross-departmental conflict is the whole point of Objective 1, so the
    stub data should exercise it rather than hide it.

    TODO (Prasad, Day 2):
        vector = embed(query)
        points = client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vector,
            limit=top_k,
        )
        return [CorpusHit(**point.payload, score=point.score) for point in points]
    """
    top_k = top_k or settings.TOP_K
    return [
        CorpusHit(
            **record,
            score=round(0.92 - index * 0.07, 3),
            source_url=f"https://gr.maharashtra.gov.in/{record['gr_id']}",
        )
        for index, record in enumerate(_FAKE_CORPUS[:top_k])
    ]


def lookup_by_gr_number(gr_number: str) -> CorpusHit | None:
    """
    Exact lookup by GR number, used by references.py to check whether a
    cited GR exists and is still in force.

    This is NOT semantic search — it is an exact match on a metadata
    field, so on Day 2 use a Qdrant payload filter, not a vector query.
    """
    return None


def is_connected() -> bool:
    """Whether Qdrant is reachable. Surfaced on /health."""
    return False  # replace with a real ping on Day 2
