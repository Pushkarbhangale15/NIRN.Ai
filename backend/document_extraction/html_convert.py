"""
html_convert.py — Task 2c: turn extracted plain text into
Tiptap-compatible HTML.

The editor needs HTML, not a plain string, and OCR/PDF-extracted text
must never be dumped in as one giant paragraph — newlines have to
become real block structure or they collapse into a run-on sentence.
"""

import html
import re
import unicodedata

# Reuse the GR-number patterns already built and tuned in references.py —
# the task is explicit that this must not be a second regex.
from references import _ANNOUNCE_PATTERN, _EN_PATTERN, _MR_PATTERN
from clause_numbering import leading_marker

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")

_SUBJECT_RE = re.compile(r"^\s*(विषय|Subject)\s*[:：]", re.IGNORECASE | re.UNICODE)
_REFERENCE_RE = re.compile(r"^\s*(संदर्भ|Reference)\s*[:：]", re.IGNORECASE | re.UNICODE)

_GR_NUMBER_PATTERNS = (_EN_PATTERN, _MR_PATTERN, _ANNOUNCE_PATTERN)


def clean_text(text: str) -> str:
    """Strip control characters and normalise to NFC. Devanagari from
    OCR frequently arrives decomposed (combining marks split from their
    base character) and renders wrong in the browser until normalised."""
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    return text


def _mark_gr_numbers(line: str) -> str:
    """Bold the first GR-number-shaped span found in a line, using the
    same patterns references.py uses to extract citations."""
    for pattern in _GR_NUMBER_PATTERNS:
        match = pattern.search(line)
        if match:
            span = match.group(0)
            start, end = match.span()
            return (
                html.escape(line[:start])
                + f"<strong>{html.escape(span)}</strong>"
                + html.escape(line[end:])
            )
    return html.escape(line)


def _block_to_html(block: str) -> str:
    lines = [ln for ln in block.split("\n") if ln.strip()]
    if not lines:
        return ""

    first = lines[0].strip()

    # "विषय:" / "Subject:" -> heading
    if _SUBJECT_RE.match(first):
        heading_text = "\n".join(lines).strip()
        return f"<h2>{html.escape(heading_text)}</h2>"

    # "संदर्भ:" / "Reference:" -> a reference list. The label line
    # becomes a lead-in paragraph; every following line is one <li>.
    if _REFERENCE_RE.match(first):
        label, _, rest_of_first = first.partition(":")
        if ":" not in first:
            label, _, rest_of_first = first.partition("：")
        items = [rest_of_first.strip()] + [ln.strip() for ln in lines[1:]]
        items = [i for i in items if i]
        out = f"<p><strong>{html.escape(label.strip())}:</strong></p>"
        if items:
            out += "<ol>" + "".join(f"<li>{_mark_gr_numbers(i)}</li>" for i in items) + "</ol>"
        return out

    # Numbered operative clauses ("1.", "2.", "१.", "२.") -> <ol>. A
    # block counts as a numbered list if every line opens with a number
    # — otherwise it's just a paragraph that happens to start with a
    # digit — OR if every line AFTER the first does, so a label line
    # like "Government Resolution:" or "शासन निर्णय:" leading into
    # numbered clauses in the same block is still recognised.
    parsed = [leading_marker(ln) for ln in lines]
    if all(parsed):
        items = "".join(f"<li>{_mark_gr_numbers(rest)}</li>" for _marker, rest in parsed)
        return f"<ol>{items}</ol>"

    if len(parsed) >= 3 and parsed[0] is None and all(parsed[1:]):
        lead_in = f"<p>{_mark_gr_numbers(lines[0])}</p>"
        items = "".join(f"<li>{_mark_gr_numbers(rest)}</li>" for _marker, rest in parsed[1:])
        return lead_in + f"<ol>{items}</ol>"

    # Plain paragraph. Soft line breaks inside one block (e.g. a
    # multi-line header/address) become <br/>, not a run-on sentence.
    return "<p>" + "<br/>".join(_mark_gr_numbers(ln.strip()) for ln in lines) + "</p>"


def text_to_html(text: str) -> str:
    """Plain extracted text -> Tiptap-compatible HTML block string."""
    text = clean_text(text)
    blocks = [b.strip() for b in _BLOCK_SPLIT_RE.split(text) if b.strip()]
    if not blocks:
        return "<p></p>"
    return "".join(_block_to_html(b) for b in blocks)
