import os
import json
import re
from typing import Optional, List, Dict, Any
from .models import ConflictReportItem

# Load rules from rules_config.json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "rules_config.json")

def load_rules_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading rules_config.json: {e}")
        return {"categories": {}}

_RULES_CONFIG = load_rules_config()

# Categories where the literal draft_contains/match_contains pairs above only cover two
# hardcoded examples (e.g. "30 days" vs "90 days"). These generalize that to ANY differing
# number within the same category, so long as the category's existing keyword gate already
# passed -- this does not add new keyword gating, only a numeric fallback checked after the
# literal rules for that category found no match.
_TIMELINE_NUMBER_PATTERNS = [r"(\d+)\s*days?", r"(\d+)\s*दिवस"]
_COMMITTEE_NUMBER_PATTERNS = [r"(\d+)\s*members?", r"(\d+)\s*सदस्य"]
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _extract_first_int(patterns: List[str], text: str) -> Optional[int]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def _extract_ratio(text: str) -> Optional[tuple]:
    """
    Extracts an N:N ratio, but ONLY from a sentence that also mentions "ratio" or "प्रमाण" --
    this prevents unrelated colon-formatted numbers (GR numbers like "45:2023", times like
    "10:30 AM") from ever being misread as a funding ratio.
    """
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if "ratio" in sentence.lower() or "प्रमाण" in sentence:
            m = re.search(r"(\d{1,3})\s*:\s*(\d{1,3})", sentence)
            if m:
                return (int(m.group(1)), int(m.group(2)))
    return None


def _numeric_generalized_conflict(
    category_name: str, draft_clause: str, matched_clause: str
) -> Optional[Dict[str, Any]]:
    """
    Fallback numeric comparison for Timeline/Committee/Funding, used only after the literal
    rules for `category_name` (and the category's keyword gate) found no match. Only compares
    numbers when both sides have an extractable value -- never guesses a missing side.

    Known limitation (accepted trade-off): the category keyword gate confirms both clauses
    discuss the same TOPIC (e.g. both mention "timeline"/"days"), not the same ACTIVITY, so a
    genuine edge case is two clauses about different processes that both happen to state a
    day-count (e.g. "grievance redressal within 30 days" vs "permit review within 90 days").
    Assigning a lower confidence than the literal rules (0.75 vs 0.85-0.95) reflects that this
    is a heuristic match, not a confirmed one.
    """
    if category_name == "Timeline Conflict":
        d = _extract_first_int(_TIMELINE_NUMBER_PATTERNS, draft_clause)
        m = _extract_first_int(_TIMELINE_NUMBER_PATTERNS, matched_clause)
        if d is not None and m is not None and d != m and abs(d - m) / max(d, m) >= 0.2:
            return {
                "severity": "Medium",
                "confidence": 0.75,
                "reason": (
                    f"Draft specifies a timeline of {d} days for this process, while the "
                    f"referenced GR specifies {m} days for a comparable process."
                ),
                "recommendation": "Confirm both clauses govern the same activity; align timelines if so.",
            }

    elif category_name == "Committee Conflict":
        d = _extract_first_int(_COMMITTEE_NUMBER_PATTERNS, draft_clause)
        m = _extract_first_int(_COMMITTEE_NUMBER_PATTERNS, matched_clause)
        if d is not None and m is not None and d != m:
            return {
                "severity": "Medium",
                "confidence": 0.75,
                "reason": (
                    f"Draft specifies a {d}-member committee, while the referenced GR "
                    f"mandates a {m}-member committee for a comparable body."
                ),
                "recommendation": "Confirm both clauses govern the same committee; align composition if so.",
            }

    elif category_name == "Funding Conflict":
        d = _extract_ratio(draft_clause)
        m = _extract_ratio(matched_clause)
        if d is not None and m is not None and d != m:
            return {
                "severity": "High",
                "confidence": 0.75,
                "reason": (
                    f"Draft specifies a funding ratio of {d[0]}:{d[1]}, while the referenced "
                    f"GR specifies a ratio of {m[0]}:{m[1]} for a comparable funding share."
                ),
                "recommendation": "Confirm both clauses govern the same funding share; align ratios if so.",
            }

    return None


def check_deterministic_conflicts(
    draft_clause: str,
    matched_gr_id: str,
    matched_gr_title: str,
    matched_clause: str,
    matched_gr_date: Optional[str] = None,
    matched_department: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Optional[ConflictReportItem]:
    """
    Checks the draft clause and the matched candidate clause against
    the deterministic rules defined in rules_config.json.
    Returns a ConflictReportItem if a deterministic rule matches, else None.
    """
    matched_gr_label = f"{matched_gr_id}: {matched_gr_title}"
    if matched_gr_date:
        matched_gr_label += f" (dated {matched_gr_date})"

    categories = _RULES_CONFIG.get("categories", {})
    
    for category_name, category_data in categories.items():
        keywords = category_data.get("keywords", [])
        
        # Check if the clause mentions any of the category keywords
        has_keywords_draft = any(k.lower() in draft_clause.lower() for k in keywords)
        has_keywords_match = any(k.lower() in matched_clause.lower() for k in keywords)
        
        if not (has_keywords_draft and has_keywords_match):
            continue
            
        rules = category_data.get("rules", [])
        for rule in rules:
            # Check draft contains patterns
            draft_match = False
            for p in rule.get("draft_contains", []):
                if re.search(r"\b" + re.escape(p.lower()) + r"\b", draft_clause.lower()) or p.lower() in draft_clause.lower():
                    draft_match = True
                    break
                    
            # Check match contains patterns
            match_match = False
            for p in rule.get("match_contains", []):
                if re.search(r"\b" + re.escape(p.lower()) + r"\b", matched_clause.lower()) or p.lower() in matched_clause.lower():
                    match_match = True
                    break
                    
            if draft_match and match_match:
                return ConflictReportItem(
                    draft_clause=draft_clause,
                    matched_gr=matched_gr_label,
                    matched_clause=matched_clause,
                    conflict=True,
                    category=category_name,
                    severity=rule.get("severity", "High"),
                    confidence=rule.get("confidence", 0.90),
                    reason=rule.get("reason", "Deterministic policy contradiction detected."),
                    recommendation=rule.get("recommendation", "Review clauses for alignment."),
                    existing_gr_id=matched_gr_id,
                    existing_gr_title=matched_gr_title,
                    existing_department=matched_department or "",
                    source_url=source_url,
                )

        # No literal rule matched for this category -- try the numeric fallback (Timeline/
        # Committee/Funding only). The keyword gate above already passed, so this is not a
        # new gating condition, only a broader comparison within the same gated category.
        numeric_match = _numeric_generalized_conflict(category_name, draft_clause, matched_clause)
        if numeric_match:
            return ConflictReportItem(
                draft_clause=draft_clause,
                matched_gr=matched_gr_label,
                matched_clause=matched_clause,
                conflict=True,
                category=category_name,
                severity=numeric_match["severity"],
                confidence=numeric_match["confidence"],
                reason=numeric_match["reason"],
                recommendation=numeric_match["recommendation"],
                existing_gr_id=matched_gr_id,
                existing_gr_title=matched_gr_title,
                existing_department=matched_department or "",
                source_url=source_url,
            )

    return None
