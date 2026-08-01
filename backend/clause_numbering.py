"""
clause_numbering.py — the single parser for "does this line open with a
clause number" ('1.', '2)', Devanagari '१.', or a sub-clause like
'4(b)').

document_extraction/html_convert.py uses `leading_marker` to build <ol>
markup for uploaded/converted drafts. conflict_detection uses
`clause_ref` to attach a human-readable clause reference to each
detected conflict. One parser, reused by both — not a second one built
from scratch for conflicts.
"""

import re

LATIN_NUM_RE = re.compile(r"^\s*(\d{1,3})[.)]\s+(.*)$")
DEVANAGARI_NUM_RE = re.compile(r"^\s*([०-९]{1,3})[.)]\s+(.*)$")

# A sub-clause marker directly after the top-level number, e.g. "4(b)"
# or "४(ब)" — only matched at the very start of the line, never searched
# for inside a paragraph, so this never "guesses" which part matched.
_SUBCLAUSE_RE = re.compile(r"^\s*(\d{1,3}|[०-९]{1,3})\s*\(([a-zA-Zअ-ह]{1,3})\)")


def leading_marker(line: str) -> tuple[str, str] | None:
    """Returns (marker, rest) if `line` opens a numbered clause — '1.',
    '2)', or Devanagari '१.', '२.' — else None. `line` must be a single
    line (no embedded newlines); callers pass one line at a time."""
    m = LATIN_NUM_RE.match(line) or DEVANAGARI_NUM_RE.match(line)
    if not m:
        return None
    return m.group(1), m.group(2)


def clause_ref(block: str) -> str | None:
    """Best-effort 'Clause N' / 'Clause N(x)' label for the first line of
    a clause/text block. Returns None when the block doesn't open with a
    recognisable marker — callers must never guess a clause number."""
    if not block or not block.strip():
        return None
    first_line = block.strip().splitlines()[0]
    sub = _SUBCLAUSE_RE.match(first_line)
    if sub:
        return f"Clause {sub.group(1)}({sub.group(2)})"
    marker = leading_marker(first_line)
    if marker:
        return f"Clause {marker[0]}"
    return None
