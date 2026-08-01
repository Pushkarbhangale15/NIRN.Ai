"""
ocr.py — Task 2b: Tesseract OCR with preprocessing, tuned for mixed
Devanagari + Latin GR scans.

OCR is the LAST resort in the extraction pipeline (see pipeline.py) —
called only for images and PDF pages with no text layer.
"""

import logging

import cv2
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from config import OCR_LANGUAGES, settings
from document_extraction.errors import OcrUnavailableError

logger = logging.getLogger(settings.APP_NAME)

_availability_checked = False


def ensure_tesseract_available() -> None:
    """Checked lazily, only when a request actually needs OCR — a
    missing Tesseract install must never block docx/digital-PDF/txt
    uploads, which don't need it at all. Cached after the first
    successful check so we're not shelling out to `tesseract` on every
    request."""
    global _availability_checked
    if _availability_checked:
        return

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise OcrUnavailableError(
            "OCR is not available on this server: the Tesseract binary isn't "
            "installed. Ask an administrator to install it (macOS: "
            "`brew install tesseract tesseract-lang`) — see backend/README.md."
        ) from exc

    try:
        installed_langs = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise OcrUnavailableError(
            "OCR is not available on this server: could not list installed "
            "Tesseract languages. See backend/README.md."
        ) from exc

    missing = {"mar", "eng"} - installed_langs
    if missing:
        raise OcrUnavailableError(
            f"OCR is not available: missing Tesseract language data for "
            f"{', '.join(sorted(missing))}. Install with `brew install "
            f"tesseract-lang` (macOS) — see backend/README.md."
        )

    _availability_checked = True


def _preprocess(image: Image.Image) -> Image.Image:
    """Greyscale, upscale toward ~300 DPI, adaptive threshold. Raw phone
    photos OCR badly without this — Tesseract expects clean black-on-white
    scanned-document contrast, not a photo's lighting gradient."""
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # A4 at 300 DPI is roughly 2480x3508px. Upscale (never downscale) so
    # the longest edge is at least ~2800px — most phone/scan uploads
    # arrive well under that.
    longest_edge = max(gray.shape)
    target = 2800
    if longest_edge < target:
        scale = target / longest_edge
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return Image.fromarray(thresh)


def ocr_image(image: Image.Image) -> tuple[str, float]:
    """Returns (text, mean_confidence 0-100). Language string is
    'mar+eng' so a single pass recognises both Devanagari and Latin
    script in the same document — a GR often mixes both."""
    ensure_tesseract_available()

    processed = _preprocess(image)
    data = pytesseract.image_to_data(processed, lang=OCR_LANGUAGES, output_type=Output.DICT)

    words = []
    confidences = []
    for text, conf in zip(data["text"], data["conf"]):
        text = text.strip()
        if not text:
            continue
        words.append(text)
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_val >= 0:
            confidences.append(conf_val)

    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    plain_text = pytesseract.image_to_string(processed, lang=OCR_LANGUAGES)
    return plain_text, mean_confidence
