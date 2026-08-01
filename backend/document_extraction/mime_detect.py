"""
mime_detect.py — validates the REAL file type by sniffing bytes with
libmagic, never by trusting the filename extension (a renamed .exe with
a .docx extension must not sail through).
"""

import zipfile
from io import BytesIO

import magic

from document_extraction.errors import UnsupportedFileTypeError

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ALLOWED_MIME_TO_KIND = {
    _DOCX_MIME: "docx",
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "text/plain": "txt",
}


def _looks_like_docx(content: bytes) -> bool:
    """libmagic sometimes reports a .docx as generic 'application/zip'
    depending on the installed magic database version. A .docx is
    specifically a zip that contains word/document.xml — check that
    directly rather than trusting the extension."""
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            return "word/document.xml" in zf.namelist()
    except zipfile.BadZipFile:
        return False


def detect_kind(content: bytes) -> str:
    mime = magic.from_buffer(content, mime=True)
    kind = ALLOWED_MIME_TO_KIND.get(mime)

    if kind is None and mime in ("application/zip", "application/octet-stream"):
        if _looks_like_docx(content):
            kind = "docx"

    if kind is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type ({mime}). Upload a .docx, .pdf, .png, "
            f".jpg, .jpeg, .webp, or .txt file."
        )
    return kind
