"""
template_rules_marathi.py — Objective 4: Manual of Office Procedure enforcement for Marathi GRs.

Checks a draft GR body in Marathi against a set of structural and stylistic rules
derived from the Maharashtra Government's Manual of Office Procedure (MOP).

All checks here are purely rule-based (regex + heuristics). No LLM is
involved — these are deterministic, fast, and free to call.
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
    has_govt = bool(re.search(r"महाराष्ट्र\s+शासन", first_lines, re.UNICODE))
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
    first_lines = text.strip()[:500]
    has_dept = bool(re.search(r"विभाग", first_lines, re.UNICODE))
    if not has_dept:
        return TemplateIssue(
            rule_id="MOP-MR-002",
            severity=Severity.ERROR,
            message="Department name is missing from the header block.",
            section="Header",
            suggestion="Add the issuing department name containing 'विभाग' (e.g. 'महसूल विभाग' or 'उच्च व तंत्र शिक्षण विभाग').",
        )
    return None


def _check_mr003_gr_number(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-003 — Government Resolution Reference Number must be present."""
    has_grno = bool(
        re.search(
            r"(शासन\s*निर्णय\s*क्रमांक|क्रमांक|GR\s*No\.?)",
            text, re.IGNORECASE | re.UNICODE,
        )
    )
    if not has_grno:
        return TemplateIssue(
            rule_id="MOP-MR-003",
            severity=Severity.ERROR,
            message="Government Resolution reference number is missing.",
            section="Header",
            suggestion="Include a GR reference number in the format: 'शासन निर्णय क्रमांक: XYZ-2026/...' or 'क्रमांक: ...'.",
        )
    return None


