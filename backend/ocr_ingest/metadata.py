"""
ocr_ingest/metadata.py — extract GR number, date, department, and subject
from cleaned OCR text. Regex/lookup first (these follow regular formats in
real GRs); LLM fills in whatever's still missing after that, in one call
covering every remaining field rather than one call per field.
"""
import re
from typing import List, Optional

import llm
from knowledge import get_knowledge_service
from prompts import _ENGLISH_MONTHS, _MARATHI_MONTHS
from references import _EN_PATTERN, _MR_PATTERN

_DEVANAGARI_TO_ARABIC = str.maketrans("०१२३४५६७८९", "0123456789")

_MR_MONTH_TO_NUM = {name: i + 1 for i, name in enumerate(_MARATHI_MONTHS)}
_EN_MONTH_TO_NUM = {name.lower(): i + 1 for i, name in enumerate(_ENGLISH_MONTHS)}

# "दिनांक: ..." / "Dated: ..." label, same vocabulary template_rules.py's
# MOP-004 check already validates presence of -- this extracts the value.
_DATE_LABEL_RE = re.compile(r"(?:दिनांक|dated?)\s*[:\s]+([^\n]{6,40})", re.IGNORECASE | re.UNICODE)
_NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
_NAMED_DATE_RE = re.compile(r"([०-९0-9]{1,2})[ \t]+([ऀ-ॿa-zA-Z]+)[, \t]+([०-९0-9]{4})", re.UNICODE)

_DEPARTMENT_LINE_RE = re.compile(
    # [ ,] (literal space/comma), not \s -- \s matches newlines too, which
    # let this greedily span into the PRECEDING header line ("महाराष्ट्र
    # शासन\nसामान्य प्रशासन विभाग" as one match instead of just the
    # department line) and fail the canonical-department lookup entirely.
    r"([ऀ-ॿ][ऀ-ॿ ,]{2,60}विभाग|[A-Za-z][A-Za-z ,&]{2,60}Department)"
)
_SUBJECT_LINE_RE = re.compile(r"(?:विषय|Subject)\s*[:\-]\s*(.+)", re.IGNORECASE)


def extract_gr_number(text: str) -> Optional[str]:
    for pattern in (_EN_PATTERN, _MR_PATTERN):
        m = pattern.search(text)
        if m:
            return m.group(0)

    # references.py's _MR_PATTERN hardcodes an ASCII "19"/"20" year prefix,
    # but real generated GR numbers commonly render the year in Devanagari
    # digits even in an otherwise-Marathi number (e.g. "जीए-२०२६/...").
    # str.translate() with a single-char-to-single-char digit mapping is
    # index-preserving, so matching against a digit-normalized copy and
    # slicing the SAME span out of the original text recovers the number
    # in its original (Devanagari-year) form rather than a translated one.
    normalized = text.translate(_DEVANAGARI_TO_ARABIC)
    m = _MR_PATTERN.search(normalized)
    if m:
        return text[m.start():m.end()]
    return None


def extract_date(text: str) -> Optional[str]:
    label_match = _DATE_LABEL_RE.search(text)
    window = label_match.group(1) if label_match else text[:400]

    m = _NUMERIC_DATE_RE.search(window)
    if m:
        day, month, year = m.groups()
        year = year if len(year) == 4 else f"20{year}"
        return f"{int(day):02d}.{int(month):02d}.{year}"

    m = _NAMED_DATE_RE.search(window)
    if m:
        day_raw, month_name, year_raw = m.groups()
        day = day_raw.translate(_DEVANAGARI_TO_ARABIC)
        year = year_raw.translate(_DEVANAGARI_TO_ARABIC)
        month_num = _MR_MONTH_TO_NUM.get(month_name) or _EN_MONTH_TO_NUM.get(month_name.lower())
        if month_num:
            return f"{int(day):02d}.{month_num:02d}.{year}"
    return None


def extract_department(text: str) -> Optional[str]:
    """Match a "...विभाग"/"...Department" span in the header, then
    canonicalize it against the known department list -- the raw OCR span
    is rarely byte-exact, so a fuzzy KnowledgeService lookup is what makes
    this usable rather than just a regex capture."""
    m = _DEPARTMENT_LINE_RE.search(text[:600])
    if not m:
        return None
    candidate = m.group(1).strip()
    entry = get_knowledge_service().find_department(candidate)
    if not entry:
        return None
    english = entry.get("english", "")
    return english.replace(" ", "_") if english else None


def extract_subject(text: str) -> Optional[str]:
    m = _SUBJECT_LINE_RE.search(text)
    if not m:
        return None
    return m.group(1).strip().split("\n")[0][:200] or None


def extract_metadata(text: str) -> dict:
    gr_number = extract_gr_number(text)
    date = extract_date(text)
    department = extract_department(text)
    subject = extract_subject(text)

    fields = {"gr_number": gr_number, "date": date, "department": department, "subject": subject}
    missing = [name for name, value in fields.items() if value is None]
    extraction_method = "regex"

    if missing:
        llm_result = _llm_fill_missing(text, missing)
        for name in missing:
            fields[name] = fields[name] or llm_result.get(name)
        # The LLM returns whatever department text it found, not
        # necessarily the canonical slug -- run it through the same
        # lookup the regex path uses so pipeline.py's department-code /
        # cross-department logic gets a slug either way.
        if "department" in missing and fields["department"]:
            entry = get_knowledge_service().find_department(fields["department"])
            if entry and entry.get("english"):
                fields["department"] = entry["english"].replace(" ", "_")
        extraction_method = "regex+llm" if any(fields.values()) else "llm"

    fields["extraction_method"] = extraction_method
    return fields


def _llm_fill_missing(text: str, missing_fields: List[str]) -> dict:
    system_prompt = (
        "You extract structured metadata from a Maharashtra Government "
        "Resolution's OCR'd text, which may contain scan artifacts. Return "
        "ONLY a raw JSON object with exactly these keys: "
        f"{', '.join(missing_fields)}. Use null for any field you cannot "
        "find with reasonable confidence in the text -- never guess or "
        "fabricate a value."
    )
    user_msg = f"OCR TEXT:\n{text[:2000]}"
    raw = llm.call_model(system_prompt, user_msg)
    parsed = llm.parse_json_reply(raw)
    return parsed if isinstance(parsed, dict) else {}
