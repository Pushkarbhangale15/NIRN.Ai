#!/usr/bin/env python3
"""
generate_glossary.py — Main entry point for the NIRN.Ai Knowledge Base Generator.

This is a one-time offline utility. Run it once; delete it after verification.

Usage:
    python generate_glossary.py [--fresh] [--llm] [--verbose]

Options:
    --fresh     Ignore existing checkpoint and start from scratch.
    --llm       Enable LLM validation for low-confidence candidates.
    --verbose   Enable DEBUG-level logging.
    --workers N Number of parallel workers (default: from config).
    --batch N   Batch size (default: from config).
"""

import argparse
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

# ── Bootstrap: ensure this directory is on sys.path ──────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

import config
from aligner import AlignedPair, BilingualAligner
from categorizer import classify
from cleaner import clean_text, detect_language, remove_page_headers, split_sentences
from exporter import KnowledgeBaseExporter
from extractor import PhraseExtractor
from statistics import GenerationStats
from utils import (
    DEPARTMENT_MARATHI_NAMES,
    clear_checkpoint,
    discover_documents,
    load_checkpoint,
    read_file_safe,
    save_checkpoint,
    setup_logging,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Worker function (runs in subprocess for parallel processing)
# ─────────────────────────────────────────────────────────────────────────────

def _process_document_pair(args: Tuple) -> Optional[dict]:
    """
    Process a single bilingual GR document pair (en + mr).

    This function is designed to run in a subprocess. All imports are
    local to avoid pickling issues.

    Args:
        args: Tuple of (en_path, mr_path, gr_id, department, config_dict)

    Returns:
        Dict with extracted data, or None on failure.
    """
    en_path, mr_path, gr_id, department = args

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from cleaner import clean_text, detect_language, remove_page_headers, split_sentences
        from extractor import PhraseExtractor

        extractor = PhraseExtractor(
            min_phrase_chars=config.MIN_PHRASE_CHARS,
            max_phrase_tokens=config.MAX_PHRASE_TOKENS,
        )

        result = {
            "gr_id": gr_id,
            "department": department,
            "en_phrases": [],
            "mr_phrases": [],
            "en_sentences": [],
            "mr_sentences": [],
            "budget_heads": [],
            "language": "unknown",
        }

        # Read English file
        if en_path and os.path.exists(en_path):
            raw_en = _read_file(en_path)
            if raw_en:
                en_text = clean_text(raw_en, preserve_structure=True)
                en_text = remove_page_headers(en_text)
                en_phrases = extractor.extract(en_text, "en", gr_id, department)
                result["en_phrases"] = [p.text for p in en_phrases]
                result["en_sentences"] = split_sentences(en_text)[:100]  # cap for memory
                result["en_budget"] = [
                    p.text for p in en_phrases if p.category_hint == "Budget"
                ]

        # Read Marathi file
        if mr_path and os.path.exists(mr_path):
            raw_mr = _read_file(mr_path)
            if raw_mr:
                mr_text = clean_text(raw_mr, preserve_structure=True)
                mr_text = remove_page_headers(mr_text)
                mr_phrases = extractor.extract(mr_text, "mr", gr_id, department)
                result["mr_phrases"] = [p.text for p in mr_phrases]
                result["mr_sentences"] = split_sentences(mr_text)[:100]
                result["mr_budget"] = [
                    p.text for p in mr_phrases if p.category_hint == "Budget"
                ]

        lang_en = bool(result["en_phrases"])
        lang_mr = bool(result["mr_phrases"])
        if lang_en and lang_mr:
            result["language"] = "bilingual"
        elif lang_en:
            result["language"] = "en"
        elif lang_mr:
            result["language"] = "mr"

        return result

    except Exception as e:
        return {"gr_id": gr_id, "error": str(e)}


def _read_file(path: str) -> Optional[str]:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                return f.read()
        except Exception:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Document grouping: pair .en.txt with .mr.txt by GR ID
# ─────────────────────────────────────────────────────────────────────────────

def group_bilingual_pairs(dataset_path: str) -> List[Tuple]:
    """
    Walk the corpus and group English + Marathi files by GR ID.

    Returns:
        List of (en_path, mr_path, gr_id, department) tuples.
        Either en_path or mr_path may be None for monolingual docs.
    """
    from pathlib import Path
    import os

    pairs = {}  # gr_id -> {"en": path, "mr": path, "dept": name}
    root = Path(dataset_path)

    for dept_dir in sorted(root.iterdir()):
        if not dept_dir.is_dir() or dept_dir.name.startswith('.'):
            continue
        department = dept_dir.name

        for filepath in sorted(dept_dir.iterdir()):
            if filepath.is_dir() or filepath.name.startswith('.'):
                continue

            fname = filepath.name.lower()
            if fname.endswith('.en.txt'):
                gr_id = filepath.name[:-7]  # strip .en.txt
                if gr_id not in pairs:
                    pairs[gr_id] = {"dept": department}
                pairs[gr_id]["en"] = str(filepath)
            elif fname.endswith('.mr.txt'):
                gr_id = filepath.name[:-7]  # strip .mr.txt
                if gr_id not in pairs:
                    pairs[gr_id] = {"dept": department}
                pairs[gr_id]["mr"] = str(filepath)

    result = []
    for gr_id, info in pairs.items():
        result.append((
            info.get("en"),
            info.get("mr"),
            gr_id,
            info["dept"],
        ))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    fresh: bool = False,
    use_llm: bool = False,
    verbose: bool = False,
    num_workers: int = None,
    batch_size: int = None,
):
    """Main pipeline orchestrator."""

    # ── Setup ────────────────────────────────────────────────────────────────
    setup_logging(config.LOG_DIR, verbose=verbose)
    logger.info("=" * 60)
    logger.info("NIRN.Ai Government Knowledge Base Generator")
    logger.info("=" * 60)
    logger.info("Dataset:  %s", config.DATASET_PATH)
    logger.info("Output:   %s", config.OUTPUT_PATH)

    stats = GenerationStats()

    if fresh:
        clear_checkpoint(config.CHECKPOINT_FILE)
        logger.info("Starting fresh (cleared checkpoint).")
    else:
        checkpoint = load_checkpoint(config.CHECKPOINT_FILE)
        processed_gr_ids: Set[str] = set(checkpoint.get("processed_grs", []))
        phrase_freq_raw: Dict[str, int] = checkpoint.get("phrase_freq", {})
        logger.info("Loaded checkpoint: %d GRs already processed.", len(processed_gr_ids))

    if fresh:
        processed_gr_ids = set()
        phrase_freq_raw = {}

    n_workers = num_workers or config.NUM_WORKERS
    b_size = batch_size or config.BATCH_SIZE

    # ── Discover and group documents ─────────────────────────────────────────
    logger.info("Discovering documents in corpus...")
    all_pairs = group_bilingual_pairs(config.DATASET_PATH)
    stats.total_docs_found = len(all_pairs) * 2  # EN + MR per pair
    logger.info("Found %d GR pairs (%d documents total).", len(all_pairs), stats.total_docs_found)

    # Filter out already-processed GRs (checkpointing)
    pending_pairs = [p for p in all_pairs if p[2] not in processed_gr_ids]
    logger.info(
        "%d pairs to process (skipping %d already done).",
        len(pending_pairs), len(all_pairs) - len(pending_pairs)
    )

    # ── Department metadata ──────────────────────────────────────────────────
    dept_data: Dict[str, dict] = {}
    for pair in all_pairs:
        dept = pair[3]
        if dept not in dept_data:
            meta = DEPARTMENT_MARATHI_NAMES.get(dept, {})
            dept_data[dept] = {
                "marathi": meta.get("marathi", ""),
                "abbreviation": meta.get("abbreviation", ""),
                "aliases": [],
                "gr_count": 0,
            }
        dept_data[dept]["gr_count"] += 1

    # ── Extraction: parallel processing ─────────────────────────────────────
    logger.info("Extracting phrases from %d GR pairs (workers=%d, batch=%d)...",
                len(pending_pairs), n_workers, b_size)

    all_en_phrases: List[str] = []
    all_mr_phrases: List[str] = []
    all_bilingual_results = []
    errors = 0

    # Process in batches for checkpointing
    total_batches = (len(pending_pairs) + b_size - 1) // b_size
    batch_num = 0

    for batch_start in range(0, len(pending_pairs), b_size):
        batch = pending_pairs[batch_start:batch_start + b_size]
        batch_num += 1
        logger.info("Processing batch %d/%d (%d pairs)...", batch_num, total_batches, len(batch))

        # Process in parallel
        batch_results = []
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_process_document_pair, args): args for args in batch}
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=60)
                    if result:
                        if "error" in result:
                            logger.warning("Error processing GR %s: %s",
                                           result["gr_id"], result["error"])
                            stats.errors.append(f"{result['gr_id']}: {result['error']}")
                            errors += 1
                        else:
                            batch_results.append(result)
                except Exception as e:
                    logger.error("Future failed: %s", e)
                    errors += 1

        # Accumulate results
        for result in batch_results:
            gr_id = result["gr_id"]
            processed_gr_ids.add(gr_id)
            stats.total_docs_processed += 1

            lang = result.get("language", "unknown")
            if lang == "bilingual":
                stats.docs_bilingual += 1
                stats.docs_english += 1
                stats.docs_marathi += 1
            elif lang == "en":
                stats.docs_english += 1
            elif lang == "mr":
                stats.docs_marathi += 1

            # Count phrase frequencies
            for phrase in result.get("en_phrases", []):
                key = phrase.lower().strip()
                phrase_freq_raw[key] = phrase_freq_raw.get(key, 0) + 1
                all_en_phrases.append(phrase)

            for phrase in result.get("mr_phrases", []):
                key = phrase.strip()
                phrase_freq_raw[key] = phrase_freq_raw.get(key, 0) + 1
                all_mr_phrases.append(phrase)

            all_bilingual_results.append(result)

        stats.total_docs_skipped = errors

        # Save checkpoint after each batch
        save_checkpoint(config.CHECKPOINT_FILE, {
            "processed_grs": list(processed_gr_ids),
            "phrase_freq": phrase_freq_raw,
        })
        logger.info(
            "Batch %d done. Processed: %d | EN phrases so far: %d | MR phrases: %d",
            batch_num, stats.total_docs_processed, len(all_en_phrases), len(all_mr_phrases)
        )

    stats.raw_phrases_extracted = len(all_en_phrases) + len(all_mr_phrases)
    logger.info("Raw phrases extracted: %d", stats.raw_phrases_extracted)

    # ── Frequency filtering ──────────────────────────────────────────────────
    logger.info("Filtering by minimum frequency (%d)...", config.MIN_FREQUENCY)
    qualified_phrases = {
        phrase: count
        for phrase, count in phrase_freq_raw.items()
        if count >= config.MIN_FREQUENCY
    }
    below_min = len(phrase_freq_raw) - len(qualified_phrases)
    stats.below_min_frequency = below_min
    logger.info(
        "Qualified phrases: %d (removed %d below frequency threshold)",
        len(qualified_phrases), below_min
    )

    # ── Bilingual alignment ──────────────────────────────────────────────────
    logger.info("Running bilingual alignment...")
    aligner = BilingualAligner()

    # Start with all seed pairs (always high confidence)
    aligned_pairs: List[AlignedPair] = aligner.get_all_seed_pairs()
    review_candidates: List[AlignedPair] = []

    # Attempt position-based alignment from bilingual document pairs
    qualified_en = [p for p in all_en_phrases if p.lower() in qualified_phrases]
    qualified_mr = [p for p in all_mr_phrases if p in qualified_phrases]

    # De-duplicate for alignment
    unique_en = list(dict.fromkeys(qualified_en))[:500]
    unique_mr = list(dict.fromkeys(qualified_mr))[:500]

    for result in all_bilingual_results:
        if result.get("language") != "bilingual":
            continue
        en_sents = result.get("en_sentences", [])
        mr_sents = result.get("mr_sentences", [])
        if not en_sents or not mr_sents:
            continue

        hi, rev = aligner.align_from_bilingual_documents(
            en_sentences=en_sents,
            mr_sentences=mr_sents,
            gr_id=result["gr_id"],
            en_phrases=unique_en,
            mr_phrases=unique_mr,
        )
        aligned_pairs.extend(hi)
        review_candidates.extend(rev)

    stats.aligned_pairs = len(aligned_pairs)
    logger.info(
        "Alignment complete: %d high-confidence pairs, %d review candidates",
        len(aligned_pairs), len(review_candidates)
    )

    # ── Classify all pairs ───────────────────────────────────────────────────
    logger.info("Classifying terms...")
    for pair in aligned_pairs:
        if pair.category in ("General Government", ""):
            pair.category = classify(pair.english, "en", pair.category)

    # ── LLM validation (optional) ────────────────────────────────────────────
    if use_llm and review_candidates:
        logger.info("Running LLM validation on %d review candidates...", len(review_candidates))
        from validator import validate_candidates_with_llm
        validated, still_uncertain = validate_candidates_with_llm(
            review_candidates,
            provider=config.LLM_PROVIDER,
            ollama_base_url=config.OLLAMA_BASE_URL,
            ollama_model=config.OLLAMA_MODEL,
            gemini_api_key=config.LLM_API_KEY,
        )
        aligned_pairs.extend(validated)
        review_candidates = still_uncertain
        logger.info(
            "LLM validated %d, still uncertain: %d",
            len(validated), len(still_uncertain)
        )

    # ── Deduplicate final pairs ──────────────────────────────────────────────
    logger.info("Deduplicating...")
    seen_keys: Set[str] = set()
    unique_pairs: List[AlignedPair] = []
    for pair in sorted(aligned_pairs, key=lambda p: -p.confidence):
        key = f"{pair.english.lower().strip()}|{pair.marathi.strip()}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_pairs.append(pair)

    stats.duplicates_removed = len(aligned_pairs) - len(unique_pairs)
    logger.info(
        "Deduplicated: %d unique pairs (removed %d duplicates)",
        len(unique_pairs), stats.duplicates_removed
    )

    # ── Export ───────────────────────────────────────────────────────────────
    logger.info("Exporting knowledge base to %s...", config.OUTPUT_PATH)
    exporter = KnowledgeBaseExporter(config.OUTPUT_PATH)
    final_stats = exporter.export_all(
        aligned_pairs=unique_pairs,
        phrase_freq=qualified_phrases,
        dept_data=dept_data,
        stats=stats,
        review_candidates=review_candidates,
        config=config,
    )

    # ── Clear checkpoint on success ───────────────────────────────────────────
    clear_checkpoint(config.CHECKPOINT_FILE)

    # ── Final summary ────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅  GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info("  Documents processed : %d", final_stats.total_docs_processed)
    logger.info("  Bilingual pairs     : %d", final_stats.docs_bilingual)
    logger.info("  Total KB entries    : %d", final_stats.total_glossary_entries)
    logger.info("  Aligned pairs       : %d", final_stats.aligned_pairs)
    logger.info("  Review candidates   : %d", final_stats.total_review_candidates)
    logger.info("  Execution time      : %s", final_stats.elapsed_human)
    logger.info("  Output directory    : %s", config.OUTPUT_PATH)
    logger.info("=" * 60)

    return final_stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NIRN.Ai Government Knowledge Base Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Ignore checkpoint and start from scratch",
    )
    parser.add_argument(
        "--llm", action="store_true",
        help="Enable LLM validation for low-confidence candidates",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG-level logging",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=None,
        help=f"Number of parallel workers (default: {config.NUM_WORKERS})",
    )
    parser.add_argument(
        "--batch", "-b", type=int, default=None,
        help=f"Batch size for processing (default: {config.BATCH_SIZE})",
    )
    args = parser.parse_args()

    try:
        stats = run_pipeline(
            fresh=args.fresh,
            use_llm=args.llm,
            verbose=args.verbose,
            num_workers=args.workers,
            batch_size=args.batch,
        )
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user. Progress saved in checkpoint.")
        sys.exit(1)
    except Exception as e:
        logging.getLogger(__name__).exception("Fatal error: %s", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
