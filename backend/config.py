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
    
    # ---- Telemetry ---------------------------------------------------------
    # When enabled, injects X-NIRN-Metrics and X-Performance-Profile into HTTP responses
    ENABLE_TELEMETRY: bool = Field(default=True, alias="ENABLE_TELEMETRY")

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

    # ---- Conflict detection tuning ----------------------------------------
    # How many clauses at most we analyse per draft (cost / latency guard).
    MAX_CLAUSES_ANALYSED: int = 10

    # How many corpus candidates to retrieve per draft clause before the
    # model judges the relationships.
    CANDIDATES_PER_CLAUSE: int = 5

    # Minimum confidence for a conflict to be included in the final report.
    CONFLICT_CONFIDENCE_FLOOR: float = 0.60

    # Confidence bands for the semantic-first pipeline
    CONFIDENCE_AUTO: float = 0.85       # >= this: auto-confirmed conflict
    CONFIDENCE_REVIEW: float = 0.60     # >= this: needs officer review
    # < CONFIDENCE_REVIEW: discarded

    # Experimental feature flag for unified conflict detection (legacy, unused)
    USE_UNIFIED_CONFLICT_PROMPT: bool = False

    # ---- Chunking ----------------------------------------------------------
    CHUNK_CHARS: int = 500
    CHUNK_OVERLAP: int = 100

    # ---- Postgres (SQLAlchemy async) ---------------------------------------
    DATABASE_URL: str = Field(
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://nirn_app:CHANGEME@localhost:5432/nirn_ai",
        ),
        alias="DATABASE_URL",
    )

    # ---- Auth ----------------------------------------------------------------
    JWT_SECRET: str = Field(default=os.getenv("JWT_SECRET", "CHANGEME"), alias="JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 12

    class Config:
        # Look for a .env file one level above backend/ (i.e. at the project root).
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        # Allow LLM_API_KEY to be set as GEMINI_API_KEY as well (common alias).
        populate_by_name = True
        extra = "ignore"


settings = Settings()


# ---- Department short codes ------------------------------------------------
# Used to build provisional GR numbers (NIRN/<CODE>/<YYYY>/<seq>) — see
# db/repositories/gr_numbers.py. Keys match the `value` strings sent by the
# department dropdown in frontend/src/components/drafting/DraftInputCard.jsx
# exactly (underscored department names), one entry per department listed
# there. DEFAULT_DEPARTMENT_CODE covers anything unexpected instead of
# crashing draft creation over a cosmetic reference number.
DEFAULT_DEPARTMENT_CODE = "GEN"

DEPARTMENT_CODES: dict[str, str] = {
    "Agriculture,_Dairy_Development,_Animal_Husbandry_and_Fisheries_Department": "AGRI",
    "Co-operation,_Textiles_and_Marketing_Department": "COOP",
    "Environment_Department": "ENV",
    "Finance_Department": "FIN",
    "Food,_Civil_Supplies_and_Consumer_Protection_Department": "FCS",
    "General_Administration_Department": "GAD",
    "Higher_and_Technical_Education_Department": "HTE",
    "Home_Department": "HOME",
    "Housing_Department": "HSG",
    "Industries,_Energy_and_Labour_Department": "IEL",
    "Information_Technology_Department": "IT",
    "Law_and_Judiciary_Department": "LAW",
    "Marathi_Language_Department": "MLD",
    "Medical_Education_and_Drugs_Department": "MED",
    "Minorities_Development_Department": "MIN",
    "Other_Backward_Bahujan_Welfare_Department": "OBC",
    "Parliamentary_Affairs_Department": "PAD",
    "Persons_with_Disabilities_Welfare_Department": "DIS",
    "Planning_Department": "PLAN",
    "Public_Health_Department": "PH",
    "Public_Works_Department": "PWD",
    "Revenue_and_Forest_Department": "REV",
    "Rural_Development_Department": "RD",
    "Skill_Development_and_Entrepreneurship_Department": "SDE",
    "School_Education_and_Sports_Department": "SES",
    "Social_Justice_and_Special_Assistance_Department": "SJSA",
    "Soil_and_Water_Conservation_Department": "SWC",
    "Tourism_and_Cultural_Affairs_Department": "TCA",
    "Tribal_Development_Department": "TD",
    "Urban_Development_Department": "UD",
    "Water_Resources_Department": "WR",
    "Water_Supply_and_Sanitation_Department": "WSS",
    "Women_and_Child_Development_Department": "WCD",
}


def department_code(department: str) -> str:
    return DEPARTMENT_CODES.get(department, DEFAULT_DEPARTMENT_CODE)


# ---- Upload / document extraction ------------------------------------------
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB, enforced in routes.py
OCR_LANGUAGES = "mar+eng"
OCR_LOW_CONFIDENCE_THRESHOLD = 70.0
