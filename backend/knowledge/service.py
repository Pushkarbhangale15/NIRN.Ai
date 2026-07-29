"""
service.py — KnowledgeService singleton facade.

Central entry point for every backend module needing terminology,
departments, designations, standard phrases, or budget heads.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .cache import KnowledgeCache
from .loader import load_all_datasets, KnowledgeBaseLoadError
from .matcher import TermMatcher
from .search import KnowledgeSearcher

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Singleton Knowledge Service.
    Wraps loading, indexing, matching, and search operations into a clean API.
    """

    _instance: Optional["KnowledgeService"] = None
    _init_lock = threading.Lock()

    def __init__(self, glossary_dir: Optional[str] = None):
        self._cache = KnowledgeCache()
        self._matcher = TermMatcher(self._cache)
        self._searcher = KnowledgeSearcher(self._cache)
        self._glossary_dir = glossary_dir
        self.initialize(glossary_dir)

    def initialize(self, glossary_dir: Optional[str] = None) -> None:
        """
        Load datasets into cache. Called automatically during instantiation.
        Safe to call again if path changes.
        """
        target_dir = glossary_dir or self._glossary_dir
        datasets = load_all_datasets(target_dir)
        self._cache.populate(datasets)
        stats = self._cache.get_stats()
        logger.info(
            "KnowledgeService initialized | %d terms | %d departments | %d designations",
            stats["total_terms"], stats["total_departments"], stats["total_designations"]
        )

    # ── Master Term Queries ──────────────────────────────────────────

    def find_term(self, term: str) -> Optional[dict]:
        """
        Lookup a term entry by English name, Marathi name, or alias.
        """
        return self._matcher.match_term(term)

    def find_terms(self, category: Optional[str] = None, min_confidence: float = 0.0) -> List[dict]:
        """
        Return terms matching category or confidence filters.
        """
        all_terms = self._cache.get_all_terms()
        if category:
            all_terms = [t for t in all_terms if t.get("category", "").lower() == category.lower()]
        if min_confidence > 0:
            all_terms = [t for t in all_terms if t.get("confidence", 0.0) >= min_confidence]
        return all_terms

    def find_department(self, name: str) -> Optional[dict]:
        """
        Lookup department entry by English name, Marathi name, or abbreviation.
        """
        return self._matcher.match_department(name)

    def find_designation(self, name: str) -> Optional[dict]:
        """
        Lookup designation by English or Marathi title.
        """
        return self._matcher.match_designation(name)

    def find_phrase(self, phrase: str) -> Optional[dict]:
        """
        Lookup standard government phrase by English or Marathi text.
        """
        return self._matcher.match_phrase(phrase)

    def find_budget_head(self, code: str) -> Optional[dict]:
        """
        Lookup budget head entry by numeric code string.
        """
        return self._matcher.match_budget_head(code)

    def find_category(self, category_name: str) -> List[dict]:
        """
        Return all terms belonging to a category.
        """
        return self._matcher.get_category_terms(category_name)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.0
    ) -> List[dict]:
        """
        Search terms with partial, prefix, and fuzzy matching.
        """
        return self._searcher.search(query, category=category, limit=limit, min_confidence=min_confidence)

    def lookup_alias(self, alias: str) -> Optional[dict]:
        """
        Lookup term by alias string.
        """
        return self._cache.get_term_by_alias(alias)

    def lookup_marathi(self, english_term: str) -> Optional[str]:
        """
        Lookup approved Marathi translation for an English term.
        """
        return self._matcher.match_marathi_translation(english_term)

    def lookup_english(self, marathi_term: str) -> Optional[str]:
        """
        Lookup approved English translation for a Marathi term.
        """
        return self._matcher.match_english_translation(marathi_term)

    def get_related_terms(self, term: str) -> List[dict]:
        """
        Return related term entries for a given term.
        """
        return self._matcher.get_related_terms(term)

    def get_all_departments(self) -> List[dict]:
        """
        Return all 33 department entries.
        """
        return self._cache.get_all_departments()

    def get_all_glossary_terms(self) -> List[dict]:
        """
        Return all master knowledge base term entries.
        """
        return self._cache.get_all_terms()

    def get_all_designations(self) -> List[dict]:
        """
        Return all designation entries.
        """
        return self._cache.get_all_designations()

    def get_all_phrases(self) -> List[dict]:
        """
        Return all standard phrase entries.
        """
        return self._cache.get_all_phrases()

    def get_summary_stats(self) -> dict:
        """
        Return cache loading & dataset summary statistics.
        """
        return self._cache.get_stats()


# ── Global Singleton Pattern ──────────────────────────────────────────

_instance: Optional[KnowledgeService] = None
_lock = threading.Lock()


def get_knowledge_service(glossary_dir: Optional[str] = None) -> KnowledgeService:
    """
    Thread-safe accessor for the global KnowledgeService singleton.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = KnowledgeService(glossary_dir)
    return _instance


# Convenient alias
knowledge_service = get_knowledge_service
