"""
ocr_ingest/extract.py — OCR extraction for scanned GR images/PDFs.

Rasterizes PDFs (pdf2image/poppler) since these are scans, not text-layer
documents -- never assumes an embedded text layer exists. Preprocesses
each page image (grayscale, denoise, deskew, binarize) via OpenCV before
handing it to Tesseract, then runs the combined eng+mar language model in
one pass: GRs mix Marathi body text with English headers/GR numbers/scheme
names, and Tesseract's multi-language mode reads a mixed-script line
correctly within a single pass. A line that still scores below
OCR_CONFIDENCE_THRESHOLD is re-OCR'd against each single language (cropped
to just that line) and the higher-confidence result is kept -- a cheap,
targeted retry rather than re-running the whole page three times.
"""
import io
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageSequence

from config import settings

TESSERACT_LANG = "eng+mar"
_RETRY_LANGS = ["eng", "mar"]
_PDF_DPI = 300


@dataclass
class OcrBlock:
    text: str
    confidence: float  # 0-100, pytesseract's scale
    needs_review: bool


def extract_pages(file_bytes: bytes, file_type: str) -> List[Image.Image]:
    """One PIL Image per page. file_type is one of pdf/png/jpg/jpeg/tiff
    (lowercase, no leading dot)."""
    if file_type == "pdf":
        return convert_from_bytes(file_bytes, dpi=_PDF_DPI)

    img = Image.open(io.BytesIO(file_bytes))
    if file_type == "tiff" and getattr(img, "n_frames", 1) > 1:
        return [frame.convert("RGB").copy() for frame in ImageSequence.Iterator(img)]
    return [img.convert("RGB")]


def _preprocess(pil_image: Image.Image) -> np.ndarray:
    """Grayscale -> denoise -> deskew -> Otsu binarize. Returns a cv2 array
    ready for Tesseract."""
    gray = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Deskew: find the dominant text angle from the binarized image's
    # minimum-area bounding rect and rotate to correct it.
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    deskewed = denoised
    if len(coords) > 100:  # enough ink to trust an angle estimate
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) > 0.1:
            h, w = denoised.shape
            matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            deskewed = cv2.warpAffine(
                denoised, matrix, (w, h),
                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
            )

    _, binarized = cv2.threshold(deskewed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return binarized


def _group_lines(data: dict) -> dict:
    """pytesseract.image_to_data's Output.DICT groups words with
    (block_num, par_num, line_num) keys -- reassemble those into lines,
    each carrying its bounding box (for the single-language retry crop)
    and averaged confidence."""
    lines: dict = {}
    n = len(data["text"])
    for i in range(n):
        word = data["text"][i].strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        conf = float(data["conf"][i])
        entry = lines.setdefault(key, {
            "words": [], "confs": [],
            "left": data["left"][i], "top": data["top"][i],
            "right": data["left"][i] + data["width"][i],
            "bottom": data["top"][i] + data["height"][i],
        })
        entry["words"].append(word)
        if conf >= 0:  # Tesseract uses -1 for non-text regions
            entry["confs"].append(conf)
        entry["left"] = min(entry["left"], data["left"][i])
        entry["top"] = min(entry["top"], data["top"][i])
        entry["right"] = max(entry["right"], data["left"][i] + data["width"][i])
        entry["bottom"] = max(entry["bottom"], data["top"][i] + data["height"][i])
    return lines


def _retry_single_language(cv_image: np.ndarray, box: dict) -> tuple[str, float]:
    """Re-OCR just one line's bounding box against each single language;
    return the (text, confidence) of whichever scores higher."""
    pad = 4
    h, w = cv_image.shape
    crop = cv_image[
        max(0, box["top"] - pad):min(h, box["bottom"] + pad),
        max(0, box["left"] - pad):min(w, box["right"] + pad),
    ]
    best_text, best_conf = "", -1.0
    for lang in _RETRY_LANGS:
        data = pytesseract.image_to_data(crop, lang=lang, output_type=pytesseract.Output.DICT)
        words = [w.strip() for w in data["text"] if w.strip()]
        confs = [float(c) for c in data["conf"] if float(c) >= 0]
        if not words:
            continue
        conf = sum(confs) / len(confs) if confs else 0.0
        if conf > best_conf:
            best_text, best_conf = " ".join(words), conf
    return best_text, best_conf


def _ocr_page(cv_image: np.ndarray) -> List[OcrBlock]:
    data = pytesseract.image_to_data(cv_image, lang=TESSERACT_LANG, output_type=pytesseract.Output.DICT)
    lines = _group_lines(data)

    blocks: List[OcrBlock] = []
    for key in sorted(lines.keys()):
        entry = lines[key]
        text = " ".join(entry["words"])
        confidence = sum(entry["confs"]) / len(entry["confs"]) if entry["confs"] else 0.0

        if confidence < settings.OCR_CONFIDENCE_THRESHOLD:
            retry_text, retry_conf = _retry_single_language(cv_image, entry)
            if retry_conf > confidence and retry_text:
                text, confidence = retry_text, retry_conf

        blocks.append(OcrBlock(
            text=text,
            confidence=confidence,
            needs_review=confidence < settings.OCR_CONFIDENCE_THRESHOLD,
        ))
    return blocks


def ocr_document(file_bytes: bytes, file_type: str) -> List[OcrBlock]:
    """Full pipeline: rasterize/open -> preprocess -> Tesseract, per page.
    Returns an ordered list of OcrBlock spanning the whole document --
    page breaks are just adjacent blocks in this list."""
    pages = extract_pages(file_bytes, file_type)
    all_blocks: List[OcrBlock] = []
    for page_image in pages:
        cv_image = _preprocess(page_image)
        all_blocks.extend(_ocr_page(cv_image))
    return all_blocks
