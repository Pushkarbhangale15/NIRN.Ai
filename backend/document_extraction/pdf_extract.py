"""
pdf_extract.py — Task 2a: route a PDF by whether it has a real text
layer.

Digital PDF (has selectable text) -> PyMuPDF's own text extraction:
fast, exact, and handles Devanagari natively since it reads the font's
embedded character map rather than re-recognising glyphs.

Scanned PDF (no text layer, i.e. it's just page images) -> rasterise
each page with PyMuPDF and OCR it. This is the expensive, last-resort
path — never the default.
"""

import io

import fitz  # PyMuPDF
from PIL import Image

from document_extraction.ocr import ocr_image

# A digital page with real content easily clears this; a scanned page
# with no text layer returns ~0 characters from get_text().
_MIN_CHARS_FOR_DIGITAL_PAGE = 40
_OCR_ZOOM = 300 / 72  # render at ~300 DPI (PDF points are 72/inch)


def _has_text_layer(doc: "fitz.Document") -> bool:
    if doc.page_count == 0:
        return False
    return len(doc[0].get_text("text").strip()) >= _MIN_CHARS_FOR_DIGITAL_PAGE


def _rasterize_page(page: "fitz.Page") -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(_OCR_ZOOM, _OCR_ZOOM), alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def extract_pdf(content: bytes) -> tuple[str, bool, float | None]:
    """Returns (plain_text, used_ocr, mean_ocr_confidence_or_None)."""
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        if _has_text_layer(doc):
            text = "\n\n".join(page.get_text("text") for page in doc)
            return text, False, None

        # Scanned PDF: rasterise + OCR every page, average the
        # per-page confidences into one number for the response.
        page_texts = []
        confidences = []
        for page in doc:
            image = _rasterize_page(page)
            page_text, confidence = ocr_image(image)
            page_texts.append(page_text)
            confidences.append(confidence)

        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n\n".join(page_texts), True, mean_confidence
    finally:
        doc.close()
