"""
mime_detect.py — validates the REAL file type by sniffing bytes with
libmagic, never by trusting the filename extension (a renamed .exe with
a .docx extension must not sail through).
"""

import zipfile
from io import BytesIO

try:
    import magic
except ImportError:
    magic = None


def detect_kind(content: bytes) -> str:
    mime = None
    if magic is not None:
        try:
            mime = magic.from_buffer(content, mime=True)
        except Exception:
            mime = None

    # Pure byte magic number fallback if libmagic is unavailable or fails
    if mime is None:
        if content.startswith(b"%PDF"):
            mime = "application/pdf"
        elif content.startswith(b"\x89PNG"):
            mime = "image/png"
        elif content.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            mime = "image/webp"
        elif content.startswith(b"PK\x03\x04"):
            mime = _DOCX_MIME if _looks_like_docx(content) else "application/zip"
        else:
            try:
                content.decode("utf-8")
                mime = "text/plain"
            except UnicodeDecodeError:
                mime = "application/octet-stream"
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
