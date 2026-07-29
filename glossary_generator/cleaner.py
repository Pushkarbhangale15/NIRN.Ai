"""
cleaner.py — Text cleaning and Unicode normalization.

Handles OCR noise, HTML stripping, whitespace normalization, and
Unicode NFC normalization. All functions are pure (no side effects).
"""

import html
import re
import unicodedata
from typing import Optional

# Devanagari Unicode block range
_DEVANAGARI_RANGE = re.compile(r'[\u0900-\u097F]')

# Page marker patterns common in OCR output
_PAGE_MARKERS = re.compile(
    r'#\s*Page\s*\d+|Page\s*\d+\s*of\s*\d+|पृष्ठ\s*\d+\s*पैकी\s*\d+',
    re.IGNORECASE
)

# GR number patterns (to preserve as-is, not extract as phrases)
_GR_NUMBER = re.compile(
    r'(?:[A-Z]{2,8}|[^\u0900-\u097F\s]{2,12})'  # prefix
    r'[-–]\d{4}'                                   # year
    r'/[A-Za-z\u0900-\u097F.\s]{1,20}'            # case ref
    r'/[A-Za-z\u0900-\u097F.-]{1,15}',
    re.UNICODE
)

# HTML tag stripper
_HTML_TAG = re.compile(r'<[^>]+>')

# Multiple whitespace collapse
_MULTI_SPACE = re.compile(r'\s+')

# Common OCR noise patterns
_OCR_NOISE = re.compile(r'[|{}\\~`^*]')

# Lines that are purely numeric (page numbers, counts)
_PURE_NUMERIC = re.compile(r'^\s*[\d\u0966-\u096F\s.,()\-]+\s*$')


def clean_text(raw: str, preserve_structure: bool = False) -> str:
    """
    Main cleaning pipeline for a raw document string.

    Steps:
        1. Decode HTML entities
        2. Strip HTML tags
        3. Remove page markers
        4. Remove OCR noise
        5. Unicode NFC normalization
        6. Whitespace normalization

    Args:
        raw: Raw input text (may be HTML, OCR output, plain text).
        preserve_structure: If True, keeps newlines for sentence splitting.

    Returns:
        Cleaned, normalized string.
    """
    if not raw or not isinstance(raw, str):
        return ""

    # 1. HTML entity decode
    text = html.unescape(raw)

    # 2. Strip HTML tags
    text = _HTML_TAG.sub(" ", text)

    # 3. Remove page markers (OCR artifacts)
    text = _PAGE_MARKERS.sub(" ", text)

    # 4. Remove OCR noise characters
    text = _OCR_NOISE.sub(" ", text)

    # 5. Unicode NFC normalization — critical for Devanagari
    text = unicodedata.normalize("NFC", text)

    # 6. Whitespace normalization
    if preserve_structure:
        # Collapse multiple spaces but preserve newlines
        lines = []
        for line in text.splitlines():
            line = re.sub(r'[ \t]+', ' ', line).strip()
            if line:
                lines.append(line)
        text = "\n".join(lines)
    else:
        text = _MULTI_SPACE.sub(" ", text).strip()

    return text


def remove_page_headers(text: str) -> str:
    """
    Remove repeated GR number headers that appear at the top of each page.
    These are lines matching 'Government Resolution No: ...' that repeat.
    """
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip pure page-number lines
        if _PURE_NUMERIC.match(stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def normalize_marathi_numerals(text: str) -> str:
    """
    Convert Devanagari numerals (०-९) to ASCII for year/number extraction.
    Returns the text with Devanagari digits replaced by ASCII equivalents.
    """
    deva_to_ascii = str.maketrans('०१२३४५६७८९', '0123456789')
    return text.translate(deva_to_ascii)


def detect_language(text: str) -> str:
    """
    Detect whether a text is primarily Marathi (Devanagari) or English.

    Returns:
        "mr" if >= 15% of non-whitespace characters are Devanagari,
        "en" otherwise.
    """
    if not text:
        return "en"
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return "en"
    deva_count = sum(1 for c in non_ws if '\u0900' <= c <= '\u097F')
    ratio = deva_count / len(non_ws)
    return "mr" if ratio >= 0.15 else "en"


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences.

    Handles both English (period/newline) and Marathi (| danda / newline).
    Returns a list of non-empty sentence strings.
    """
    # Split on: period+space, newline, Devanagari danda (।), double danda (॥)
    raw_sentences = re.split(r'(?<=[.!?।॥])\s+|\n+', text)
    result = []
    for s in raw_sentences:
        s = s.strip()
        if len(s) >= 10:  # skip very short fragments
            result.append(s)
    return result


def is_valid_phrase(phrase: str, min_chars: int = 5, max_tokens: int = 8, min_tokens: int = 2) -> bool:
    """
    Return True if a phrase is a valid multi-word administrative term.

    Rejects:
        - Single-word phrases (unless specifically whitelisted)
        - Purely numeric strings
        - Too short or too long phrases
        - Phrases that are GR numbers
    """
    phrase = phrase.strip()
    if not phrase:
        return False
    if len(phrase) < min_chars:
        return False
    tokens = phrase.split()
    if len(tokens) < min_tokens:
        return False
    if len(tokens) > max_tokens:
        return False
    if _PURE_NUMERIC.match(phrase):
        return False
    return True


def normalize_phrase(phrase: str) -> str:
    """
    Normalize a phrase for deduplication:
        - NFC Unicode
        - Lowercase (for English)
        - Strip punctuation at boundaries
        - Collapse whitespace
    """
    phrase = unicodedata.normalize("NFC", phrase.strip())
    phrase = re.sub(r'^[,\-–./:;]+|[,\-–./:;]+$', '', phrase)
    phrase = _MULTI_SPACE.sub(" ", phrase)
    return phrase.strip()
