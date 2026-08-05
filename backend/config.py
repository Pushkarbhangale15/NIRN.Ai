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

    # How many of the leading clauses are eligible for LLM verification.
    # The deterministic rule engine now runs over every extracted clause
    # (cheap, local, no LLM call); this constant keeps the LLM-call volume
    # identical to the previous MAX_CLAUSES_ANALYSED behaviour.
    MAX_CLAUSES_FOR_LLM: int = 2

    # How many corpus candidates to retrieve per draft clause before the
    # model judges the relationships. This bounds LLM-call volume -- unchanged.
    CANDIDATES_PER_CLAUSE: int = 2

    # How many corpus candidates the (free, local, no-LLM) deterministic rule engine gets
    # to inspect per clause. Wider than CANDIDATES_PER_CLAUSE on purpose: only the top
    # CANDIDATES_PER_CLAUSE of this same pool (already score-sorted by retrieval.search)
    # are ever passed to the LLM stage, so widening this has zero effect on LLM-call volume
    # -- it only gives the rule engine more chances to find a deterministic match before
    # falling through to (or past) the LLM budget. Local FAISS/embedding cost only.
    RULE_ENGINE_CANDIDATES_PER_CLAUSE: int = 6

    # Minimum confidence for a conflict to be included in the final report.
    CONFLICT_CONFIDENCE_FLOOR: float = 0.45

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
