"""
search.py — Partial, prefix, contains, and fuzzy search over Knowledge Base.

Allows searching terms, departments, designations, and phrases without
manual iteration in backend callers.
"""

import difflib
from typing import Dict, List, Optional
from .cache import KnowledgeCache


class KnowledgeSearcher:
    """
    Search engine over KnowledgeCache entries.
    Supports partial/substring matching, prefix matching, and fuzzy matching.
    """

    def __init__(self, cache: KnowledgeCache):
        self._cache = cache

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> List[dict]:
        """
        Multi-strategy search over all terms:
          1. Exact / Prefix matches first
          2. Substring (contains) matches second
          3. Fuzzy similarity matches third

        Args:
            query: Natural language or term search query.
            category: Optional category filter.
            limit: Max results to return.
            min_confidence: Floor for term confidence score.

        Returns:
            List of matching term entries sorted by relevance.
        """
        if not query or not isinstance(query, str):
            return []

        q_clean = query.strip()
        q_lower = q_clean.lower()
        if not q_lower:
            return []

        all_terms = self._cache.get_all_terms()
        if category:
            all_terms = [t for t in all_terms if t.get("category", "").lower() == category.lower()]
        if min_confidence > 0:
            all_terms = [t for t in all_terms if t.get("confidence", 0.0) >= min_confidence]

        exact_prefix_hits = []
        substring_hits = []
        fuzzy_candidates = []

        for term in all_terms:
            en = term.get("english", "").lower()
            mr = term.get("marathi", "")
            aliases = [a.lower() for a in term.get("aliases", []) if isinstance(a, str)]

            # 1. Exact or Prefix match
            if en.startswith(q_lower) or mr.startswith(q_clean) or any(a.startswith(q_lower) for a in aliases):
                exact_prefix_hits.append((1.0, term))
                continue

            # 2. Substring match
            if q_lower in en or q_clean in mr or any(q_lower in a for a in aliases):
                substring_hits.append((0.75, term))
                continue

            # 3. Fuzzy match fallback
            ratio_en = difflib.SequenceMatcher(None, q_lower, en).ratio()
            ratio_mr = difflib.SequenceMatcher(None, q_clean, mr).ratio()
            best_ratio = max(ratio_en, ratio_mr)
            if best_ratio >= 0.55:
                fuzzy_candidates.append((best_ratio, term))

        # Sort and merge
        exact_prefix_hits.sort(key=lambda x: -x[0])
        substring_hits.sort(key=lambda x: -x[1].get("frequency", 0))
        fuzzy_candidates.sort(key=lambda x: -x[0])

        merged = []
        seen_ids = set()

        for _, item in exact_prefix_hits + substring_hits + fuzzy_candidates:
            item_id = item.get("id")
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                merged.append(item)
                if len(merged) >= limit:
                    break

        return merged

    def search_departments(self, query: str, limit: int = 5) -> List[dict]:
        """
        Search departments by substring or acronym.
        """
        if not query:
            return []
        q_lower = query.strip().lower()
        results = []

        for dept in self._cache.get_all_departments():
            en = dept.get("english", "").lower()
            mr = dept.get("marathi", "")
            abbr = dept.get("abbreviation", "").lower()

            if q_lower in en or query.strip() in mr or q_lower == abbr:
                results.append(dept)
                if len(results) >= limit:
                    break
        return results

    def search_phrases(self, query: str, limit: int = 5) -> List[dict]:
        """
        Search standard phrases by text match.
        """
        if not query:
            return []
        q_lower = query.strip().lower()
        results = []

        for phrase in self._cache.get_all_phrases():
            en = phrase.get("english", "").lower()
            mr = phrase.get("marathi", "")

            if q_lower in en or query.strip() in mr:
                results.append(phrase)
                if len(results) >= limit:
                    break
        return results
