"""
template_rules.py — Objective 4: Manual of Office Procedure compliance.

NOT A STUB. This works today.

Template enforcement is a rules problem, not an AI problem. A rule
either fires or it doesn't — deterministic, instant, free, and
explainable to a judge. Using a language model here would be slower,
costlier and occasionally wrong for no benefit.

Every rule carries a stable ID (MOP-001 ...). Keep these IDs stable:
they let the frontend link to an explanation, and they let you report
per-rule accuracy in the final presentation. Almost no hackathon team
reports accuracy numbers, and it is exactly what separates a project
from a demo.

These nine rules are a first pass. On Day 2, open five real GRs from
data/, note what every one of them contains, and add rules for it.
"""

import re
from typing import Callable, List, Tuple

from schemas import Severity, TemplateIssue

# A rule is: (id, severity, message, suggestion, test function)
Rule = Tuple[str, Severity, str, str, Callable[[str], bool]]


def _has(pattern: str) -> Callable[[str], bool]:
    """Build a test function that returns True when the pattern is present."""
    compiled = re.compile(pattern, re.IGNORECASE | re.UNICODE | re.MULTILINE)
    return lambda text: bool(compiled.search(text))


RULES: List[Rule] = [
    (
        "MOP-001",
        Severity.ERROR,
        "Missing Government of Maharashtra header block.",
        "Begin the document with the Government of Maharashtra header naming the issuing department.",
        _has(r"Government of Maharashtra|महाराष्ट्र\s+शासन"),
    ),
    (
        "MOP-002",
        Severity.ERROR,
        "Missing GR reference number.",
        "Add the GR number in the form PREFIX-YYYY/Case No./Desk Code.",
        _has(r"(?:[A-Z]{2,8}|[\u0900-\u097F]{2,15})[-–](?:19|20)\d{2}/"),
    ),
    (
        "MOP-003",
        Severity.ERROR,
        "Missing the 'Government Resolution' section heading.",
        "Insert the heading 'Government Resolution' / 'शासन निर्णय' before the operative clauses.",
        _has(r"Government\s+Resolution|शासन\s+निर्णय"),
    ),
    (
        "MOP-004",
        Severity.WARNING,
        "No preamble or background section detected.",
        "Add a preamble ('Preamble' / 'प्रस्तावना') stating the background before the operative part.",
        _has(r"Preamble|Background|प्रस्तावना"),
    ),
    (
        "MOP-005",
        Severity.WARNING,
        "Operative clauses are not numbered.",
        "Number each operative clause (1., 2., 3.) so that it can be cited individually later.",
        _has(r"^\s*\d+[.)]\s+\S"),
    ),
    (
        "MOP-006",
        Severity.ERROR,
        "Missing issue date.",
        "State the date of issue in the standard format.",
        _has(r"\b\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2}\b|dated\s+\d{1,2}"),
    ),
    (
        "MOP-007",
        Severity.WARNING,
        "No signature or authority block found.",
        "Close with the signing authority's designation, e.g. 'By order and in the name of the Governor of Maharashtra'.",
        _has(r"By order and in the name|Secretary|Under\s+Secretary|सचिव|राज्यपाल"),
    ),
    (
        "MOP-008",
        Severity.INFO,
        "No distribution / copy-to list found.",
        "Add the 'Copy to' list naming the offices that receive this GR.",
        _has(r"Copy\s+to|प्रत\s+माहितीसाठी"),
    ),
]

MIN_BODY_CHARS = 200


def check_template(text: str) -> List[TemplateIssue]:
    """
    Run every rule against the draft.

    Returns only the rules that FAILED — a clean draft returns an empty
    list, which the frontend renders as a green tick.
    """
    issues: List[TemplateIssue] = []

    for rule_id, severity, message, suggestion, test in RULES:
        if not test(text):
            issues.append(
                TemplateIssue(
                    rule_id=rule_id,
                    severity=severity,
                    message=message,
                    suggestion=suggestion,
                )
            )

    if len(text.strip()) < MIN_BODY_CHARS:
        issues.append(
            TemplateIssue(
                rule_id="MOP-009",
                severity=Severity.WARNING,
                message=f"Draft is very short ({len(text.strip())} characters).",
                suggestion="A complete GR normally runs to at least a page.",
            )
        )

    return issues
