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
