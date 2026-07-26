"""
config.py — central configuration for NIRN.Ai backend.

Every value that might vary between local development and the production
demo environment lives here.  Other modules import `settings` and read
from it; nothing should hard-code a port, key, or threshold directly.

Reads from environment variables / a .env file so the API key is never
committed to the repo.  Add a .env file in the project root:

    LLM_API_KEY=AIza...your-key...
    DEBUG=true

Then activate the venv and run:

    cd backend
    uvicorn app:app --reload
"""

import os
from typing import List

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

    # ---- LLM ---------------------------------------------------------------
    # Gemini model to use for generation.
    LLM_API_KEY: str = Field(default="your-api-key-here", alias="LLM_API_KEY")
    LLM_MODEL: str = "gemini-2.0-flash"

    # ---- Retrieval ---------------------------------------------------------
    # How many corpus chunks to return per user search query.
    TOP_K: int = 8

    # ---- Conflict detection tuning ----------------------------------------
    # How many clauses at most we analyse per draft (cost / latency guard).
    MAX_CLAUSES_ANALYSED: int = 10

    # How many corpus candidates to retrieve per draft clause before the
    # model judges the relationships.
    CANDIDATES_PER_CLAUSE: int = 4

    # Minimum confidence for a conflict to be included in the final report.
    CONFLICT_CONFIDENCE_FLOOR: float = 0.45

    # ---- Chunking ----------------------------------------------------------
    CHUNK_CHARS: int = 500
    CHUNK_OVERLAP: int = 100

    class Config:
        # Look for a .env file one level above backend/ (i.e. at the project root).
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        # Allow LLM_API_KEY to be set as GEMINI_API_KEY as well (common alias).
        populate_by_name = True
        extra = "ignore"


settings = Settings()
