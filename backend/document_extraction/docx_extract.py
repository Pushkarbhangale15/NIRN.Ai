"""
docx_extract.py — Task 2a: .docx -> Tiptap HTML via python-docx.

Reads paragraphs and runs directly rather than falling back to OCR —
python-docx gives real structure (headings, bold/italic, lists) for
free, which is faster and far more accurate than flattening to plain
text and re-guessing that structure back with regex.
"""

import html
from io import BytesIO

from docx import Document

from document_extraction.html_convert import clean_text

_HEADING_TAGS = {
    "Title": "h1",
    "Heading 1": "h1",
    "Heading 2": "h2",
    "Heading 3": "h3",
}


def _run_html(paragraph) -> str:
    parts = []
    for run in paragraph.runs:
        text = html.escape(clean_text(run.text))
        if not text:
            continue
        if run.bold and run.italic:
            text = f"<strong><em>{text}</em></strong>"
        elif run.bold:
            text = f"<strong>{text}</strong>"
        elif run.italic:
            text = f"<em>{text}</em>"
        parts.append(text)
    if parts:
        return "".join(parts)
    # Paragraphs with no distinguishable runs (e.g. from certain field
    # codes) still have a usable .text — fall back to that.
    return html.escape(clean_text(paragraph.text))


def extract_docx(content: bytes) -> tuple[str, str]:
    """Returns (html, plain_text)."""
    document = Document(BytesIO(content))

    html_parts: list[str] = []
    plain_parts: list[str] = []
    list_buffer: list[str] = []

    def flush_list():
        if list_buffer:
            items = "".join(f"<li>{item}</li>" for item in list_buffer)
            html_parts.append(f"<ol>{items}</ol>")
            list_buffer.clear()

    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text).strip()
        style_name = (paragraph.style.name if paragraph.style else "") or ""

        if not text:
            flush_list()
            continue

        plain_parts.append(text)

        if style_name in _HEADING_TAGS:
            flush_list()
            tag = _HEADING_TAGS[style_name]
            html_parts.append(f"<{tag}>{html.escape(text)}</{tag}>")
            continue

        if style_name.startswith("List"):
            list_buffer.append(_run_html(paragraph))
            continue

        flush_list()
        html_parts.append(f"<p>{_run_html(paragraph)}</p>")

    flush_list()

    html_out = "".join(html_parts) or "<p></p>"
    plain_out = "\n\n".join(plain_parts)
    return html_out, plain_out
