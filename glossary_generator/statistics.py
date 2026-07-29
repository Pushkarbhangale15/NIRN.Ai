"""
statistics.py — Collect and format run statistics.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GenerationStats:
    """Runtime statistics for a single glossary generation run."""

    # Document counts
    total_docs_found: int = 0
    total_docs_processed: int = 0
    total_docs_skipped: int = 0
    docs_marathi: int = 0
    docs_english: int = 0
    docs_bilingual: int = 0

    # Extraction counts
    raw_phrases_extracted: int = 0
    duplicates_removed: int = 0
    below_min_frequency: int = 0

    # Final output counts
    total_glossary_entries: int = 0
    total_review_candidates: int = 0
    low_confidence_entries: int = 0
    aligned_pairs: int = 0

    # Category breakdown
    entries_by_category: Dict[str, int] = field(default_factory=dict)

    # Department breakdown
    entries_by_department: Dict[str, int] = field(default_factory=dict)

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def stop_timer(self):
        self.end_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        if self.end_time > 0:
            return round(self.end_time - self.start_time, 2)
        return round(time.time() - self.start_time, 2)

    @property
    def elapsed_human(self) -> str:
        secs = self.elapsed_seconds
        if secs < 60:
            return f"{secs:.1f} seconds"
        mins = int(secs // 60)
        secs_rem = secs % 60
        return f"{mins}m {secs_rem:.0f}s"

    def to_dict(self) -> dict:
        return {
            "execution_time": self.elapsed_human,
            "execution_seconds": self.elapsed_seconds,
            "documents": {
                "total_found":      self.total_docs_found,
                "total_processed":  self.total_docs_processed,
                "total_skipped":    self.total_docs_skipped,
                "marathi":          self.docs_marathi,
                "english":          self.docs_english,
                "bilingual_pairs":  self.docs_bilingual,
            },
            "extraction": {
                "raw_phrases_extracted": self.raw_phrases_extracted,
                "duplicates_removed":    self.duplicates_removed,
                "below_min_frequency":   self.below_min_frequency,
            },
            "output": {
                "total_glossary_entries":    self.total_glossary_entries,
                "total_review_candidates":   self.total_review_candidates,
                "low_confidence_entries":    self.low_confidence_entries,
                "aligned_bilingual_pairs":   self.aligned_pairs,
            },
            "by_category":   self.entries_by_category,
            "by_department": self.entries_by_department,
            "errors":        self.errors,
            "warnings":      self.warnings,
        }