def _check_mr004_date(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-004 — Date must be present."""
    has_date = bool(
        re.search(
            r"(दिनांक\s*[:\.]?|दि\s*\.?[:\.]?)\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}",
            text, re.IGNORECASE | re.UNICODE,
        )
        or re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\b", text)
    )
    if not has_date:
        return TemplateIssue(
            rule_id="MOP-MR-004",
            severity=Severity.ERROR,
            message="Issue date is missing from the resolution.",
            section="Header",
            suggestion="Add the date of issue (e.g., 'दिनांक : DD/MM/YYYY' or 'दि. DD.MM.YYYY').",
        )
    return None


def _check_mr005_subject_line(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-005 — Subject Line must exist (starting with 'विषय :')."""
    has_subject = bool(re.search(r"विषय\s*:", text, re.UNICODE))
    if not has_subject:
        return TemplateIssue(
            rule_id="MOP-MR-005",
            severity=Severity.ERROR,
            message="Subject line ('विषय :') is missing.",
            section="Subject",
            suggestion="Include a subject line starting with 'विषय :'.",
        )
    return None


def _check_mr006_reference_section(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-006 — Reference Section must exist (containing 'संदर्भ :')."""
    has_ref = bool(re.search(r"संदर्भ\s*:", text, re.UNICODE))
    if not has_ref:
        return TemplateIssue(
            rule_id="MOP-MR-006",
            severity=Severity.WARNING,
            message="Reference section ('संदर्भ :') is missing.",
            section="References",
            suggestion="Add a references section starting with 'संदर्भ :' to cite relevant base guidelines or preceding GRs.",
        )
    return None


def _check_mr007_preamble(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-007 — Preamble section must exist (containing 'प्रस्तावना' or 'प्रस्तावित बाब')."""
    has_preamble = bool(
        re.search(r"(प्रस्तावना|प्रस्तावित\s+बाब)", text, re.UNICODE)
    )
    if not has_preamble:
        return TemplateIssue(
            rule_id="MOP-MR-007",
            severity=Severity.WARNING,
            message="Preamble section ('प्रस्तावना' or 'प्रस्तावित बाब') is missing.",
            section="Preamble",
            suggestion="Include a preamble section ('प्रस्तावना' or 'प्रस्तावित बाब') explaining the background, need, and authority for this resolution.",
        )
    return None


def _check_mr008_operative_section(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-008 — Operative section must exist (containing 'शासन निर्णय')."""
    has_operative = bool(re.search(r"शासन\s+निर्णय", text, re.UNICODE))
    if not has_operative:
        return TemplateIssue(
            rule_id="MOP-MR-008",
            severity=Severity.ERROR,
            message="Operative section header ('शासन निर्णय') is missing.",
            section="Operative Section",
            suggestion="Include the main operative section header 'शासन निर्णय:'.",
        )
    return None


def _check_mr009_numbered_clauses(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-009 — Operative clauses must be numbered using Marathi or Arabic numerals."""
    # Look at text after 'शासन निर्णय' to find clauses
    operative_match = re.search(r"शासन\s+निर्णय\s*(.*)", text, re.UNICODE | re.DOTALL)
    scope = operative_match.group(1) if operative_match else text

    # Detect either Arabic (1., 2., 3.) or Marathi (१., २., ३., 1), २)) numbering at the start of a line
    has_numbered = bool(
        re.search(r"^\s*[1-9][.)]\s", scope, re.MULTILINE)
        or re.search(r"^\s*[१-९][.)]\s", scope, re.MULTILINE | re.UNICODE)
    )
    if not has_numbered:
        return TemplateIssue(
            rule_id="MOP-MR-009",
            severity=Severity.WARNING,
            message="Operative clauses do not appear to be numbered.",
            section="Operative Section",
            suggestion="Number each operative clause (e.g., '१.', '२.' or '1.', '2.') so they can be referenced precisely.",
        )
    return None


def _check_mr010_closing_formula(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-010 — Closing formula 'महाराष्ट्राचे राज्यपाल यांच्या नावाने व आदेशानुसार' must be present."""
    has_closing = bool(
        re.search(
            r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या\s+नावाने\s+व\s+आदेशानुसार",
            text, re.UNICODE,
        )
    )
    if not has_closing:
        return TemplateIssue(
            rule_id="MOP-MR-010",
            severity=Severity.WARNING,
            message="Standard closing formula is missing.",
            section="Closing",
            suggestion="End the resolution with: 'महाराष्ट्राचे राज्यपाल यांच्या नावाने व आदेशानुसार'.",
        )
    return None


def _check_mr011_signature_block(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-011 — Signature block must require an official designation."""
    # Accept common official ranks
    designations = r"(सचिव|उप\s+सचिव|सह\s+सचिव|प्रधान\s+सचिव|अपर\s+मुख्य\s+सचिव|अवर\s+सचिव)"
    has_designation = bool(re.search(designations, text, re.UNICODE))
    if not has_designation:
        return TemplateIssue(
            rule_id="MOP-MR-011",
            severity=Severity.WARNING,
            message="Official signatory designation is missing from the closing block.",
            section="Signature",
            suggestion="Add the signatory's designation (e.g. 'सचिव', 'उप सचिव', 'प्रधान सचिव', or 'सह सचिव') at the end.",
        )
    return None


def _check_mr012_place_of_issue(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-012 — Place of issue must contain 'मंत्रालय' or 'मुंबई'."""
    has_place = bool(
        re.search(r"(मंत्रालय|मुंबई)", text, re.UNICODE)
    )
    if not has_place:
        return TemplateIssue(
            rule_id="MOP-MR-012",
            severity=Severity.WARNING,
            message="Place of issue (मंत्रालय or मुंबई) is not mentioned.",
            section="Header",
            suggestion="Mention the place of issue in the header, e.g. 'मंत्रालय, मुंबई'.",
        )
    return None


def _check_mr013_formal_language(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-013 — Detect conversational pronouns inside the operative section."""
    operative_match = re.search(r"शासन\s+निर्णय\s*(.*)", text, re.UNICODE | re.DOTALL)
    scope = operative_match.group(1) if operative_match else ""
    if not scope:
        return None

    # Match common conversational Marathi pronouns
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


def _check_mr014_minimum_length(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-014 — GR must be at least 50 words long."""
    word_count = len(text.split())
    if word_count < 50:
        return TemplateIssue(
            rule_id="MOP-MR-014",
            severity=Severity.ERROR,
            message=f"Resolution body is very short ({word_count} words). A valid GR must have substantive content.",
            section="Content",
            suggestion="Expand the resolution to include all required sections with at least 50 words.",
        )
    return None


def _check_mr015_excessive_english(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-015 — Detect excessive English words inside a Marathi GR."""
    # Find words with English letters of length >= 2
    english_words = re.findall(r"\b[a-zA-Z]{2,}\b", text)
    if len(english_words) > 20:
        return TemplateIssue(
            rule_id="MOP-MR-015",
            severity=Severity.INFO,
            message=f"Found {len(english_words)} English words. Standard Marathi GRs should limit excessive English vocabulary.",
            section="Language",
            suggestion="Use Marathi administrative terminology wherever possible to reduce excessive English words.",
        )
    return None


def _check_mr016_mandatory_terminology(text: str) -> Optional[TemplateIssue]:
    """MOP-MR-016 — Headings should use Marathi terminology over English equivalents."""
    replacements = []
    
    # Check for obvious English headers in a Marathi document
    if re.search(r"\bSubject\b", text, re.IGNORECASE):
        replacements.append("'Subject' -> 'विषय'")
    if re.search(r"\bReference\b", text, re.IGNORECASE):
        replacements.append("'Reference' -> 'संदर्भ'")
    if re.search(r"\bGovernment\s+Resolution\b", text, re.IGNORECASE):
        replacements.append("'Government Resolution' -> 'शासन निर्णय'")
    if re.search(r"\bPreamble\b", text, re.IGNORECASE):
        replacements.append("'Preamble' -> 'प्रस्तावना'")

    if replacements:
        return TemplateIssue(
            rule_id="MOP-MR-016",
            severity=Severity.WARNING,
            message=f"Obvious English heading terms ({', '.join(replacements)}) were detected in a Marathi GR.",
            section="Terminology",
            suggestion="Replace English section headers with official Marathi terminology ('विषय', 'संदर्भ', 'शासन निर्णय', 'प्रस्तावना').",
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
    _check_mr005_subject_line,
    _check_mr006_reference_section,
    _check_mr007_preamble,
    _check_mr008_operative_section,
    _check_mr009_numbered_clauses,
    _check_mr010_closing_formula,
    _check_mr011_signature_block,
    _check_mr012_place_of_issue,
    _check_mr013_formal_language,
    _check_mr014_minimum_length,
    _check_mr015_excessive_english,
    _check_mr016_mandatory_terminology,
]


# =========================================================================
# Public API
# =========================================================================

def check_template_marathi(body_text: str) -> List[TemplateIssue]:
    """
    Run all MOP rules for Marathi against the supplied draft text and return every issue
    found. Returns an empty list for a perfectly compliant draft.
    """
    issues: List[TemplateIssue] = []
    for rule in RULES:
        result = rule(body_text)
        if result is not None:
            issues.append(result)
    return issues
