"""
document_extraction — turn an uploaded GR (Word/PDF/image/txt) into
Tiptap-compatible HTML for the draft editor.

Routing is cheapest-and-most-accurate-path-first (see extract_document
below): OCR is the last resort, not the default, since direct text
extraction is faster and far more accurate — especially for Devanagari.
"""

from document_extraction.errors import ExtractionError, UnsupportedFileTypeError
from document_extraction.pipeline import ExtractionResult, extract_document

__all__ = ["extract_document", "ExtractionResult", "ExtractionError", "UnsupportedFileTypeError"]
