"""
template_rules_marathi.py — Objective 4: Manual of Office Procedure enforcement for Marathi GRs.

Checks a draft GR body in Marathi against a set of structural and stylistic rules
derived from the Maharashtra Government's Manual of Office Procedure (MOP).

Updated to enforce the official Maharashtra Government परिपत्रक (Circular) format
as used in real GRs:

  महाराष्ट्र शासन
  [विभागाचे नाव]
  शासन परिपत्रक क्रमांक: [PREFIX]-[YEAR]/प्र.क्र.[NUMBER]/[DESK]-[NUMBER]
  हुतात्मा राजगुरु चौक, मादाम कामा मार्ग, मंत्रालय मुंबई-३२
  दिनांक: [DD Month, YYYY]

  वाचा:
  १. [Reference GR 1]
  २. [Reference GR 2]

  शासन परिपत्रक:
  [Background / preamble paragraph]

  ०१. [First operative clause]
  ०२. [Second operative clause]

  महाराष्ट्राचे राज्यपाल यांच्या आदेशानुसार व नावाने.

  [Officer Name]
  शासनाचे अवर सचिव

  प्रत,
  १. [Office 1]

All checks are purely rule-based (regex + heuristics). No LLM is involved.
"""

import re
from typing import Callable, List, Optional

from schemas import Severity, TemplateIssue


# =========================================================================
# Individual rule functions
# =========================================================================
# Each returns a TemplateIssue if the rule is violated, or None if OK.

