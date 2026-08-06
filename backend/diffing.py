"""
diffing.py — word-level diff between two plain-text draft versions, for
the side-by-side DraftDiffView (reviewing officer's edits vs. the
drafting officer's original). Separate from db/integrity.py's SHA-256
hashing: that proves a version wasn't tampered with; this shows what
actually changed between two versions.

Operates on content_plain, never on the raw HTML `content` field —
diffing HTML tags directly produces unreadable noise.
"""

import difflib
import re
from typing import List, TypedDict


class DiffSegment(TypedDict):
    type: str  # 'equal' | 'insert' | 'delete'
    text: str


def _tokenize(text: str) -> List[str]:
    """Splits on whitespace boundaries but keeps the whitespace itself
    as its own token, so re-joining segments reproduces the original
    spacing instead of collapsing it."""
    return re.findall(r"\s+|\S+", text or "")


def compute_diff(text_before: str, text_after: str) -> List[DiffSegment]:
    before_tokens = _tokenize(text_before)
    after_tokens = _tokenize(text_after)
    matcher = difflib.SequenceMatcher(a=before_tokens, b=after_tokens, autojunk=False)

    segments: List[DiffSegment] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            segments.append({"type": "equal", "text": "".join(before_tokens[i1:i2])})
        elif tag == "delete":
            segments.append({"type": "delete", "text": "".join(before_tokens[i1:i2])})
        elif tag == "insert":
            segments.append({"type": "insert", "text": "".join(after_tokens[j1:j2])})
        elif tag == "replace":
            segments.append({"type": "delete", "text": "".join(before_tokens[i1:i2])})
            segments.append({"type": "insert", "text": "".join(after_tokens[j1:j2])})
    return segments


def diff_summary(segments: List[DiffSegment]) -> dict:
    """Word-count additions/deletions for the compact summary line
    ("N additions, N deletions") above the diff panes."""
    additions = sum(len(seg["text"].split()) for seg in segments if seg["type"] == "insert")
    deletions = sum(len(seg["text"].split()) for seg in segments if seg["type"] == "delete")
    return {"additions": additions, "deletions": deletions}
