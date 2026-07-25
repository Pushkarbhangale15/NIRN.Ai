"""
config.py — every setting in one place, read from environment variables.

Never hardcode an API key. Put it in the .env file at the repo root
(which is gitignored) and it arrives here automatically.

Import it anywhere as:
    from config import settings
"""

import os

from dotenv import load_dotenv

# Looks for .env in the current directory, then walks upward to the
# repo root. Works whether you launch from backend/ or from the root.
load_dotenv()


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes"}


class Settings:
    # --- Identity ---
    APP_NAME = "NIRN.Ai"
    VERSION = "0.1.0"
    DEBUG = _bool("DEBUG", True)

    # --- Frontend origins allowed to call this API ---
    # Vite dev server runs on 5173, Create React App on 3000.
    # If Tanmay uses a different port, add it here or the browser
    # silently blocks every request.
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Vector database (Prasad) ---
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "mah_grs")

    # Must match the embedding model's output size, or every insert
    # into Qdrant is rejected.
    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    # --- Language model ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")   # gemini | anthropic | openai
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

    # --- Retrieval and analysis tuning ---
    TOP_K = int(os.getenv("TOP_K", "8"))                 # passages fetched per query
    CANDIDATES_PER_CLAUSE = int(os.getenv("CANDIDATES_PER_CLAUSE", "3"))
    MAX_CLAUSES_ANALYSED = int(os.getenv("MAX_CLAUSES_ANALYSED", "5"))

    # Conflicts below this confidence are hidden. A false alarm wastes
    # more of an officer's time than a miss does.
    CONFLICT_CONFIDENCE_FLOOR = float(os.getenv("CONFLICT_CONFIDENCE_FLOOR", "0.55"))

    # --- Chunking ---
    CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "1200"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))


settings = Settings()
