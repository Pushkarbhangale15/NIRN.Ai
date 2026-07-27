import json
import re
from typing import Optional
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

def verify_conflict_with_llm(
    draft_clause: str,
    matched_gr_id: str,
    matched_gr_title: str,
    matched_clause: str
) -> Optional[ConflictReportItem]:
    """
    Sends the draft and matched clause to the LLM verification layer
    to check for semantic or ambiguous conflicts.
    """
    system_prompt = (
        "You are an expert legal policy checker for the Government of Maharashtra.\n"
        "Your task is to analyze a DRAFT CLAUSE and a MATCHED CLAUSE from an existing GR "
        "and determine if there is a cross-departmental policy conflict, contradiction, or mismatch.\n\n"
        "Categories of conflicts to detect:\n"
        "- Authority Conflict (different approval authorities mandated)\n"
        "- Department Ownership Conflict (jurisdiction clashes)\n"
        "- Funding Conflict (funding rules or shares mismatch)\n"
        "- Procedure Conflict (different procurement/tender/administrative procedures)\n"
        "- Timeline Conflict (expiry, deadlines, or timeline clashes)\n"
        "- Committee Conflict (members size, chairpersons inconsistency)\n"
        "- Legal Reference Conflict (different version/cites of acts/rules)\n"
        "- Policy Conflict (strategic policy contradictions)\n"
        "- Operational Conflict (operational guideline mismatches)\n"
        "- Terminology Conflict (inconsistent translation or administrative term mapping)\n\n"
        "If there is NO conflict, set \"conflict\": false in your output.\n"
        "If there is a conflict, set \"conflict\": true, identify the category (must be one of the above 10 categories), "
        "assign severity (Low, Medium, High, Critical), specify a confidence score (0.0 to 1.0), and provide a concise reason and recommendation.\n\n"
        "Return ONLY a raw JSON object (no markdown, no backticks, no comments) matching this structure:\n"
        "{\n"
        "  \"conflict\": true,\n"
        "  \"category\": \"Funding Conflict\",\n"
        "  \"severity\": \"Critical\",\n"
        "  \"confidence\": 0.95,\n"
        "  \"reason\": \"Detailed reason quoting both clauses.\",\n"
        "  \"recommendation\": \"Review funding provisions for consistency.\"\n"
        "}"
    )

    user_msg = (
        f"DRAFT CLAUSE:\n{draft_clause}\n\n"
        f"MATCHED CLAUSE (GR No: {matched_gr_id}, Title: {matched_gr_title}):\n{matched_clause}"
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
            
        return ConflictReportItem(
            draft_clause=draft_clause,
            matched_gr=f"{matched_gr_id}: {matched_gr_title}",
            matched_clause=matched_clause,
            conflict=True,
            category=category,
            severity=severity,
            confidence=float(parsed.get("confidence", 0.70)),
            reason=parsed.get("reason", "Semantic contradiction detected by AI."),
            recommendation=parsed.get("recommendation", "Review clauses for consistency.")
        )
    except Exception as e:
        print(f"LLM Conflict Verifier error: {e}")
        return None
