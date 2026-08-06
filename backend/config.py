"""
config.py — central configuration for NIRN.Ai backend.

Every value that might vary between local development and the production
demo environment lives here.  Other modules import `settings` and read
from it; nothing should hard-code a port, key, or threshold directly.

Switch LLM provider in your .env:

    # Offline (Ollama — 100% free, no internet after model download)
    LLM_PROVIDER=ollama
    OLLAMA_MODEL=gemma3:4b

    # Online (Google AI Studio — free quota)
    LLM_PROVIDER=gemini
    LLM_API_KEY=AIza...
"""

import os
from typing import List

from dotenv import load_dotenv

# Resolve .env from the project root (one level above backend/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path, override=True)

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- Identity ----------------------------------------------------------
    APP_NAME: str = "NIRN.Ai"
    VERSION: str = "1.0.0"

    # ---- Debug mode --------------------------------------------------------
    # Set DEBUG=true in .env for verbose logging.
    DEBUG: bool = False

    # ---- CORS --------------------------------------------------------------
    # The React dev server runs on 5173 by default; add 3000 as a fallback.
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # ---- LLM provider selection --------------------------------------------
    # "gemini" (default) uses Google AI Studio.
    # "ollama" runs a model locally via Ollama — no API key needed.
    LLM_PROVIDER: str = Field(default=os.getenv("LLM_PROVIDER", "gemini"), alias="LLM_PROVIDER")

    # ---- Gemini (Google AI Studio) -----------------------------------------
    LLM_API_KEY: str = Field(default=os.getenv("LLM_API_KEY", "your-api-key-here"), alias="LLM_API_KEY")
    LLM_MODEL: str = Field(default=os.getenv("LLM_MODEL", "gemini-2.0-flash"), alias="LLM_MODEL")

    # ---- Ollama (local, offline) -------------------------------------------
    # Install Ollama: https://ollama.com  then run: ollama pull gemma3:4b
    OLLAMA_MODEL: str = Field(default=os.getenv("OLLAMA_MODEL", "gemma3:4b"), alias="OLLAMA_MODEL")
    OLLAMA_BASE_URL: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), alias="OLLAMA_BASE_URL")

    # ---- Rate limiting -----------------------------------------------------
    # Max requests per minute. Ollama is local so set it high (e.g. 60).
    # Gemini free-tier: 15 RPM. Set lower (e.g. 10) to leave headroom.
    LLM_RPM: int = Field(default=int(os.getenv("LLM_RPM", "10")), alias="LLM_RPM")

    # ---- Retrieval ---------------------------------------------------------
    # How many corpus chunks to return per user search query.
    TOP_K: int = 8

    # FAISS IVF-SQ8 clusters searched per query (out of 4096 total). 512 measured at 99%
    # recall@10 vs. exact search, ~120ms/query -- both keep rising past this with diminishing
    # returns, so this is the sweet spot rather than a floor.
    FAISS_NPROBE: int = 512

    # ---- Conflict detection tuning ----------------------------------------
    # How many clauses at most we analyse per draft (cost / latency guard).
    # Each unresolved clause->candidate pair costs one sequential local-LLM call
    # (~6-10s observed with gemma3:4b via Ollama on this machine), so this and
    # CANDIDATES_PER_CLAUSE together bound worst-case request latency: keep their
    # product small to stay under the 30s target. Measured 23.8s-28.7s at these
    # values on fresh (uncached) drafts.
    MAX_CLAUSES_ANALYSED: int = 2

    # SAFETY CEILING, not a coverage budget: every clause with at least one
    # retrieved candidate is LLM-eligible up to this many clauses per draft.
    # Previously a flat 2-clause cap regardless of draft size -- confirmed
    # (retrieval-observability validation, nutrition/health test draft) that
    # this silently excluded high-similarity candidates (0.89-0.93) in
    # Public Health / Rural Development clauses from ever reaching the LLM,
    # purely because they ranked below 2 other clauses in the same draft, not
    # because retrieval or the rule engine filtered them out.
    #
    # Set well above observed real-world clause counts (most recent 20
    # drafts: max 5, avg 3.35 -- see conflict_detection._extract_operative_clauses
    # output against the drafts table) so it is not a practical constraint for
    # any typical draft; a warning is logged if it's ever actually hit (see
    # detect_cross_department_conflicts), so an unusually large draft hitting
    # it is visible rather than silently reintroducing the same coverage gap.
    MAX_CLAUSES_FOR_LLM: int = 12

    # How many of the top-ranked retrieved candidates (out of
    # RULE_ENGINE_CANDIDATES_PER_CLAUSE) each LLM-eligible clause is verified
    # against. Raised from 2 to 3 -- both changes together increase worst-case
    # LLM-call volume per draft; see the latency remeasurement in
    # test_runs/ for the actual impact of this change.
    CANDIDATES_PER_CLAUSE: int = 3

    # How many corpus candidates the initial vector search fetches per clause.
    # Widened to 15 to give the cross-encoder reranker a meaningful pool to work over.
    # The reranker then selects the top CANDIDATES_PER_CLAUSE from this pool before
    # any rule-engine or LLM calls are made -- so LLM-call volume is still bounded
    # by CANDIDATES_PER_CLAUSE, not this number. Local FAISS/embedding cost only.
    RULE_ENGINE_CANDIDATES_PER_CLAUSE: int = 15

    # Cross-encoder model used to rerank the RULE_ENGINE_CANDIDATES_PER_CLAUSE pool.
    # BAAI/bge-reranker-v2-m3 is multilingual (handles English and Marathi) and
    # lightweight enough to run on CPU in <200ms for 15-20 candidates.
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"

    # Minimum confidence for a conflict to be included in the final report.
    CONFLICT_CONFIDENCE_FLOOR: float = 0.45

    # ---- Scanned GR upload / OCR ingestion ----------------------------------
    MAX_UPLOAD_SIZE_MB: int = 10

    # 0-100 scale (pytesseract's per-word/line confidence, averaged per block).
    # A block below this is flagged needs_review but still proceeds through
    # cleaning/clause-splitting/conflict detection -- this is a review flag,
    # not a gate. Tune after real-world testing; Marathi text may warrant a
    # separate/lower threshold if the false-flag rate is high in the first
    # week of use (Devanagari OCR is inherently noisier than Latin script).
    OCR_CONFIDENCE_THRESHOLD: int = 78

    # ---- Chunking ----------------------------------------------------------
    CHUNK_CHARS: int = 500
    CHUNK_OVERLAP: int = 100

    # ---- Local database (PostgreSQL) ----------------------------------------
    # asyncpg driver, used by the app at request time.
    DATABASE_URL: str = Field(
        default=os.getenv("DATABASE_URL", "postgresql+asyncpg://nirn_app:CHANGEME@localhost:5432/nirn_ai"),
        alias="DATABASE_URL",
    )
    # Sync driver (psycopg2-style URL, "+asyncpg" stripped in alembic/env.py),
    # used only by Alembic and only with superuser privileges for DDL.
    ALEMBIC_DATABASE_URL: str = Field(
        default=os.getenv("ALEMBIC_DATABASE_URL", "postgresql://postgres:CHANGEME@localhost:5432/nirn_ai"),
        alias="ALEMBIC_DATABASE_URL",
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5

    # ---- Auth / JWT ----------------------------------------------------------
    JWT_SECRET: str = Field(default=os.getenv("JWT_SECRET", "CHANGEME"), alias="JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 12  # 12 hours — a working shift
    LOGIN_RATE_LIMIT: str = "5/minute"

    # ---- Pagination ----------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ---- Department codes ----------------------------------------------------
    # Used to compose provisional GR numbers: NIRN/<CODE>/<YYYY>/<seq>.
    # Keys match the `value` field of the department <select> in
    # DraftInputCard.jsx exactly. Anything not listed falls back to 'GEN'.
    DEPARTMENT_CODES: dict = {
        "Agriculture,_Dairy_Development,_Animal_Husbandry_and_Fisheries_Department": "AHD",
        "Co-operation,_Textiles_and_Marketing_Department": "CTM",
        "Environment_Department": "ENV",
        "Finance_Department": "FIN",
        "Food,_Civil_Supplies_and_Consumer_Protection_Department": "FCS",
        "General_Administration_Department": "GAD",
        "Higher_and_Technical_Education_Department": "HTE",
        "Home_Department": "HD",
        "Housing_Department": "HSG",
        "Industries,_Energy_and_Labour_Department": "IEL",
        "Information_Technology_Department": "IT",
        "Law_and_Judiciary_Department": "LJD",
        "Marathi_Language_Department": "MLD",
        "Medical_Education_and_Drugs_Department": "MED",
        "Minorities_Development_Department": "MD",
        "Other_Backward_Bahujan_Welfare_Department": "OBW",
        "Parliamentary_Affairs_Department": "PAD",
        "Persons_with_Disabilities_Welfare_Department": "PWD",
        "Planning_Department": "PLN",
        "Public_Health_Department": "PHD",
        "Public_Works_Department": "PWK",
        "Revenue_and_Forest_Department": "RFD",
        "Rural_Development_Department": "RD",
        "Skill_Development_and_Entrepreneurship_Department": "SDE",
        "School_Education_and_Sports_Department": "SES",
        "Social_Justice_and_Special_Assistance_Department": "SJD",
        "Soil_and_Water_Conservation_Department": "SWC",
        "Tourism_and_Cultural_Affairs_Department": "TCA",
        "Tribal_Development_Department": "TD",
        "Urban_Development_Department": "UD",
        "Water_Resources_Department": "WR",
        "Water_Supply_and_Sanitation_Department": "WSS",
        "Women_and_Child_Development_Department": "WCD",
    }

    class Config:
        # Look for a .env file one level above backend/ (i.e. at the project root).
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        # Allow LLM_API_KEY to be set as GEMINI_API_KEY as well (common alias).
        populate_by_name = True
        extra = "ignore"


settings = Settings()
