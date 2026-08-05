import json
import re
from typing import List, Optional
import llm
from .models import ConflictReportItem

VALID_CATEGORIES = [
    "Authority Conflict",
    "Department Ownership Conflict",
    "Funding Conflict",
    "Procedure Conflict",
    "Timeline Conflict",
    "Committee Conflict",
    "Legal Reference Conflict",
    "Policy Conflict",
    "Operational Conflict",
    "Terminology Conflict"
]

VALID_SEVERITIES = ["Low", "Medium", "High", "Critical"]

# One-step downgrade used when the deterministic post-processing rule fires.
_SEVERITY_DOWNGRADE = {"Critical": "Medium", "High": "Low", "Medium": "Low", "Low": "Low"}

def verify_conflict_with_llm(
    draft_clause: str,
    matched_gr_id: str,
    matched_gr_title: str,
    matched_clause: str,
    matched_gr_date: Optional[str] = None,
    cited_references: Optional[List[str]] = None,
    matched_department: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Optional[ConflictReportItem]:
    """
    Sends the draft and matched clause to the LLM verification layer
    to check for semantic or ambiguous conflicts.
    """
    system_prompt = (
        "You are an expert legal policy checker for the Government of Maharashtra.\n"
        "Your task is to analyze a DRAFT CLAUSE and a MATCHED CLAUSE from an existing GR and "
        "determine if there is a genuine, specific policy conflict between them.\n\n"

        "CRITICAL RULE: Similarity is NOT conflict. Two clauses mentioning the same department, "
        "the same general topic, or similar administrative language are NOT a conflict unless "
        "they make INCOMPATIBLE requirements about the SAME specific action or subject. Do not "
        "infer a conflict merely because a department name or a general theme (e.g. 'approval', "
        "'orders', 'procurement') appears in both.\n\n"

        "Before deciding, verify ALL of the following:\n"
        "1. Both clauses address the SAME specific action or subject matter -- not just the same "
        "department or a loosely related theme.\n"
        "2. You can quote the EXACT words in each clause that create the contradiction.\n"
        "3. The matched clause is not describing an EXCEPTION, a different scenario, or a "
        "narrower/unrelated case that happens to share vocabulary with the draft.\n"
        "4. If the matched text is a short snippet that appears to state a strict rule with no "
        "visible exceptions, treat that as UNCERTAIN, not confirmed -- snippets can be truncated "
        "mid-document and miss an exception stated elsewhere in the same GR. Lower confidence "
        "rather than asserting the rule is absolute.\n\n"

        "If ANY of the above cannot be satisfied, set \"conflict\": false. When genuinely unsure, "
        "prefer conflict: false over a speculative conflict: true.\n\n"

        "Categories of conflicts to detect:\n"
        "- Authority Conflict (different approval authorities mandated for the SAME decision)\n"
        "- Department Ownership Conflict (jurisdiction clashes over the SAME function)\n"
        "- Funding Conflict (funding rules or shares mismatch for the SAME expenditure)\n"
        "- Procedure Conflict (different procurement/tender/administrative procedures for the SAME process)\n"
        "- Timeline Conflict (incompatible deadlines/timelines for the SAME activity)\n"
        "- Committee Conflict (members size, chairpersons inconsistency for the SAME committee)\n"
        "- Legal Reference Conflict (different version/cites of the SAME act/rule)\n"
        "- Policy Conflict (strategic policy contradictions on the SAME question)\n"
        "- Operational Conflict (operational guideline mismatches for the SAME operation)\n"
        "- Terminology Conflict (inconsistent translation or term mapping for the SAME concept)\n\n"

        "BEFORE assigning an overall verdict, you MUST first decide two separate structured "
        "facts and report them explicitly:\n"
        "- \"beneficiary_match\": true only if both clauses govern the SAME beneficiary/entity type "
        "(e.g. both about Gram Panchayats, or both about Municipal Corporations) -- false if they "
        "target different beneficiary types even if the wording looks similar.\n"
        "- \"scope_match\": true only if both clauses cover the SAME jurisdiction/scope (e.g. both "
        "rural, or both urban/state-wide) -- false if one is narrower or targets a different scope "
        "than the other.\n"
        "Do not let lexical/wording similarity substitute for actually checking these two facts. "
        "If beneficiary_match is false AND scope_match is false, this is a lexical false positive, "
        "not a genuine conflict -- set \"conflict\": false in that case.\n\n"

        "If there is NO conflict, set \"conflict\": false.\n"
        "If there is a conflict, set \"conflict\": true, identify the category (must be one of the "
        "above 10), assign severity (Low, Medium, High, Critical), specify a confidence score "
        "(0.0 to 1.0), quote the exact contradicting text from both clauses in \"evidence\", and "
        "provide a concise reason and recommendation.\n\n"
        "Return ONLY a raw JSON object (no markdown, no backticks, no comments) matching this structure:\n"
        "{\n"
        "  \"beneficiary_match\": false,\n"
        "  \"scope_match\": false,\n"
        "  \"conflict\": true,\n"
        "  \"category\": \"Funding Conflict\",\n"
        "  \"severity\": \"Critical\",\n"
        "  \"confidence\": 0.95,\n"
        "  \"evidence\": \"Draft: '...exact quote...'. Matched: '...exact quote...'.\",\n"
        "  \"reason\": \"Detailed reason quoting both clauses.\",\n"
        "  \"recommendation\": \"Review funding provisions for consistency.\"\n"
        "}"
    )

    matched_gr_label = f"{matched_gr_id}: {matched_gr_title}"
    if matched_gr_date:
        matched_gr_label += f" (dated {matched_gr_date})"

    user_msg = (
        f"DRAFT CLAUSE:\n{draft_clause}\n\n"
        f"MATCHED CLAUSE (GR No: {matched_gr_id}, Title: {matched_gr_title}, "
        f"Date: {matched_gr_date or 'Unknown'}) -- this is a partial excerpt from a longer "
        f"document; it may not show exceptions or qualifications stated elsewhere in the same "
        f"GR:\n{matched_clause}"
    )
    if cited_references:
        refs = "; ".join(cited_references[:5])
        user_msg += f"\n\nThe matched GR itself cites/refers to: {refs}"
        user_msg += (
            "\nUse this only to judge whether the matched GR already supersedes or amends "
            "an earlier rule — do not treat it as a conflict on its own."
        )

    try:
        raw_reply = llm.call_model(system_prompt, user_msg)
        parsed = llm.parse_json_reply(raw_reply)
        if not parsed or not isinstance(parsed, dict):
            return None

        if not parsed.get("conflict", False):
            return None

        category = parsed.get("category", "Policy Conflict")
        if category not in VALID_CATEGORIES:
            category = "Policy Conflict"

        severity = parsed.get("severity", "High")
        if severity not in VALID_SEVERITIES:
            severity = "High"

        evidence = parsed.get("evidence", "").strip()
        reason = parsed.get("reason", "Semantic contradiction detected by AI.")
        if evidence:
            reason = f"{evidence} {reason}"

        beneficiary_match = parsed.get("beneficiary_match")
        scope_match = parsed.get("scope_match")
        if not isinstance(beneficiary_match, bool):
            beneficiary_match = None
        if not isinstance(scope_match, bool):
            scope_match = None

        relation = "conflict"
        # Deterministic post-processing: if the model's own structured facts show no
        # beneficiary overlap AND no scope overlap, the raw "conflict"/severity label it
        # picked is untrustworthy (a lexical false positive) — downgrade regardless of
        # what it said. This is plain logic, not another model call.
        if beneficiary_match is False and scope_match is False:
            relation = "overlap"
            severity = _SEVERITY_DOWNGRADE.get(severity, "Low")
            reason = f"[Auto-downgraded: no beneficiary or scope overlap per model's own analysis] {reason}"

        return ConflictReportItem(
            draft_clause=draft_clause,
            matched_gr=matched_gr_label,
            matched_clause=matched_clause,
            conflict=True,
            category=category,
            severity=severity,
            confidence=float(parsed.get("confidence", 0.70)),
            reason=reason,
            recommendation=parsed.get("recommendation", "Review clauses for consistency."),
            existing_gr_id=matched_gr_id,
            existing_gr_title=matched_gr_title,
            existing_department=matched_department or "",
            source_url=source_url,
            relation=relation,
            beneficiary_match=beneficiary_match,
            scope_match=scope_match,
        )
    except Exception as e:
        print(f"LLM Conflict Verifier error: {e}")
        return None