def _check_mr001_header_govt(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-001 — Header must begin with 'महाराष्ट्र शासन'."""
    first_lines = text.strip()[:400]
    has_govt = bool(
        re.search(r"महाराष्ट्र\s+शासन", first_lines, re.UNICODE)
        # Also accept English fallback in case of mixed draft
        or re.search(r"government\s+of\s+maharashtra", first_lines, re.IGNORECASE)
    )
    if not has_govt:
        return TemplateIssue(
            rule_id="MOP-MR-001",
            severity=Severity.ERROR,
            message="Header must begin with 'महाराष्ट्र शासन'.",
            section="Header",
            suggestion="Add 'महाराष्ट्र शासन' as the first line of the document.",
        )
    return None


def _check_mr002_department_line(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-002 — Department name must exist (containing 'विभाग')."""
    first_lines = text.strip()[:600]
    has_dept = bool(
        re.search(r"विभाग", first_lines, re.UNICODE)
        or re.search(r"department", first_lines, re.IGNORECASE)
    )
    if not has_dept:
        return TemplateIssue(
            rule_id="MOP-MR-002",
            severity=Severity.ERROR,
            message="Department name is missing from the header block.",
            section="Header",
            suggestion="Add the issuing department name containing 'विभाग' (e.g. 'महसूल व वन विभाग' or 'उच्च व तंत्र शिक्षण विभाग').",
        )
    return None


def _check_mr003_gr_number(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-003 — Government Resolution/Circular Reference Number must be present."""
    has_grno = bool(
        # Primary official form: शासन परिपत्रक क्रमांक:
        re.search(r"शासन\s*परिपत्रक\s*क्रमांक\s*:", text, re.UNICODE)
        # Also accept: शासन निर्णय क्रमांक (for निर्णय-type GRs)
        or re.search(r"शासन\s*निर्णय\s*क्रमांक", text, re.UNICODE)
        # Bare क्रमांक: label
        or re.search(r"क्रमांक\s*:", text, re.UNICODE)
        # English fallback
        or re.search(r"(GR\s*No\.?|Government\s+Resolution\s+No\.?|Government\s+Circular\s+No\.?)", text, re.IGNORECASE)
    )
    if not has_grno:
        return TemplateIssue(
            rule_id="MOP-MR-003",
            severity=Severity.ERROR,
            message="Government Resolution reference number is missing.",
            section="Header",
            suggestion=(
                "Include a GR reference number in the format: "
                "'शासन परिपत्रक क्रमांक: XYZ-२०२६/प्र.क्र.०१/[DESK]-[NUMBER]'."
            ),
        )
    return None


def _check_mr004_date(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-004 — Date must be present (दिनांक:)."""
    has_date = bool(
        # Marathi: दिनांक: DD Month, YYYY
        re.search(r"दिनांक\s*[:\.]", text, re.UNICODE)
        # Numeric date
        or re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\b", text)
        # Marathi month names
        or re.search(
            r"\b(?:जानेवारी|फेब्रुवारी|मार्च|एप्रिल|मे|जून|जुलै|ऑगस्ट|"
            r"सप्टेंबर|ऑक्टोबर|नोव्हेंबर|डिसेंबर)\b", text, re.UNICODE
        )
        # English date fallback
        or re.search(
            r"dated?\s*[:\s]*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}",
            text, re.IGNORECASE,
        )
    )
    if not has_date:
        return TemplateIssue(
            rule_id="MOP-MR-004",
            severity=Severity.ERROR,
            message="Issue date is missing from the resolution.",
            section="Header",
            suggestion="Add the date of issue (e.g., 'दिनांक: २८ जुलै, २०२६').",
        )
    return None


def _check_mr005_vacha_section(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-005 — 'वाचा:' reference section must be present."""
    has_vacha = bool(
        re.search(r"^\s*वाचा\s*:", text, re.UNICODE | re.MULTILINE)
        # English fallback
        or re.search(r"^\s*read\s*:", text, re.IGNORECASE | re.MULTILINE)
        # Old 'संदर्भ :' also accepted
        or re.search(r"संदर्भ\s*:", text, re.UNICODE)
    )
    if not has_vacha:
        return TemplateIssue(
            rule_id="MOP-MR-005",
            severity=Severity.WARNING,
            message="'वाचा:' reference section is missing.",
            section="वाचा Section",
            suggestion=(
                "Add a 'वाचा:' section with a numbered list of earlier GRs being cited. "
                "Example:\nवाचा:\n१. शासन निर्णय, महसूल विभाग, क्रमांक... दि. ..."
            ),
        )
    return None


def _check_mr006_preamble_section(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-006 — 'शासन परिपत्रक:' preamble heading must be present."""
    has_preamble = bool(
        # Primary official heading
        re.search(r"^\s*शासन\s*परिपत्रक\s*:", text, re.UNICODE | re.MULTILINE)
        # Also accept शासन निर्णय: for निर्णय-type GRs
        or re.search(r"^\s*शासन\s*निर्णय\s*:", text, re.UNICODE | re.MULTILINE)
        # Legacy terms
        or re.search(r"(प्रस्तावना|प्रस्तावित\s+बाब)", text, re.UNICODE)
        # English fallback
        or re.search(r"^\s*government\s+resolution\s*:", text, re.IGNORECASE | re.MULTILINE)
    )
    if not has_preamble:
        return TemplateIssue(
            rule_id="MOP-MR-006",
            severity=Severity.WARNING,
            message="Preamble section heading ('शासन परिपत्रक:') is missing.",
            section="Preamble",
            suggestion=(
                "Add 'शासन परिपत्रक:' as a section heading before the background "
                "paragraph explaining the context and authority for this resolution."
            ),
        )
    return None


def _check_mr007_numbered_clauses(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-007 — Operative clauses must be numbered using Marathi or Arabic numerals."""
    # Detect Devanagari zero-padded (०१., ०२.) or Arabic (01., 1., 1))
    has_numbered = bool(
        re.search(r"^\s*[०]?[१-९][.)]\s", text, re.MULTILINE | re.UNICODE)
        or re.search(r"^\s*0?[1-9][.)]\s", text, re.MULTILINE)
    )
    if not has_numbered:
        return TemplateIssue(
            rule_id="MOP-MR-007",
            severity=Severity.WARNING,
            message="Operative clauses do not appear to be numbered.",
            section="Operative Clauses",
            suggestion=(
                "Number each operative clause (e.g., '०१.', '०२.' or '1.', '2.') "
                "so they can be referenced precisely."
            ),
        )
    return None


def _check_mr008_closing_formula(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-008 — Closing formula must be present."""
    has_closing = bool(
        # Official Marathi closing (both word-order variants seen in real GRs)
        re.search(r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या\s+आदेशानुसार\s+व\s+नावाने", text, re.UNICODE)
        or re.search(r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या\s+नावाने\s+व\s+आदेशानुसार", text, re.UNICODE)
        # English fallback
        or re.search(r"by\s+order\s+and\s+in\s+the\s+name\s+of\s+the\s+governor", text, re.IGNORECASE)
    )
    if not has_closing:
        return TemplateIssue(
            rule_id="MOP-MR-008",
            severity=Severity.WARNING,
            message="Standard closing formula is missing.",
            section="Closing",
            suggestion=(
                "End the resolution with: "
                "'महाराष्ट्राचे राज्यपाल यांच्या आदेशानुसार व नावाने.'"
            ),
        )
    return None


def _check_mr009_signature_block(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-009 — Signature block must include an official designation."""
    designations = r"(सचिव|उप\s*सचिव|सह\s*सचिव|प्रधान\s*सचिव|अपर\s*मुख्य\s*सचिव|अवर\s*सचिव)"
    has_designation = bool(
        re.search(designations, text, re.UNICODE)
        or re.search(
            r"\b(under\s+secretary|deputy\s+secretary|joint\s+secretary|"
            r"principal\s+secretary|additional\s+chief\s+secretary|secretary)\b",
            text, re.IGNORECASE,
        )
    )
    if not has_designation:
        return TemplateIssue(
            rule_id="MOP-MR-009",
            severity=Severity.WARNING,
            message="Official signatory designation is missing from the closing block.",
            section="Signature",
            suggestion=(
                "Add the signatory's designation (e.g. 'शासनाचे अवर सचिव', "
                "'उप सचिव', 'प्रधान सचिव') at the end."
            ),
        )
    return None


def _check_mr010_mantralaya_address(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-010 — Full Mantralaya address or place of issue must be present."""
    has_place = bool(
        # Full official address
        re.search(r"हुतात्मा\s+राजगुरु\s+चौक", text, re.UNICODE)
        or re.search(r"मादाम\s+कामा\s+मार्ग", text, re.UNICODE)
        # Short form
        or re.search(r"मंत्रालय", text, re.UNICODE)
        # English fallback
        or re.search(r"mantralaya", text, re.IGNORECASE)
    )
    if not has_place:
        return TemplateIssue(
            rule_id="MOP-MR-010",
            severity=Severity.WARNING,
            message="Place of issue (मंत्रालय address) is not mentioned.",
            section="Header",
            suggestion=(
                "Add the official Mantralaya address in the header: "
                "'हुतात्मा राजगुरु चौक, मादाम कामा मार्ग, मंत्रालय मुंबई-३२'."
            ),
        )
    return None


def _check_mr011_prat_section(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-011 — Distribution list ('प्रत,') must be present."""
    has_prat = bool(
        re.search(r"^\s*प्रत\s*[,:]", text, re.UNICODE | re.MULTILINE)
        # English fallback
        or re.search(r"^\s*copy\s+to\s*[,:]", text, re.IGNORECASE | re.MULTILINE)
    )
    if not has_prat:
        return TemplateIssue(
            rule_id="MOP-MR-011",
            severity=Severity.WARNING,
            message="Distribution list ('प्रत,') is missing.",
            section="Distribution",
            suggestion=(
                "Add a 'प्रत,' section listing all offices that must receive this GR. "
                "Example:\nप्रत,\n१. मुख्य सचिव, महाराष्ट्र शासन\n२. संबंधित जिल्हाधिकारी"
            ),
        )
    return None


def _check_mr012_minimum_length(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-012 — GR must be at least 50 words long."""
    word_count = len(text.split())
    if word_count < 50:
        return TemplateIssue(
            rule_id="MOP-MR-012",
            severity=Severity.ERROR,
            message=f"Resolution body is very short ({word_count} words). A valid GR must have substantive content.",
            section="Content",
            suggestion="Expand the resolution to include all required sections with at least 50 words.",
        )
    return None


def _check_mr013_formal_language(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-013 — Detect conversational pronouns inside the operative section."""
    operative_match = re.search(
        r"(शासन\s+परिपत्रक|शासन\s+निर्णय)\s*:(.*)",
        text, re.UNICODE | re.DOTALL
    )
    scope = operative_match.group(2) if operative_match else ""
    if not scope:
        return None

    pronouns = re.findall(r"(?:\s|^)(मी|आम्ही|तू|तुम्ही|माझे|आमचे)(?=[\s,.\-?!]|$)", scope)
    if len(pronouns) >= 3:
        return TemplateIssue(
            rule_id="MOP-MR-013",
            severity=Severity.INFO,
            message=f"Found {len(pronouns)} conversational pronoun(s) in the operative section.",
            section="Language",
            suggestion="Rewrite using formal third-person government language rather than conversational pronouns (मी, आम्ही, तू, तुम्ही, माझे, आमचे).",
        )
    return None


def _check_mr014_excessive_english(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-014 — Detect excessive English words inside a Marathi GR."""
    english_words = re.findall(r"\b[a-zA-Z]{2,}\b", text)
    if len(english_words) > 20:
        return TemplateIssue(
            rule_id="MOP-MR-014",
            severity=Severity.INFO,
            message=f"Found {len(english_words)} English words. Standard Marathi GRs should limit excessive English vocabulary.",
            section="Language",
            suggestion="Use Marathi administrative terminology wherever possible to reduce excessive English words.",
        )
    return None


def _check_mr015_mandatory_terminology(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-015 — Headings must use Marathi terminology, not English equivalents."""
    replacements = []

    if re.search(r"\bSubject\b", text, re.IGNORECASE):
        replacements.append("'Subject' → 'विषय'")
    if re.search(r"\bReference\b", text, re.IGNORECASE):
        replacements.append("'Reference' → 'संदर्भ'")
    if re.search(r"^\s*Government\s+Resolution\s*:", text, re.IGNORECASE | re.MULTILINE):
        replacements.append("'Government Resolution:' → 'शासन परिपत्रक:' or 'शासन निर्णय:'")
    if re.search(r"\bPreamble\b", text, re.IGNORECASE):
        replacements.append("'Preamble' → 'प्रस्तावना'")
    if re.search(r"^\s*Read\s*:", text, re.IGNORECASE | re.MULTILINE):
        replacements.append("'Read:' → 'वाचा:'")
    if re.search(r"^\s*Copy\s+to\s*[,:]", text, re.IGNORECASE | re.MULTILINE):
        replacements.append("'Copy to:' → 'प्रत,'")

    if replacements:
        return TemplateIssue(
            rule_id="MOP-MR-015",
            severity=Severity.WARNING,
            message=f"English heading terms detected in a Marathi GR: {', '.join(replacements)}.",
            section="Terminology",
            suggestion="Replace English section headers with official Marathi terminology.",
        )
    return None


# =========================================================================
# Rule registry — add new check functions here to activate them.
# =========================================================================

RULES: List[Callable[[str], Optional[TemplateIssue]]] = [
    _check_mr001_header_govt,
    _check_mr002_department_line,
    _check_mr003_gr_number,
    _check_mr004_date,
    _check_mr005_vacha_section,
    _check_mr006_preamble_section,
    _check_mr007_numbered_clauses,
    _check_mr008_closing_formula,
    _check_mr009_signature_block,
    _check_mr010_mantralaya_address,
    _check_mr011_prat_section,
    _check_mr012_minimum_length,
    _check_mr013_formal_language,
    _check_mr014_excessive_english,
    _check_mr015_mandatory_terminology,
]


# =========================================================================
# Public API
# =========================================================================

def check_template_marathi(body_text: str) -> List[TemplateIssue]:
    """
    Run all MOP rules for Marathi against the supplied draft text and return every issue
    found. Returns an empty list for a perfectly compliant draft.

    Rules enforce the official Maharashtra Government परिपत्रक format:
    महाराष्ट्र शासन → विभाग → परिपत्रक क्रमांक → पत्ता → दिनांक →
    वाचा: → शासन परिपत्रक: → numbered clauses → closing → signatory → प्रत,
    """
    issues: List[TemplateIssue] = []
    for rule in RULES:
        result = rule(body_text)
        if result is not None:
            issues.append(result)
    return issues
