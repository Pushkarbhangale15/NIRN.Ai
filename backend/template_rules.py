"""
template_rules.py — Objective 4: Manual of Office Procedure enforcement.

Checks a draft GR body against a set of structural and stylistic rules
derived from the Maharashtra Government's Manual of Office Procedure (MOP).

All checks here are purely rule-based (regex + heuristics).  No LLM is
involved — these are deterministic, fast, and free to call.

How to add a new rule
---------------------
1.  Write a function  _check_<rule_id>(text) -> Optional[TemplateIssue]
2.  Add it to the RULES list at the bottom of this file.
3.  Done.  The check is automatically included in run_template_check().

Rule IDs follow the scheme  MOP-NNN  so they can be traced to a specific
paragraph in the manual.
"""

import re
from typing import Callable, List, Optional

from schemas import Severity, TemplateIssue


# =========================================================================
# Individual rule functions
# =========================================================================
# Each returns a TemplateIssue if the rule is violated, or None if OK.

def _check_mop001_header_govt(text: str) -> Optional[TemplateIssue]:
    """MOP §2.1 — The GR must open with 'Government of Maharashtra' / 'महाराष्ट्र शासन'."""
    first_lines = text.strip()[:400]
    has_govt = bool(
        re.search(r"government\s+of\s+maharashtra", first_lines, re.IGNORECASE)
        or re.search(r"महाराष्ट्र\s+शासन", first_lines, re.UNICODE)
    )
    if not has_govt:
        return TemplateIssue(
            rule_id="MOP-001",
            severity=Severity.ERROR,
            message="Header must begin with 'Government of Maharashtra' or 'महाराष्ट्र शासन'.",
            section="Header",
            suggestion=(
                "Add 'GOVERNMENT OF MAHARASHTRA' or 'महाराष्ट्र शासन' as the very first line of the document."
            ),
        )
    return None


def _check_mop002_department_line(text: str) -> Optional[TemplateIssue]:
    """MOP §2.2 — Department name must appear in the header block."""
    first_lines = text.strip()[:500]
    has_dept = bool(
        re.search(r"department", first_lines, re.IGNORECASE)
        or re.search(r"विभाग", first_lines, re.UNICODE)      # Marathi: department
    )
    if not has_dept:
        return TemplateIssue(
            rule_id="MOP-002",
            severity=Severity.ERROR,
            message="Department name is missing from the header block.",
            section="Header",
            suggestion=(
                "Add the issuing department name on the second line, e.g. "
                "'Higher and Technical Education Department'."
            ),
        )
    return None


def _check_mop003_gr_number(text: str) -> Optional[TemplateIssue]:
    """MOP §2.3 — A GR reference number must be present."""
    has_grno = bool(
        re.search(
            r"(GR\s*No\.?|Government\s+Resolution\s+No\.?|शासन\s*निर्णय\s*क्रमांक)",
            text, re.IGNORECASE | re.UNICODE,
        )
    )
    if not has_grno:
        return TemplateIssue(
            rule_id="MOP-003",
            severity=Severity.ERROR,
            message="Government Resolution reference number is missing.",
            section="Header",
            suggestion=(
                "Include a GR number in the format: "
                "'Government Resolution No. ABC-2024/CR-001/XY-1'."
            ),
        )
    return None


def _check_mop004_date(text: str) -> Optional[TemplateIssue]:
    """MOP §2.4 — A date of issue must be present."""
    has_date = bool(
        re.search(
            r"dated?[:\s]*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}",
            text, re.IGNORECASE,
        )
        or re.search(r"\b(?:january|february|march|april|may|june|july|august|"
                     r"september|october|november|december)\b", text, re.IGNORECASE)
        # Numeric date anywhere in header (DD.MM.YYYY or DD/MM/YYYY)
        or re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\b", text)
    )
    if not has_date:
        return TemplateIssue(
            rule_id="MOP-004",
            severity=Severity.ERROR,
            message="Issue date is missing from the resolution.",
            section="Header",
            suggestion="Add 'Dated: DD.MM.YYYY' in the header block.",
        )
    return None


def _check_mop005_preamble(text: str) -> Optional[TemplateIssue]:
    """MOP §3.1 — A Preamble / प्रस्तावना section must be present."""
    has_preamble = bool(
        re.search(r"preamble", text, re.IGNORECASE)
        or re.search(r"प्रस्तावना", text, re.UNICODE)
    )
    if not has_preamble:
        return TemplateIssue(
            rule_id="MOP-005",
            severity=Severity.WARNING,
            message="Preamble section (Preamble / प्रस्तावना) is missing.",
            section="Preamble",
            suggestion=(
                "Add a 'Preamble:' section that explains the background, "
                "need, and authority for this resolution."
            ),
        )
    return None


def _check_mop006_operative_clauses(text: str) -> Optional[TemplateIssue]:
    """MOP §3.2 — Operative clauses must be present and numbered."""
    has_operative = bool(
        re.search(r"Government\s+Resolution[:\s]*\n", text, re.IGNORECASE)
        or re.search(r"शासन\s+निर्णय", text, re.UNICODE)
    )
    # Check for numbered clauses (1. / 1) / १.)
    has_numbered = bool(
        re.search(r"^\s*[1-9][.)]\s", text, re.MULTILINE)
        or re.search(r"^\s*[१-९][.)]\s", text, re.MULTILINE | re.UNICODE)
    )
    if not has_operative:
        return TemplateIssue(
            rule_id="MOP-006",
            severity=Severity.ERROR,
            message=(
                "'Government Resolution' / 'शासन निर्णय' operative section is missing."
            ),
            section="Operative Section",
            suggestion=(
                "Add a 'Government Resolution:' heading followed by numbered "
                "operative clauses."
            ),
        )
    if not has_numbered:
        return TemplateIssue(
            rule_id="MOP-006B",
            severity=Severity.WARNING,
            message="Operative clauses do not appear to be numbered.",
            section="Operative Section",
            suggestion=(
                "Number each operative clause (1., 2., 3. …) so they can be "
                "cited precisely."
            ),
        )
    return None


