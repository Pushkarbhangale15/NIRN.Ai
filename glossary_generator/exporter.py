"""
exporter.py — Write all generated knowledge base files to disk.

Generates the 8 output JSON files in backend/data/glossary/:
  - government_knowledge_base.json
  - legal_glossary.json
  - department_names.json
  - office_designations.json
  - government_phrases.json
  - budget_heads.json
  - statistics.json
  - review_candidates.json
"""

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _write_json(path: str, data: Any, description: str):
    """Write data as pretty-printed JSON. Creates parent directories."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(path) / 1024
    logger.info("Wrote %s: %s (%.1f KB)", description, os.path.basename(path), size_kb)


def make_entry(
    english: str,
    marathi: str,
    category: str,
    frequency: int,
    confidence: float,
    sources: List[str],
    aliases: List[str] = None,
    example_en: str = "",
    example_mr: str = "",
    related_terms: List[str] = None,
) -> dict:
    """Build a standard knowledge base entry."""
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{english}|{marathi}")),
        "english": english,
        "marathi": marathi,
        "category": category,
        "aliases": aliases or [],
        "frequency": frequency,
        "confidence": round(confidence, 4),
        "sources": sources[:10],  # cap to 10 source GR IDs
        "example_usage": [
            {"language": "en", "text": example_en[:250]} if example_en else None,
            {"language": "mr", "text": example_mr[:250]} if example_mr else None,
        ],
        "related_terms": related_terms or [],
    }


class KnowledgeBaseExporter:
    """
    Assembles and writes all output JSON files from the collected data.
    """

    def __init__(self, output_path: str):
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)

    def export_all(
        self,
        aligned_pairs: list,      # List[AlignedPair]
        phrase_freq: dict,         # phrase_text -> count
        dept_data: dict,           # dept_name -> {aliases, departments}
        stats: Any,                # GenerationStats
        review_candidates: list,   # List[AlignedPair]
        config: Any,               # config module
    ):
        """
        Run the full export pipeline.
        """
        logger.info("Starting export of %d aligned pairs...", len(aligned_pairs))
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # ── 1. Build master knowledge base ──────────────────────────────────
        kb_entries = []
        legal_entries = []
        phrase_entries = []
        designation_entries = []

        category_counts = defaultdict(int)

        for pair in aligned_pairs:
            freq = phrase_freq.get(pair.english.lower(), 1)
            entry = make_entry(
                english=pair.english,
                marathi=pair.marathi,
                category=pair.category,
                frequency=freq,
                confidence=pair.confidence,
                sources=pair.sources,
                example_en=pair.example_en,
                example_mr=pair.example_mr,
            )
            kb_entries.append(entry)
            category_counts[pair.category] += 1

            # Route into sub-files
            cat = pair.category.lower()
            if cat in ("legal", "office procedure"):
                legal_entries.append(entry)
            elif "procedure" in cat or cat == "office procedure":
                phrase_entries.append(entry)
            elif cat == "personnel" or "secretary" in pair.english.lower() or "officer" in pair.english.lower():
                designation_entries.append(entry)

        # Sort by frequency (most common first)
        kb_entries.sort(key=lambda e: -e["frequency"])

        # ── 2. Build budget heads (from phrase frequency data) ───────────────
        import re
        budget_head_pattern = re.compile(r'^\d{4}[-–]\d{2}[-–]\d{3}[-–]\d{2}$')
        budget_entries = []
        for phrase, freq in phrase_freq.items():
            if budget_head_pattern.match(phrase.strip()):
                budget_entries.append({
                    "code": phrase.strip(),
                    "frequency": freq,
                    "description": "",  # Future: map from official head list
                })
        budget_entries.sort(key=lambda e: -e["frequency"])

        # ── 3. Build department names file ──────────────────────────────────
        dept_entries = []
        for dept_name, info in dept_data.items():
            dept_entries.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, dept_name)),
                "english": dept_name.replace("_", " "),
                "marathi": info.get("marathi", ""),
                "abbreviation": info.get("abbreviation", ""),
                "aliases": info.get("aliases", []),
                "gr_count": info.get("gr_count", 0),
                "category": "Administration",
            })
        dept_entries.sort(key=lambda e: e["english"])

        # ── 4. Government phrases file ───────────────────────────────────────
        # Include both extracted and the built-in standard phrases
        from extractor import STANDARD_EN_PHRASES, STANDARD_MR_PHRASES

        std_phrase_entries = []
        for i, (en_ph, mr_ph) in enumerate(zip(STANDARD_EN_PHRASES, STANDARD_MR_PHRASES)):
            std_phrase_entries.append(make_entry(
                english=en_ph,
                marathi=mr_ph,
                category="Office Procedure",
                frequency=999,  # Always include these
                confidence=1.0,
                sources=["curated"],
            ))

        # Add corpus-extracted phrases
        all_phrase_entries = std_phrase_entries + phrase_entries

        # ── 5. Review candidates ─────────────────────────────────────────────
        review_entries = []
        for pair in review_candidates:
            review_entries.append({
                "english": pair.english,
                "marathi": pair.marathi,
                "confidence": round(pair.confidence, 4),
                "method": pair.method,
                "sources": pair.sources[:5],
                "category_hint": pair.category,
                "reason": "Below confidence threshold — needs manual verification",
            })

        # ── 6. Update stats ──────────────────────────────────────────────────
        stats.total_glossary_entries = len(kb_entries)
        stats.total_review_candidates = len(review_entries)
        stats.low_confidence_entries = sum(1 for e in kb_entries if e["confidence"] < 0.85)
        stats.entries_by_category = dict(category_counts)
        stats.entries_by_department = {d: info.get("gr_count", 0) for d, info in dept_data.items()}
        stats.stop_timer()

        # ── 7. Write all files ───────────────────────────────────────────────
        header = {"generated_at": ts, "generator": "NIRN.Ai Glossary Generator v1.0"}

        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["knowledge_base"]),
            {**header, "total": len(kb_entries), "entries": kb_entries},
            "Government Knowledge Base",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["legal_glossary"]),
            {**header, "total": len(legal_entries), "entries": legal_entries},
            "Legal Glossary",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["departments"]),
            {**header, "total": len(dept_entries), "entries": dept_entries},
            "Department Names",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["designations"]),
            {**header, "total": len(designation_entries), "entries": designation_entries},
            "Office Designations",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["phrases"]),
            {**header, "total": len(all_phrase_entries), "entries": all_phrase_entries},
            "Government Phrases",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["budget_heads"]),
            {**header, "total": len(budget_entries), "entries": budget_entries},
            "Budget Heads",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["review"]),
            {**header, "total": len(review_entries), "entries": review_entries},
            "Review Candidates",
        )
        _write_json(
            os.path.join(self.output_path, config.OUTPUT_FILES["statistics"]),
            {**header, "run_statistics": stats.to_dict()},
            "Statistics",
        )

        logger.info(
            "Export complete: %d KB entries, %d review candidates, %d budget heads",
            len(kb_entries), len(review_entries), len(budget_entries),
        )
        return stats
