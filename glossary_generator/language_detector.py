"""
language_detector.py — Lightweight language detection for GR documents.

Provides probability-based detection rather than binary classification,
useful for borderline cases (e.g. GRs with mixed Marathi/English headers).
"""

import re
from typing import Tuple

# Devanagari Unicode block
_DEVANAGARI = re.compile(r'[\u0900-\u097F]')

# Common Marathi GR markers (unique to Marathi text)
_MR_MARKERS = [
    "शासन निर्णय", "महाराष्ट्र शासन", "शासन परिपत्रक",
    "विभाग", "मंत्रालय", "दिनांक", "संदर्भ", "शासन आदेश",
]

# Common English GR markers
_EN_MARKERS = [
    "Government Resolution", "Government of Maharashtra",
    "Department", "Mantralaya", "Dated", "Reference",
    "Government Order", "Government Circular",
]


def detect_language_probability(text: str) -> Tuple[str, float]:
    """
    Detect the primary language of a GR document.

    Returns:
        (language, confidence) where language is "en" or "mr".
        confidence is a float between 0.0 and 1.0.
    """
    if not text:
        return "en", 0.5

    total_chars = len([c for c in text if not c.isspace()])
    if total_chars == 0:
        return "en", 0.5

    deva_count = len(_DEVANAGARI.findall(text))
    deva_ratio = deva_count / total_chars

    # Score based on Devanagari ratio
    if deva_ratio >= 0.40:
        base_lang, base_conf = "mr", 0.85 + min(deva_ratio - 0.40, 0.15)
    elif deva_ratio >= 0.15:
        base_lang, base_conf = "mr", 0.65 + (deva_ratio - 0.15) * 0.8
    elif deva_ratio >= 0.05:
        # Mixed document
        base_lang, base_conf = "en", 0.55
    else:
        base_lang, base_conf = "en", 0.90

    # Boost confidence with marker presence
    marker_boost = 0.0
    if base_lang == "mr":
        for marker in _MR_MARKERS:
            if marker in text:
                marker_boost += 0.01
    else:
        for marker in _EN_MARKERS:
            if marker in text:
                marker_boost += 0.01

    confidence = min(base_conf + marker_boost, 1.0)
    return base_lang, round(confidence, 3)


def is_bilingual(text: str, threshold: float = 0.08) -> bool:
    """
    Return True if the text contains significant amounts of both
    English (ASCII) and Marathi (Devanagari) content.
    """
    total_chars = len([c for c in text if not c.isspace()])
    if total_chars == 0:
        return False

    deva_count = len(_DEVANAGARI.findall(text))
    ascii_alpha = sum(1 for c in text if c.isascii() and c.isalpha())

    deva_ratio = deva_count / total_chars
    ascii_ratio = ascii_alpha / total_chars

    return deva_ratio >= threshold and ascii_ratio >= threshold