def _check_mop007_closing(text: str) -> Optional[TemplateIssue]:
    """MOP §4.1 — Closing formula 'By order and in the name of the Governor'."""
    has_closing = bool(
        re.search(
            r"by\s+order\s+and\s+in\s+the\s+name\s+of\s+the\s+governor",
            text, re.IGNORECASE,
        )
        or re.search(r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या", text, re.UNICODE)
    )
    if not has_closing:
        return TemplateIssue(
            rule_id="MOP-007",
            severity=Severity.WARNING,
            message="Standard closing formula is missing.",
            section="Closing",
            suggestion=(
                "End the resolution with: "
                "'By order and in the name of the Governor of Maharashtra, "
                "[Title] to Government'."
            ),
        )
    return None


def _check_mop008_mantralaya(text: str) -> Optional[TemplateIssue]:
    """MOP §2.2 — Place of issue (Mantralaya) should be present."""
    has_place = bool(
        re.search(r"mantralaya", text, re.IGNORECASE)
        or re.search(r"मंत्रालय", text, re.UNICODE)
    )
    if not has_place:
        return TemplateIssue(
            rule_id="MOP-008",
            severity=Severity.WARNING,
            message="Place of issue (Mantralaya) is not mentioned.",
            section="Header",
            suggestion=(
                "Add 'Mantralaya, Mumbai 400 032' after the department name."
            ),
        )
    return None


def _check_mop009_shall_language(text: str) -> Optional[TemplateIssue]:
    """MOP §3.3 — Operative clauses should use mandatory 'shall', not 'will' or 'must'."""
    # Only check inside the operative section if we can find it.
    operative_match = re.search(
        r"Government\s+Resolution[:\s]*(.*)", text,
        re.IGNORECASE | re.DOTALL,
    )
    scope = operative_match.group(1) if operative_match else text

    # Look for 'will' or 'must' used mandatorily (not in quotes or examples).
    bad_modal = re.findall(r"\b(will|must)\b", scope, re.IGNORECASE)
    if bad_modal:
        return TemplateIssue(
            rule_id="MOP-009",
            severity=Severity.INFO,
            message=(
                f"Found {len(bad_modal)} instance(s) of 'will'/'must' in operative "
                "clauses. The MOP standard register uses 'shall'."
            ),
            section="Language",
            suggestion=(
                "Replace mandatory 'will' and 'must' with 'shall' throughout "
                "the operative clauses."
            ),
        )
    return None


def _check_mop010_minimum_length(text: str) -> Optional[TemplateIssue]:
    """MOP §3.0 — A GR should have meaningful content (not a stub)."""
    word_count = len(text.split())
    if word_count < 50:
        return TemplateIssue(
            rule_id="MOP-010",
            severity=Severity.ERROR,
            message=(
                f"Resolution body is very short ({word_count} words). "
                "A valid GR must have substantive content."
            ),
            section="Content",
            suggestion="Expand the resolution to include all required sections.",
        )
    return None


def _check_mop011_no_personal_pronouns(text: str) -> Optional[TemplateIssue]:
    """MOP §3.3 — Avoid first/second person pronouns in formal GR text."""
    # Only flag if these appear in the operative section, not the preamble context.
    operative_match = re.search(
        r"Government\s+Resolution[:\s]*(.*)", text,
        re.IGNORECASE | re.DOTALL,
    )
    scope = operative_match.group(1) if operative_match else ""
    if not scope:
        return None

    pronouns = re.findall(r"\b(I|we|you|your|our|my)\b", scope, re.IGNORECASE)
    if len(pronouns) >= 3:
        return TemplateIssue(
            rule_id="MOP-011",
            severity=Severity.INFO,
            message=(
                f"Found {len(pronouns)} first/second-person pronoun(s) in the "
                "operative section. Formal GRs use the third person."
            ),
            section="Language",
            suggestion=(
                "Rewrite operative clauses in the third person "
                "(e.g. 'The institutions shall…' instead of 'You shall…')."
            ),
        )
    return None


# =========================================================================
# Rule registry — add new check functions here to activate them.
# =========================================================================

RULES: List[Callable[[str], Optional[TemplateIssue]]] = [
    _check_mop001_header_govt,
    _check_mop002_department_line,
    _check_mop003_gr_number,
    _check_mop004_date,
    _check_mop005_preamble,
    _check_mop006_operative_clauses,
    _check_mop007_closing,
    _check_mop008_mantralaya,
    _check_mop009_shall_language,
    _check_mop010_minimum_length,
    _check_mop011_no_personal_pronouns,
]


# =========================================================================
# Public API
# =========================================================================

def check_template(body_text: str) -> List[TemplateIssue]:
    """
    Run all MOP rules against the supplied draft text and return every issue
    found.  Returns an empty list for a perfectly compliant draft.

    Called by routes.run_template_check() and routes.run_full_analysis().
    """
    issues: List[TemplateIssue] = []
    for rule in RULES:
        result = rule(body_text)
        if result is not None:
            issues.append(result)
    return issues
