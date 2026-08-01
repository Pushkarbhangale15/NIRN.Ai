"""image_extract.py — Task 2a: .png/.jpg/.jpeg/.webp -> OCR directly.

Images have no text layer to check for, so this always goes straight to
OCR (see document_extraction/ocr.py for the preprocessing + Tesseract
call itself).
"""

import io

from PIL import Image

from document_extraction.ocr import ocr_image


def extract_image(content: bytes) -> tuple[str, float]:
    """Returns (plain_text, mean_ocr_confidence)."""
    image = Image.open(io.BytesIO(content))
    return ocr_image(image)
