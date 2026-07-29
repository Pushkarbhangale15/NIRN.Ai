"""
config.py — Central configuration for the NIRN.Ai Glossary Generator.

All paths, thresholds, and tunable parameters live here.
Change values here without touching any other module.
"""

import os

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

# Root of the repository (one level above glossary_generator/)
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Input: Maharashtra GR corpus
DATASET_PATH = os.path.join(_REPO_ROOT, "mahGRs-main", "GRs")

# Output: Generated knowledge base JSON files
OUTPUT_PATH = os.path.join(_REPO_ROOT, "backend", "data", "glossary")

# Logs directory (inside glossary_generator/)
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

# Checkpoint file to resume interrupted runs
CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "checkpoint.json")

# ─────────────────────────────────────────────────────────────────────────────
# Processing parameters
# ─────────────────────────────────────────────────────────────────────────────

# Minimum number of times a phrase must appear across all GRs to be included
MIN_FREQUENCY = 3

# Confidence threshold below which a term goes to review_candidates.json
CONFIDENCE_THRESHOLD = 0.70

# Number of worker processes for parallel document loading
NUM_WORKERS = 4

# Number of documents per batch during processing
BATCH_SIZE = 50

# Maximum phrase length in tokens (words) — phrases longer than this are skipped
MAX_PHRASE_TOKENS = 8

# Minimum phrase length in tokens
MIN_PHRASE_TOKENS = 2

# Minimum character length for a phrase to be kept
MIN_PHRASE_CHARS = 5

# ─────────────────────────────────────────────────────────────────────────────
# File types to process
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".txt", ".md", ".html", ".json"}

# ─────────────────────────────────────────────────────────────────────────────
# LLM (optional — only for final validation pass)
# ─────────────────────────────────────────────────────────────────────────────

# Set to False to skip LLM validation (deterministic-only mode)
USE_LLM_VALIDATION = False

# LLM provider: "ollama" or "gemini"
LLM_PROVIDER = "ollama"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma3:4b"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
# Category definitions
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = [
    "Administration",
    "Finance",
    "Education",
    "Revenue",
    "Agriculture",
    "Judiciary",
    "Personnel",
    "Budget",
    "Office Procedure",
    "Infrastructure",
    "Legal",
    "Healthcare",
    "Rural Development",
    "Urban Development",
    "General Government",
]

# ─────────────────────────────────────────────────────────────────────────────
# Output filenames
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_FILES = {
    "knowledge_base":   "government_knowledge_base.json",
    "legal_glossary":   "legal_glossary.json",
    "departments":      "department_names.json",
    "designations":     "office_designations.json",
    "phrases":          "government_phrases.json",
    "budget_heads":     "budget_heads.json",
    "statistics":       "statistics.json",
    "review":           "review_candidates.json",
}
