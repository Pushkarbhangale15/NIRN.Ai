"""
matcher.py — Term and entity matching logic.

Provides deterministic exact, case-insensitive, alias, Marathi, English,
and category matching using the KnowledgeCache.
"""

from typing import Dict, List, Optional
from .cache import KnowledgeCache


class TermMatcher:
    """
    Handles exact, case-insensitive, language-specific, alias,
    and category matching over cached datasets.
    """

    def __init__(self, cache: KnowledgeCache):
        self._cache = cache

    def match_term(self, query: str) -> Optional[dict]:
        """
        Find a term entry by trying:
          1. Exact English match (case-insensitive)
          2. Exact Marathi match
          3. Exact Alias match
        """
        if not query or not isinstance(query, str):
            return None

        cleaned = query.strip()
        if not cleaned:
            return None

        # 1. English
        match = self._cache.get_term_by_english(cleaned)
        if match:
            return match

        # 2. Marathi
        match = self._cache.get_term_by_marathi(cleaned)
        if match:
            return match

        # 3. Alias
        match = self._cache.get_term_by_alias(cleaned)
        if match:
            return match

        return None

    def match_marathi_translation(self, english_term: str) -> Optional[str]:
        """
        Return the approved Marathi translation for an English term.
        """
        entry = self.match_term(english_term)
        if entry:
            return entry.get("marathi", "")
        return None

    def match_english_translation(self, marathi_term: str) -> Optional[str]:
        """
        Return the approved English term for a Marathi term.
        """
        entry = self.match_term(marathi_term)
        if entry:
            return entry.get("english", "")
        return None

    def match_department(self, name: str) -> Optional[dict]:
        """
        Find a department entry by English name, Marathi name, or abbreviation/alias.
        """
        if not name or not isinstance(name, str):
            return None
        return self._cache.get_department(name.strip())

    def match_designation(self, query: str) -> Optional[dict]:
        """
        Find an office designation by English or Marathi title.
        """
        if not query or not isinstance(query, str):
            return None
        cleaned = query.strip().lower()

        for desig in self._cache.get_all_designations():
            if desig.get("english", "").lower() == cleaned or desig.get("marathi", "").strip() == query.strip():
                return desig
        return None

    def match_phrase(self, query: str) -> Optional[dict]:
        """
        Find a standard government phrase by English or Marathi text.
        """
        if not query or not isinstance(query, str):
            return None
        cleaned = query.strip().lower()

        for phrase in self._cache.get_all_phrases():
            if phrase.get("english", "").lower() == cleaned or phrase.get("marathi", "").strip() == query.strip():
                return phrase
        return None

    def match_budget_head(self, code: str) -> Optional[dict]:
        """
        Find a budget head by code string.
        """
        if not code or not isinstance(code, str):
            return None
        cleaned = code.strip()

        for head in self._cache.get_all_budget_heads():
            if head.get("code", "").strip() == cleaned:
                return head
        return None

    def get_category_terms(self, category_name: str) -> List[dict]:
        """
        Return all terms belonging to a specific category.
        """
        if not category_name:
            return []
        return self._cache.get_terms_by_category(category_name.strip())

    def get_related_terms(self, term: str) -> List[dict]:
        """
        Return related terms for a given term entry.
        """
        entry = self.match_term(term)
        if not entry:
            return []

        related_ids = entry.get("related_terms", [])
        results = []
        for rid in related_ids:
            rel_entry = self._cache.get_term_by_id(rid)
            if rel_entry:
                results.append(rel_entry)
        return results
