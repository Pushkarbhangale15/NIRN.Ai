"""
template_rules.py — Objective 4: Manual of Office Procedure enforcement.

Checks a draft GR body against a set of structural and stylistic rules
derived from the Maharashtra Government's Manual of Office Procedure (MOP).

All checks here are purely rule-based (regex + heuristics).  No LLM is
involved — these are deterministic, fast, and free to call.

Every rule pattern accepts BOTH the English AND Marathi equivalent so that
a GR passes validation regardless of which language it is written in.

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
    first_lines = text.strip()[:600]
    
    # 1. Broad structural check
    has_dept = bool(
        re.search(r"department", first_lines, re.IGNORECASE)
        or re.search(r"विभाग", first_lines, re.UNICODE)
    )

    # 2. Refined Knowledge Base verification
    if has_dept:
        from knowledge import get_knowledge_service
        ks = get_knowledge_service()
        # Verify if any official department from knowledge base matches
        for dept in ks.get_all_departments():
            en_name = dept.get("english", "").lower()
            mr_name = dept.get("marathi", "")
            if (en_name and en_name in first_lines.lower()) or (mr_name and mr_name in first_lines):
                return None

    if not has_dept:
        return TemplateIssue(
            rule_id="MOP-002",
            severity=Severity.ERROR,
            message="Department name is missing from the header block.",
            section="Header",
            suggestion=(
                "Add the issuing department name on the second line, e.g. "
                "'Higher and Technical Education Department' or 'महसूल व वन विभाग'."
            ),
        )
    return None



def _check_mop003_gr_number(text: str) -> Optional[TemplateIssue]:
    """MOP §2.3 — A GR reference/circular number must be present in the standard format."""
    has_grno = bool(
        # English variants
        re.search(
            r"(GR\s*No\.?|Government\s+Resolution\s+No\.?|Government\s+Circular\s+No\.?)",
            text, re.IGNORECASE,
        )
        # Marathi परिपत्रक क्रमांक (circular number — primary official form)
        or re.search(r"शासन\s*परिपत्रक\s*क्रमांक\s*:", text, re.UNICODE)
        # Marathi निर्णय क्रमांक (resolution number — also accepted)
        or re.search(r"शासन\s*निर्णय\s*क्रमांक", text, re.UNICODE)
        # Bare क्रमांक in header context
        or re.search(r"क्रमांक\s*:", text, re.UNICODE)
    )
    if not has_grno:
        return TemplateIssue(
            rule_id="MOP-003",
            severity=Severity.ERROR,
            message="Government Resolution/Circular reference number is missing.",
            section="Header",
            suggestion=(
                "Include a GR number, e.g. "
                "'Government Resolution No. ABC-2024/CR-001/XY-1' (English) or "
                "'शासन परिपत्रक क्रमांक: ABC-२०२४/प्र.क्र.001/XY-1' (Marathi)."
            ),
        )
    return None


def _check_mop004_date(text: str) -> Optional[TemplateIssue]:
    """MOP §2.4 — A date of issue must be present."""
    has_date = bool(
        # English: 'Dated: DD.MM.YYYY' or 'Dated: 28 July, 2026'
        re.search(
            r"dated?\s*[:\s]*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}",
            text, re.IGNORECASE,
        )
        # Marathi: 'दिनांक: DD Month, YYYY'
        or re.search(r"दिनांक\s*[:\s]", text, re.UNICODE)
        # English month names
        or re.search(r"\b(?:january|february|march|april|may|june|july|august|"
                     r"september|october|november|december)\b", text, re.IGNORECASE)
        # Marathi month names
        or re.search(r"\b(?:जानेवारी|फेब्रुवारी|मार्च|एप्रिल|मे|जून|जुलै|ऑगस्ट|"
                     r"सप्टेंबर|ऑक्टोबर|नोव्हेंबर|डिसेंबर)\b", text, re.UNICODE)
        # Numeric date (DD.MM.YYYY or DD/MM/YYYY)
        or re.search(r"\b\d{2}[./]\d{2}[./]\d{4}\b", text)
    )
    if not has_date:
        return TemplateIssue(
            rule_id="MOP-004",
            severity=Severity.ERROR,
            message="Issue date is missing from the resolution.",
            section="Header",
            suggestion=(
                "Add 'Dated: DD Month YYYY' (English) or "
                "'दिनांक: DD Month, YYYY' (Marathi) in the header block."
            ),
        )
    return None


def _check_mop005_read_section(text: str) -> Optional[TemplateIssue]:
    """MOP §2.5 — A 'Read:' / 'वाचा:' reference list must be present."""
    has_read = bool(
        re.search(r"^\s*read\s*:", text, re.IGNORECASE | re.MULTILINE)
        or re.search(r"^\s*वाचा\s*:", text, re.UNICODE | re.MULTILINE)
    )
    if not has_read:
        return TemplateIssue(
            rule_id="MOP-005",
            severity=Severity.WARNING,
            message="'Read:' / 'वाचा:' reference section is missing.",
            section="Read Section",
            suggestion=(
                "Add a 'Read:' section (English) or 'वाचा:' section (Marathi) with a "
                "numbered list of earlier GRs being cited or superseded."
            ),
        )
    return None


def _check_mop006_preamble_section(text: str) -> Optional[TemplateIssue]:
    """MOP §3.1 — A preamble / background section must be present."""
    has_preamble = bool(
        # English preamble heading or the operative heading which serves as preamble intro
        re.search(r"^\s*government\s+resolution\s*:", text, re.IGNORECASE | re.MULTILINE)
        or re.search(r"\bpreamble\b", text, re.IGNORECASE)
        # Marathi: 'शासन परिपत्रक:' is the standard heading for the background section
        or re.search(r"^\s*शासन\s*परिपत्रक\s*:", text, re.UNICODE | re.MULTILINE)
        or re.search(r"प्रस्तावना", text, re.UNICODE)
    )
    if not has_preamble:
        return TemplateIssue(
            rule_id="MOP-006",
            severity=Severity.WARNING,
            message="Preamble / background section is missing.",
            section="Preamble",
            suggestion=(
                "Add 'Government Resolution:' (English) or 'शासन परिपत्रक:' (Marathi) "
                "followed by a paragraph explaining the background and authority for this resolution."
            ),
        )
    return None


def _check_mop007_operative_clauses(text: str) -> Optional[TemplateIssue]:
    """MOP §3.2 — Numbered operative clauses must be present."""
    # Check for numbered clauses — Arabic (1., 01.), Devanagari (१., ०१.)
    has_numbered = bool(
        re.search(r"^\s*0?[1-9][.)]\s", text, re.MULTILINE)
        or re.search(r"^\s*[०]?[१-९][.)]\s", text, re.MULTILINE | re.UNICODE)
    )
    if not has_numbered:
        return TemplateIssue(
            rule_id="MOP-007",
            severity=Severity.WARNING,
            message="Numbered operative clauses are missing.",
            section="Operative Clauses",
            suggestion=(
                "Number each operative clause (01., 02. … or ०१., ०२. …) "
                "so they can be cited precisely."
            ),
        )
    return None


def _check_mop008_closing(text: str) -> Optional[TemplateIssue]:
    """MOP §4.1 — Closing formula 'By order and in the name of the Governor'."""
    has_closing = bool(
        re.search(
            r"by\s+order\s+and\s+in\s+the\s+name\s+of\s+the\s+governor",
            text, re.IGNORECASE,
        )
        # Accept either word order variant seen in official GRs
        or re.search(r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या\s+आदेशानुसार\s+व\s+नावाने", text, re.UNICODE)
        or re.search(r"महाराष्ट्राचे\s+राज्यपाल\s+यांच्या\s+नावाने\s+व\s+आदेशानुसार", text, re.UNICODE)
    )
    if not has_closing:
        return TemplateIssue(
            rule_id="MOP-008",
            severity=Severity.WARNING,
            message="Standard closing formula is missing.",
            section="Closing",
            suggestion=(
                "End the resolution with: "
                "'By order and in the name of the Governor of Maharashtra.' (English) or "
                "'महाराष्ट्राचे राज्यपाल यांच्या आदेशानुसार व नावाने.' (Marathi)."
            ),
        )
    return None


def _check_mop009_mantralaya_address(text: str) -> Optional[TemplateIssue]:
    """MOP §2.2 — Official Mantralaya address or place of issue must be present."""
    has_place = bool(
        # Full official Marathi address
        re.search(r"हुतात्मा\s+राजगुरु\s+चौक", text, re.UNICODE)
        or re.search(r"मादाम\s+कामा\s+मार्ग", text, re.UNICODE)
        # Short Marathi forms
        or re.search(r"मंत्रालय", text, re.UNICODE)
        # English forms
        or re.search(r"mantralaya", text, re.IGNORECASE)
        or re.search(r"hutatma\s+rajguru\s+chowk", text, re.IGNORECASE)
    )
    if not has_place:
        return TemplateIssue(
            rule_id="MOP-009",
            severity=Severity.WARNING,
            message="Place of issue (Mantralaya address) is not mentioned.",
            section="Header",
            suggestion=(
                "Add the official address in the header: "
                "'Hutatma Rajguru Chowk, Madam Cama Road, Mantralaya Mumbai-32' (English) or "
                "'हुतात्मा राजगुरु चौक, मादाम कामा मार्ग, मंत्रालय मुंबई-३२' (Marathi)."
            ),
        )
    return None


def _check_mop010_signatory_block(text: str) -> Optional[TemplateIssue]:
    """MOP §4.2 — Signatory designation (Under Secretary / अवर सचिव etc.) must be present."""
    has_sig = bool(
        # English designations
        re.search(
            r"\b(under\s+secretary|deputy\s+secretary|joint\s+secretary|"
            r"principal\s+secretary|additional\s+chief\s+secretary|secretary)\b",
            text, re.IGNORECASE,
        )
        # Marathi designations
        or re.search(
            r"(अवर\s*सचिव|उप\s*सचिव|सह\s*सचिव|प्रधान\s*सचिव|"
            r"अपर\s*मुख्य\s*सचिव|सचिव)",
            text, re.UNICODE,
        )
    )
    if not has_sig:
        return TemplateIssue(
            rule_id="MOP-010",
            severity=Severity.WARNING,
            message="Signatory designation is missing from the closing block.",
            section="Signature",
            suggestion=(
                "Add the signatory's designation, e.g. 'Under Secretary to Government' (English) or "
                "'शासनाचे अवर सचिव' (Marathi)."
            ),
        )
    return None


def _check_mop011_distribution_list(text: str) -> Optional[TemplateIssue]:
    """MOP §5.1 — Distribution list ('Copy to:' / 'प्रत,') must be present."""
    has_dist = bool(
        re.search(r"^\s*copy\s+to\s*[,:]", text, re.IGNORECASE | re.MULTILINE)
        or re.search(r"^\s*प्रत\s*[,:]", text, re.UNICODE | re.MULTILINE)
    )
    if not has_dist:
        return TemplateIssue(
            rule_id="MOP-011",
            severity=Severity.WARNING,
            message="Distribution list ('Copy to:' / 'प्रत,') is missing.",
            section="Distribution",
            suggestion=(
                "Add a 'Copy to:' section (English) or 'प्रत,' section (Marathi) "
                "listing all offices that must receive this GR."
            ),
        )
    return None


def _check_mop012_shall_language(text: str) -> Optional[TemplateIssue]:
    """MOP §3.3 — Operative clauses should use mandatory 'shall', not 'will' or 'must'."""
    # Only check inside the operative section if we can find it.
    operative_match = re.search(
        r"Government\s+Resolution[:\s]*(.*)", text,
        re.IGNORECASE | re.DOTALL,
    )
    scope = operative_match.group(1) if operative_match else text

    bad_modal = re.findall(r"\b(will|must)\b", scope, re.IGNORECASE)
    if bad_modal:
        return TemplateIssue(
            rule_id="MOP-012",
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


def _check_mop013_minimum_length(text: str) -> Optional[TemplateIssue]:
    """MOP §3.0 — A GR should have meaningful content (not a stub)."""
    word_count = len(text.split())
    if word_count < 50:
        return TemplateIssue(
            rule_id="MOP-013",
            severity=Severity.ERROR,
            message=(
                f"Resolution body is very short ({word_count} words). "
                "A valid GR must have substantive content."
            ),
            section="Content",
            suggestion="Expand the resolution to include all required sections.",
        )
    return None


def _check_mop014_no_personal_pronouns(text: str) -> Optional[TemplateIssue]:
    """MOP §3.3 — Avoid first/second person pronouns in formal GR text."""
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
            rule_id="MOP-014",
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
# LLM formatting-artifact cleanup — strips markdown code fences the model
# sometimes wraps its output in (common when asked for structured text,
# e.g. it emits "```marathi\n...\n```" around the whole GR). Must run
# before the draft is treated as final, ahead of placeholder-leak
# detection below so a stray fence doesn't get flagged twice.
# =========================================================================

_LEADING_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?")
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$")


def strip_llm_formatting_artifacts(text: str) -> str:
    """Strip a leading/trailing triple-backtick code fence (with or
    without a language tag) from LLM output. Confirmed cause: drafts
    generated wrapped in ```marathi ... ``` with the fences saved
    verbatim as part of the "final" document text.
    """
    stripped = text.strip()
    stripped = _LEADING_FENCE_RE.sub("", stripped, count=1)
    stripped = _TRAILING_FENCE_RE.sub("", stripped, count=1)
    return stripped.strip()


# =========================================================================
# Placeholder-leak detection — runs on every generated draft before it's
# returned, independent of the MOP rule registry below (this is a
# correctness gate, not a style/structure check).
# =========================================================================

_PLACEHOLDER_PATTERNS = [
    r"\[DD Month,?\s*YYYY\]",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"```",  # any surviving code fence — same class of "strip before final" artifact
    # Only flag bracketed text that looks like an actual unfilled placeholder,
    # i.e. contains words like "name", "required", "insert", "specify", etc.
    # This avoids false-positives on legitimate GR text like
    # "[Under Secretary to Government]" or "[Office/Officer 1]".
    r"\[[^\]\n]{0,80}(?:required|insert|specify|enter|fill in|placeholder|TBD|your |here\b)[^\]\n]{0,40}\]",
]

# Bare "Month"/"Year" only count as leaks when they appear where a real date
# should be (immediately after the दिनांक:/Dated: label) — matching them
# anywhere in the body would false-positive on ordinary prose.
_DATE_LABEL_LEAK_PATTERN = (
    r"(?:दिनांक|dated?)\s*[:\s]+[^\n]*\b(?:month|year)\b"
)


def find_placeholder_leaks(text: str) -> List[str]:
    """Return the list of unrendered placeholder tokens found in `text`.

    Empty list means the draft is clean. Callers should treat any hit as a
    generation failure — the placeholder must be substituted with a real
    value, never shipped to the user.
    """
    leaks: List[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        leaks.extend(re.findall(pattern, text, re.IGNORECASE))
    date_leak = re.search(_DATE_LABEL_LEAK_PATTERN, text, re.IGNORECASE)
    if date_leak:
        leaks.append(date_leak.group(0).strip())
    return leaks


# =========================================================================
# Rule registry — add new check functions here to activate them.
# =========================================================================

RULES: List[Callable[[str], Optional[TemplateIssue]]] = [
    _check_mop001_header_govt,
    _check_mop002_department_line,
    _check_mop003_gr_number,
    _check_mop004_date,
    _check_mop005_read_section,
    _check_mop006_preamble_section,
    _check_mop007_operative_clauses,
    _check_mop008_closing,
    _check_mop009_mantralaya_address,
    _check_mop010_signatory_block,
    _check_mop011_distribution_list,
    _check_mop012_shall_language,
    _check_mop013_minimum_length,
    _check_mop014_no_personal_pronouns,
]


# =========================================================================
# Public API
# =========================================================================

def check_template(body_text: str) -> List[TemplateIssue]:
    """
    Run all MOP rules against the supplied draft text and return every issue
    found.  Returns an empty list for a perfectly compliant draft.

    Called by routes.run_template_check() and routes.run_full_analysis().
    Both English and Marathi patterns are checked in every rule so this
    function is language-agnostic — it will correctly validate GRs in
    either language.
    """
    issues: List[TemplateIssue] = []
    for rule in RULES:
        result = rule(body_text)
        if result is not None:
            issues.append(result)
    return issues
