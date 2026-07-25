"""
references.py — Objective 3: pull GR citations out of draft text.

NOT A STUB. This genuinely works today.

GR numbers follow recognisable patterns, and regular expressions handle
them faster, cheaper and more reliably than any language model would.
Reserve the model for the parts that need judgement.

Real formats seen in Maharashtra GRs:
    GR No CTC-2019/Pr.Kra.252/TE-04
    शासन निर्णय क्रमांक: संकीर्ण-2019/प्र.क्र.252/तां.शि.-4
    Government Resolution No. TEM-2021/CR-45/TE-1

Shared skeleton:
    <PREFIX>-<YEAR>/<CASE NUMBER>/<DESK CODE>
"""

import re
from typing import List, Set

from schemas import GRStatus, ReferenceHit

# Latin-script GR numbers.
# Reads as: 2-8 capitals, dash, 4-digit year, slash, case chunk,
# slash, desk code.
_EN_PATTERN = re.compile(
    r"(?P<prefix>[A-Z]{2,8})[-–](?P<year>(?:19|20)\d{2})"
    r"/(?P<case>[A-Za-z.]{0,12}\.?\s?\d{1,5})"
    r"/(?P<desk>[A-Za-z.]{1,10}[-–]?\d{0,3})",
    re.UNICODE,
)

# Devanagari-script GR numbers (Marathi originals).
# \u0900-\u097F is the Devanagari block.
_MR_PATTERN = re.compile(
    r"(?P<prefix>[\u0900-\u097F]{2,15})[-–](?P<year>(?:19|20)\d{2})"
    r"/(?P<case>[\u0900-\u097F.]{0,12}\.?\s?\d{1,5})"
    r"/(?P<desk>[\u0900-\u097F.]{1,12}[-–]?\d{0,3})",
    re.UNICODE,
)

# Fallback for citations that announce themselves but use an odd format.
_ANNOUNCE_PATTERN = re.compile(
    r"(?:G\.?R\.?\s*No\.?|Government\s+Resolution\s+No\.?|शासन\s+निर्णय\s+क्रमांक)"
    r"\s*[:\-]?\s*(?P<ref>\S{6,60})",
    re.IGNORECASE | re.UNICODE,
)


def extract_references(text: str) -> List[ReferenceHit]:
    """
    Find every GR citation in the draft.

    Deduplicated (the same GR cited three times yields one hit) and
    position-tagged so the frontend can highlight each occurrence.
    """
    hits: List[ReferenceHit] = []
    seen: Set[str] = set()

    for pattern in (_EN_PATTERN, _MR_PATTERN):
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            key = _normalise(raw)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                ReferenceHit(
                    raw_text=raw,
                    gr_number=key,
                    year=int(match.group("year")),
                    char_offset=match.start(),
                )
            )

    for match in _ANNOUNCE_PATTERN.finditer(text):
        raw = match.group("ref").strip().rstrip(".,;")
        key = _normalise(raw)
        if key in seen or len(key) < 6:
            continue
        seen.add(key)
        year_match = re.search(r"(19|20)\d{2}", raw)
        hits.append(
            ReferenceHit(
                raw_text=raw,
                gr_number=key,
                year=int(year_match.group(0)) if year_match else None,
                char_offset=match.start("ref"),
            )
        )

    hits.sort(key=lambda h: h.char_offset)
    return hits


def _normalise(raw: str) -> str:
    """
    Strip spaces and unify dash characters so that the same GR written
    two slightly different ways collapses to one entry.
    """
    return re.sub(r"\s+", "", raw).replace("–", "-").upper()


def resolve_against_corpus(hits: List[ReferenceHit]) -> List[ReferenceHit]:
    """
    Check each citation against the GR corpus: does it exist, and is it
    still in force?
    """
    import retrieval
    
    for hit in hits:
        # Search the corpus for the GR number or raw text
        query = hit.gr_number or hit.raw_text
        search_results = retrieval.search(query, top_k=1)
        if search_results:
            top_hit = search_results[0]
            # Since reference text is very specific, if similarity is high (e.g. >= 0.70)
            # we consider it resolved successfully.
            if top_hit.score >= 0.70:
                hit.found_in_corpus = True
                hit.status = GRStatus.IN_FORCE
                hit.corpus_gr_id = top_hit.gr_id
                hit.corpus_title = top_hit.title
            else:
                hit.found_in_corpus = False
                hit.status = GRStatus.UNKNOWN
        else:
            hit.found_in_corpus = False
            hit.status = GRStatus.UNKNOWN
    return hits
