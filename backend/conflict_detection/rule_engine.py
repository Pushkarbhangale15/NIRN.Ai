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

def check_deterministic_conflicts(
    draft_clause: str,
    matched_gr_id: str,
    matched_gr_title: str,
    matched_clause: str
) -> Optional[ConflictReportItem]:
    """
    Checks the draft clause and the matched candidate clause against 
    the deterministic rules defined in rules_config.json.
    Returns a ConflictReportItem if a deterministic rule matches, else None.
    """
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
                    matched_gr=f"{matched_gr_id}: {matched_gr_title}",
                    matched_clause=matched_clause,
                    conflict=True,
                    category=category_name,
                    severity=rule.get("severity", "High"),
                    confidence=rule.get("confidence", 0.90),
                    reason=rule.get("reason", "Deterministic policy contradiction detected."),
                    recommendation=rule.get("recommendation", "Review clauses for alignment.")
                )
                
    return None
