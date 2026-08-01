"""
pipeline.py — Task 2a: routes an uploaded file to the cheapest, most
accurate extraction path for its real type, then converts the result to
Tiptap-compatible HTML.

    .docx                     -> python-docx (direct structure)
    .pdf, has a text layer    -> PyMuPDF text extraction
    .pdf, no text layer       -> PyMuPDF rasterise + OCR
    .png/.jpg/.jpeg/.webp     -> OCR directly
    .txt                      -> read as-is

OCR is the LAST resort, not the default.
"""

from dataclasses import dataclass
from typing import Optional

from document_extraction import mime_detect
from document_extraction.docx_extract import extract_docx
from document_extraction.errors import UnsupportedFileTypeError
from document_extraction.html_convert import clean_text, text_to_html
from document_extraction.image_extract import extract_image
from document_extraction.pdf_extract import extract_pdf


@dataclass
class ExtractionResult:
    html: str
    plain_text: str
    kind: str                       # docx | pdf | image | txt
    used_ocr: bool
    ocr_confidence: Optional[float]  # None unless OCR actually ran


def extract_document(content: bytes) -> ExtractionResult:
    kind = mime_detect.detect_kind(content)

    if kind == "docx":
        html_out, plain = extract_docx(content)
        return ExtractionResult(html=html_out, plain_text=plain, kind=kind, used_ocr=False, ocr_confidence=None)

    if kind == "pdf":
        plain, used_ocr, confidence = extract_pdf(content)
        return ExtractionResult(
            html=text_to_html(plain), plain_text=clean_text(plain),
            kind=kind, used_ocr=used_ocr, ocr_confidence=confidence,
        )

    if kind == "image":
        plain, confidence = extract_image(content)
        return ExtractionResult(
            html=text_to_html(plain), plain_text=clean_text(plain),
            kind=kind, used_ocr=True, ocr_confidence=confidence,
        )

    if kind == "txt":
        text = content.decode("utf-8", errors="replace")
        return ExtractionResult(
            html=text_to_html(text), plain_text=clean_text(text),
            kind=kind, used_ocr=False, ocr_confidence=None,
        )

    raise UnsupportedFileTypeError(f"Unsupported file kind: {kind}")
