"""
loader.py — Knowledge base JSON file loader.

Loads all verified JSON datasets from backend/data/glossary/ at startup.
Never re-opens files during requests.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class KnowledgeBaseLoadError(Exception):
    """Raised when the master knowledge base file cannot be loaded."""
    pass


# Default path relative to backend/
_DEFAULT_GLOSSARY_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "glossary")
)

# File definitions
_FILES = {
    "knowledge_base": "government_knowledge_base.json",
    "legal_glossary": "legal_glossary.json",
    "departments":    "department_names.json",
    "designations":   "office_designations.json",
    "phrases":        "government_phrases.json",
    "budget_heads":   "budget_heads.json",
}


def load_all_datasets(glossary_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Load all verified JSON datasets into a dictionary.

    Args:
        glossary_dir: Directory containing glossary JSON files.
                      Defaults to backend/data/glossary/.

    Returns:
        Dict mapping dataset key to loaded JSON dict data.

    Raises:
        KnowledgeBaseLoadError: If master government_knowledge_base.json fails to load.
    """
    target_dir = glossary_dir or _DEFAULT_GLOSSARY_DIR
    start_time = time.perf_counter()

    datasets: Dict[str, Any] = {}
    master_loaded = False

    logger.info("Loading Government Knowledge Base from %s...", target_dir)

    for key, filename in _FILES.items():
        filepath = os.path.join(target_dir, filename)
        if not os.path.exists(filepath):
            msg = f"Knowledge base file not found: {filepath}"
            if key == "knowledge_base":
                logger.error("CRITICAL: %s", msg)
                raise KnowledgeBaseLoadError(msg)
            else:
                logger.warning("%s (skipping optional dataset)", msg)
                datasets[key] = {"entries": []}
                continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            datasets[key] = data
            if key == "knowledge_base":
                master_loaded = True
            logger.debug("Loaded %s: %d items", filename, data.get("total", len(data.get("entries", []))))
        except Exception as exc:
            msg = f"Failed to parse {filename}: {exc}"
            if key == "knowledge_base":
                logger.error("CRITICAL: %s", msg)
                raise KnowledgeBaseLoadError(msg) from exc
            else:
                logger.warning("%s (skipping optional dataset)", msg)
                datasets[key] = {"entries": []}

    if not master_loaded:
        raise KnowledgeBaseLoadError("Master knowledge base was not loaded.")

    elapsed = round((time.perf_counter() - start_time) * 1000, 2)
    kb_entries = len(datasets.get("knowledge_base", {}).get("entries", []))
    dept_entries = len(datasets.get("departments", {}).get("entries", []))
    desig_entries = len(datasets.get("designations", {}).get("entries", []))

    logger.info(
        "Knowledge Base loaded successfully in %s ms | "
        "%d terms, %d departments, %d designations",
        elapsed, kb_entries, dept_entries, desig_entries
    )

    return datasets
