# NIRN.Ai — Government Knowledge Base Generator

A one-time offline utility that generates a comprehensive Marathi ↔ English legal and administrative knowledge base from the entire Maharashtra Government Resolution corpus.

> **This tool is designed to be run once and deleted after verification.**  
> The website (`backend/`) only consumes the generated JSON files — it does NOT import this generator.

---

## Prerequisites

- Python 3.10+
- The corpus at `mahGRs-main/GRs/` (already in the repository)

Install the two lightweight dependencies:

```bash
cd glossary_generator
pip install -r requirements.txt
```

No spaCy, no sentence-transformers, no heavy ML libraries required.  
The pipeline is entirely deterministic (regex + frequency analysis + curated seed dictionary).

---

## Quick Start

```bash
cd glossary_generator

# Standard run (resumes from checkpoint if interrupted)
python generate_glossary.py

# Fresh run (ignores any saved checkpoint)
python generate_glossary.py --fresh

# With LLM validation for low-confidence candidates (requires Ollama running)
python generate_glossary.py --llm

# Verbose debugging
python generate_glossary.py --verbose

# Control parallelism
python generate_glossary.py --workers 8 --batch 100
```

---

## Output

All files are written to `backend/data/glossary/`:

| File | Description |
|---|---|
| `government_knowledge_base.json` | Master knowledge base — all aligned bilingual pairs |
| `legal_glossary.json` | Legal & Office Procedure terms only |
| `department_names.json` | All 33 department names with Marathi equivalents |
| `office_designations.json` | Titles and designations |
| `government_phrases.json` | Standard GR phrases (bilingual) |
| `budget_heads.json` | Budget head codes extracted from corpus |
| `statistics.json` | Full run statistics and metrics |
| `review_candidates.json` | Low-confidence pairs for manual verification |

### Entry Structure

```json
{
  "id": "uuid-v5-of-english|marathi",
  "english": "Administrative Approval",
  "marathi": "प्रशासकीय मान्यता",
  "category": "Administration",
  "aliases": [],
  "frequency": 847,
  "confidence": 1.0,
  "sources": ["201710121514029708", "201711061646497708"],
  "example_usage": [
    {"language": "en", "text": "Administrative approval is hereby accorded..."},
    {"language": "mr", "text": "प्रशासकीय मान्यता प्रदान करण्यात येत आहे..."}
  ],
  "related_terms": []
}
```

---

## Pipeline

```
Read Documents (parallel, bilingual pairs)
       ↓
OCR Cleaning + Unicode NFC Normalization
       ↓
Language Detection (Devanagari ratio + markers)
       ↓
Sentence Segmentation
       ↓
Phrase Extraction (regex + keyword anchors)
       ↓
Frequency Analysis + Min-frequency filtering
       ↓
Bilingual Alignment (seed dict + position-based)
       ↓
Deduplication
       ↓
Category Classification (keyword vocabulary)
       ↓
[Optional] LLM Validation
       ↓
JSON Export (8 files)
```

---

## Configuration

Edit `config.py` to tune:

| Setting | Default | Description |
|---|---|---|
| `MIN_FREQUENCY` | 3 | Minimum corpus occurrence to include a phrase |
| `CONFIDENCE_THRESHOLD` | 0.70 | Below this → review_candidates.json |
| `NUM_WORKERS` | 4 | Parallel worker processes |
| `BATCH_SIZE` | 50 | GR pairs per batch (for checkpointing) |
| `MAX_PHRASE_TOKENS` | 8 | Maximum words in a phrase |
| `USE_LLM_VALIDATION` | False | Enable LLM validation pass |
| `LLM_PROVIDER` | "ollama" | "ollama" or "gemini" |

---

## Checkpointing

The generator saves progress after each batch to `checkpoint.json`.  
If interrupted (Ctrl+C or crash), restart with:

```bash
python generate_glossary.py   # Automatically resumes
```

To start completely fresh:

```bash
python generate_glossary.py --fresh
```

---

## Logs

Logs are written to `logs/`:
- `generator.log` — Full run log (DEBUG+)
- `errors.log` — Errors only

---

## Architecture

| Module | Responsibility |
|---|---|
| `generate_glossary.py` | Orchestrator / CLI entry point |
| `config.py` | All configurable values |
| `cleaner.py` | OCR cleaning, Unicode normalization, sentence splitting |
| `language_detector.py` | Devanagari ratio + marker-based language detection |
| `extractor.py` | Regex + anchor-based phrase extraction |
| `aligner.py` | Bilingual alignment (seed dict + position-based) |
| `categorizer.py` | Keyword vocabulary category classification |
| `validator.py` | Optional LLM validation layer |
| `statistics.py` | Run statistics dataclass |
| `exporter.py` | JSON writer for all 8 output files |
| `utils.py` | File discovery, logging, checkpointing |

---

## Design Principles

1. **Deterministic first**: No LLM is used unless `--llm` is explicitly passed.
2. **Never hallucinate**: The aligner only confirms pairs it can observe in the corpus. Unknown pairs go to `review_candidates.json`.
3. **Resilient**: Corrupted files are skipped with a log warning. Crashes resume from checkpoint.
4. **Extensible**: Add more patterns to `extractor.py`; add more seed pairs to `aligner.py`.
5. **Zero runtime dependency**: This tool has no connection to the FastAPI backend.

---

## After Generation

1. Review `review_candidates.json` manually for any borderline pairs.
2. Verify `statistics.json` for expected counts.
3. The website reads from `backend/data/glossary/` automatically.
4. Delete this entire `glossary_generator/` directory.
