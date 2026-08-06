"""
ocr_ingest/clean.py — normalize raw OCR block text into the paragraph/
clause structure conflict_detection's clause splitter
(_extract_operative_clauses) expects: numbered clauses on their own line,
ordinary paragraphs otherwise, no stray mid-word line breaks.
"""
import re
from typing import List, Tuple

from .extract import OcrBlock

# Common Tesseract misreads seen on Devanagari + Latin mixed GR scans.
# Deliberately empty at ship time -- a blind global string-replace table is
# risky to seed with guesses (e.g. correcting a lone "l" to "1" would also
# mangle "et al." or ordinary Marathi words), so entries should only be
# added once confirmed as a *recurring* misread on real scanned output.
# See OCR_CONFIDENCE_THRESHOLD's tuning note in config.py -- same
# "tune after real-world testing" philosophy applies here.
_MISREAD_CORRECTIONS: dict = {}

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

# A line ending in sentence-final punctuation (English/Marathi full stop,
# danda, question/exclamation, or a trailing colon before a list) closes
# the paragraph; anything else is treated as a stray OCR line-break
# mid-sentence and joined to what follows.
_SENTENCE_END_RE = re.compile(r"[.।?!:]\s*$")

# Matches a line that opens a new numbered operative clause -- Arabic
# (01./1.) or Devanagari (०१./१.) -- same shape _extract_operative_clauses
# already splits on, so a clause boundary here must start a new paragraph
# rather than being absorbed into the previous one.
_CLAUSE_MARKER_RE = re.compile(r"^\s*(?:[0-9]+|[०-९]+)[.)]\s")


def _apply_corrections(text: str) -> str:
    for wrong, right in _MISREAD_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def clean_and_reassemble(blocks: List[OcrBlock]) -> Tuple[str, List[dict]]:
    """
    Returns (cleaned_text, low_confidence_spans). low_confidence_spans is
    a list of {"text": ..., "confidence": ...} for every OCR block that
    scored below OCR_CONFIDENCE_THRESHOLD -- pipeline.py correlates these
    against the clauses eventually extracted from cleaned_text to decide
    which resulting conflicts (if any) get source_ocr_low_confidence=True.
    """
    low_confidence_spans: List[dict] = []
    cleaned_lines: List[str] = []
    for block in blocks:
        text = _apply_corrections(block.text.strip())
        if not text:
            continue
        cleaned_lines.append(text)
        if block.needs_review:
            low_confidence_spans.append({"text": text, "confidence": block.confidence})

    paragraphs: List[str] = []
    buffer = ""
    for text in cleaned_lines:
        if _CLAUSE_MARKER_RE.match(text) and buffer:
            paragraphs.append(buffer.strip())
            buffer = text
        else:
            buffer = f"{buffer} {text}".strip()
        if _SENTENCE_END_RE.search(text):
            paragraphs.append(buffer.strip())
            buffer = ""
    if buffer:
        paragraphs.append(buffer.strip())

    cleaned = "\n\n".join(p for p in paragraphs if p)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_NEWLINE_RE.sub("\n\n", cleaned)
    return cleaned.strip(), low_confidence_spans
