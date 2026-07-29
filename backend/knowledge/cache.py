"""
cache.py — In-memory thread-safe cache for Knowledge Base queries.

Pre-indexes terms, departments, designations, and phrases into O(1) hash maps.
Zero file I/O during request servicing.
"""

import threading
from typing import Any, Dict, List, Optional, Set


class KnowledgeCache:
    """
    Thread-safe in-memory cache and index container.
    """

    def __init__(self):
        self._lock = threading.RLock()

        # Datasets
        self._raw_datasets: Dict[str, Any] = {}

        # Master term indexes
        self._all_terms: List[dict] = []
        self._terms_by_id: Dict[str, dict] = {}
        self._terms_by_english: Dict[str, dict] = {}
        self._terms_by_marathi: Dict[str, dict] = {}
        self._terms_by_alias: Dict[str, dict] = {}
        self._terms_by_category: Dict[str, List[dict]] = {}

        # Department indexes
        self._all_departments: List[dict] = []
        self._departments_by_name: Dict[str, dict] = {}
        self._departments_by_alias: Dict[str, dict] = {}

        # Sub-collections
        self._designations: List[dict] = []
        self._phrases: List[dict] = []
        self._budget_heads: List[dict] = []
        self._legal_glossary: List[dict] = []

        # Stats
        self._is_loaded: bool = False
        self._load_timestamp: float = 0.0

    def is_loaded(self) -> bool:
        with self._lock:
            return self._is_loaded

    def populate(self, datasets: Dict[str, Any]) -> None:
        """
        Populate and index all loaded datasets in RAM.
        """
        with self._lock:
            self._raw_datasets = datasets

            # 1. Master Knowledge Base
            kb_data = datasets.get("knowledge_base", {})
            self._all_terms = kb_data.get("entries", [])

            self._terms_by_id.clear()
            self._terms_by_english.clear()
            self._terms_by_marathi.clear()
            self._terms_by_alias.clear()
            self._terms_by_category.clear()

            for entry in self._all_terms:
                term_id = entry.get("id", "")
                en_term = entry.get("english", "").strip()
                mr_term = entry.get("marathi", "").strip()
                category = entry.get("category", "General Government").strip()

                if term_id:
                    self._terms_by_id[term_id] = entry
                if en_term:
                    self._terms_by_english[en_term.lower()] = entry
                if mr_term:
                    self._terms_by_marathi[mr_term] = entry

                for alias in entry.get("aliases", []):
                    if alias and isinstance(alias, str):
                        self._terms_by_alias[alias.lower().strip()] = entry

                if category not in self._terms_by_category:
                    self._terms_by_category[category] = []
                self._terms_by_category[category].append(entry)

            # 2. Departments
            dept_data = datasets.get("departments", {})
            self._all_departments = dept_data.get("entries", [])
            self._departments_by_name.clear()
            self._departments_by_alias.clear()

            for dept in self._all_departments:
                en_dept = dept.get("english", "").strip()
                mr_dept = dept.get("marathi", "").strip()
                abbr = dept.get("abbreviation", "").strip()

                if en_dept:
                    self._departments_by_name[en_dept.lower()] = dept
                if mr_dept:
                    self._departments_by_name[mr_dept] = dept
                if abbr:
                    self._departments_by_alias[abbr.lower()] = dept

                for alias in dept.get("aliases", []):
                    if alias and isinstance(alias, str):
                        self._departments_by_alias[alias.lower().strip()] = dept

            # 3. Designations
            desig_data = datasets.get("designations", {})
            self._designations = desig_data.get("entries", [])

            # 4. Phrases
            phrase_data = datasets.get("phrases", {})
            self._phrases = phrase_data.get("entries", [])

            # 5. Budget Heads
            budget_data = datasets.get("budget_heads", {})
            self._budget_heads = budget_data.get("entries", [])

            # 6. Legal Glossary
            legal_data = datasets.get("legal_glossary", {})
            self._legal_glossary = legal_data.get("entries", [])

            self._is_loaded = True

    # ── Thread-safe getters ─────────────────────────────────────────

    def get_all_terms(self) -> List[dict]:
        with self._lock:
            return list(self._all_terms)

    def get_term_by_english(self, term: str) -> Optional[dict]:
        with self._lock:
            return self._terms_by_english.get(term.lower().strip())

    def get_term_by_marathi(self, term: str) -> Optional[dict]:
        with self._lock:
            return self._terms_by_marathi.get(term.strip())

    def get_term_by_alias(self, alias: str) -> Optional[dict]:
        with self._lock:
            return self._terms_by_alias.get(alias.lower().strip())

    def get_term_by_id(self, term_id: str) -> Optional[dict]:
        with self._lock:
            return self._terms_by_id.get(term_id)

    def get_terms_by_category(self, category: str) -> List[dict]:
        with self._lock:
            return list(self._terms_by_category.get(category, []))

    def get_all_departments(self) -> List[dict]:
        with self._lock:
            return list(self._all_departments)

    def get_department(self, name: str) -> Optional[dict]:
        with self._lock:
            key_raw = name.strip()
            key_lower = key_raw.lower()
            key_space_lower = key_raw.replace("_", " ").lower()
            key_space_raw = key_raw.replace("_", " ")

            return (
                self._departments_by_name.get(key_space_lower)
                or self._departments_by_name.get(key_lower)
                or self._departments_by_name.get(key_space_raw)
                or self._departments_by_name.get(key_raw)
                or self._departments_by_alias.get(key_space_lower)
                or self._departments_by_alias.get(key_lower)
            )


    def get_all_designations(self) -> List[dict]:
        with self._lock:
            return list(self._designations)

    def get_all_phrases(self) -> List[dict]:
        with self._lock:
            return list(self._phrases)

    def get_all_budget_heads(self) -> List[dict]:
        with self._lock:
            return list(self._budget_heads)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "is_loaded": self._is_loaded,
                "total_terms": len(self._all_terms),
                "total_departments": len(self._all_departments),
                "total_designations": len(self._designations),
                "total_phrases": len(self._phrases),
                "total_budget_heads": len(self._budget_heads),
                "categories_count": len(self._terms_by_category),
            }
