"""
llm.py — every call to the language model lives here and nowhere else.

Keeping all model code in one file means swapping Gemini for Claude is
a one-function change instead of a search across the codebase.

Rate-limit strategy (in order of priority):
  1. Response cache    — identical (system, user) pairs never hit the API twice.
  2. Token-bucket      — at most LLM_RPM requests per minute are sent.
  3. Exponential retry — on 429 / 503 the call is retried up to 3 times with
                         jittered back-off before falling back to mock.
"""

import hashlib
import json
import logging
import os
import re
import time
import threading
from collections import OrderedDict
from typing import List, Optional

from dotenv import load_dotenv

# Resolve .env from the project root (one level above backend/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path, override=True)

import httpx
import prompts
from config import settings
from schemas import Language, TermMapping

logger = logging.getLogger(__name__)


# =====================================================================
# Clause splitting — rule-based on purpose
# =====================================================================

def split_into_clauses(text: str) -> List[str]:
    """
    Break a draft into its operative clauses.

    Supports both Arabic numerals (1., 2.) and Devanagari numerals (०१., १., २.)
    so that Marathi GRs drafted with the official numbering are correctly split
    into individual clauses for conflict detection.
    """
    # Match:
    #   \d+[.)]           — Arabic: 1. 2. 1) 2)
    #   [\u0966-\u096F]+[.)] — Devanagari: १. ०१. ०२.
    parts = re.split(
        r"\n\s*(?=(?:\d+|[\u0966-\u096F]+)[.)]\s)",
        text,
    )
    clauses = [part.strip() for part in parts if len(part.strip()) > 40]
    return clauses or [text.strip()]


# =====================================================================
# LRU response cache
# =====================================================================

class _LRUCache:
    """
    Thread-safe LRU cache for LLM responses.
    Keyed on provider + SHA-256 of (system_prompt, user_message) so different providers
    and mock fallbacks never collide or pollute the cache.
    """

    def __init__(self, maxsize: int = 128):
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def _key(self, provider: str, system_prompt: str, user_message: str) -> str:
        raw = f"{provider}\x00{system_prompt}\x00{user_message}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, provider: str, system_prompt: str, user_message: str) -> Optional[str]:
        k = self._key(provider, system_prompt, user_message)
        with self._lock:
            if k in self._cache:
                self._cache.move_to_end(k)
                logger.debug("LLM cache hit for provider %s", provider)
                return self._cache[k]
        return None

    def set(self, provider: str, system_prompt: str, user_message: str, value: str) -> None:
        k = self._key(provider, system_prompt, user_message)
        with self._lock:
            self._cache[k] = value
            self._cache.move_to_end(k)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


_cache = _LRUCache(maxsize=128)


# =====================================================================
# Token-bucket rate limiter
# =====================================================================

class _TokenBucket:
    """
    Classic token-bucket that limits the number of API requests per minute.
    Blocks (sleeps) the calling thread until a token is available.
    """

    def __init__(self, rpm: int):
        self._capacity = rpm
        self._tokens = float(rpm)
        self._refill_rate = rpm / 60.0   # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._capacity,
                self._tokens + elapsed * self._refill_rate,
            )
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / self._refill_rate
                logger.debug("Rate-limit bucket: sleeping %.2fs", wait)
            else:
                wait = 0.0

            self._tokens -= 1

        if wait > 0:
            time.sleep(wait)


# Default: 10 RPM — conservative for free-tier Gemini Flash
_LLM_RPM = int(os.getenv("LLM_RPM", "10"))
_bucket = _TokenBucket(rpm=_LLM_RPM)


# =====================================================================
# Mock responses (fallback when API is unavailable)
# =====================================================================

def get_mock_response(system_prompt: str, user_message: str) -> str:
    """Fallback generator for local demo when API key is missing or calls fail."""
    # Ordered by how specific/unique the marker phrase is to its source prompt in prompts.py /
    # llm_verifier.py — a bare word like "terminology" or "conflict" also appears incidentally in
    # COPILOT_DRAFT's style-guidance bullets ("...terminology context", never mentions conflict),
    # so generic single-word checks can misclassify a drafting call as a terminology call. Checking
    # the most distinctive phrase from each prompt first avoids that collision.
    system_prompt_lower = system_prompt.lower()

    if "expert drafting officer" in system_prompt_lower:
        return (
            "शासन निर्णय: उच्च व तंत्र शिक्षण विभागांतर्गत येणाऱ्या शासकीय व अनुदानित महाविद्यालयांमधील "
            "मंजूर प्रवेश क्षमता (Sanctioned Intake) शैक्षणिक वर्ष २०२६-२७ पासून सुधारित करण्यात येत आहे."
        )
    elif "legal policy checker" in system_prompt_lower or "conflict" in system_prompt_lower:
        # Schema must match llm_verifier.py's parser (conflict/category/severity/confidence/
        # evidence/reason/recommendation) -- an older shape here silently produced zero conflicts
        # on every fallback, since verify_conflict_with_llm() reads parsed.get("conflict", False)
        # and a missing key defaults to False, indistinguishable from a genuine "no conflict".
        return json.dumps({
            "conflict": True,
            "category": "Funding Conflict",
            "severity": "High",
            "confidence": 0.7,
            "evidence": "Mock fallback response — the local LLM was unreachable, so this candidate "
                        "could not be genuinely verified. Treat as needing manual review, not a "
                        "confirmed conflict.",
            "reason": "LLM verification unavailable (Ollama unreachable) — falling back to a "
                      "placeholder so the candidate is surfaced for manual review instead of being "
                      "silently dropped.",
            "recommendation": "Retry analysis once the local LLM (Ollama) is reachable.",
        })
    elif "terminology" in system_prompt_lower:
        return json.dumps([
            {
                "source_term": "sanctioned intake",
                "source_language": "en",
                "target_term": "मंजूर प्रवेश क्षमता",
                "consistent_with_corpus": True,
                "note": "Standard administrative translation in Maharashtra GRs.",
            }
        ])
    elif "json" in system_prompt_lower and "answer" in system_prompt_lower:
        # Combined chat+suggestions mock
        return json.dumps({
            "answer": "हा उच्च व तंत्र शिक्षण विभागाचा अधिकृत शासन निर्णय आहे. या नियमानुसार मंजूर प्रवेश क्षमता निश्चित करण्यात आली आहे.",
            "suggestions": [
                "What are the eligibility criteria?",
                "Show me related resolutions.",
                "Summarize the rules.",
            ],
        })
    else:
        return "हा उच्च व तंत्र शिक्षण विभागाचा अधिकृत शासन निर्णय आहे. या नियमानुसार मंजूर प्रवेश क्षमता निश्चित करण्यात आली आहे."


# =====================================================================
# Core model call with cache + rate-limit + retry
# =====================================================================

_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0   # seconds; doubles each retry


def _call_ollama(system_prompt: str, user_message: str, response_schema: Optional[dict] = None) -> tuple[str, bool]:
    """
    Send a request to a locally running Ollama instance.
    Returns (text_response, is_real_llm_response).

    response_schema, when given, is passed as Ollama's structured-output `format` (a JSON
    Schema) instead of the bare "json" string -- this constrains generation to match the
    schema's shape (e.g. an array of exactly N objects), which plain prompt instructions alone
    are not reliable enough to guarantee on a small local model.
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    need_json = "json" in system_prompt.lower() and "drafting officer" not in system_prompt.lower()
    payload: dict = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": False,
    }
    if response_schema is not None:
        payload["format"] = response_schema
    elif need_json:
        payload["format"] = "json"

    # Ollama has been observed to drop connections transiently (e.g. while the desktop app is
    # still finishing its own startup, or momentarily busy loading the model into memory) even
    # though it is genuinely running and recovers within a couple of seconds. A single retry
    # avoids treating that transient window as "Ollama isn't installed" and silently falling back
    # to the mock response for what would otherwise have been a real answer a moment later.
    _OLLAMA_RETRIES = 2
    _OLLAMA_RETRY_DELAY = 1.5

    last_exc: Optional[Exception] = None
    for attempt in range(_OLLAMA_RETRIES + 1):
        try:
            response = httpx.post(url, json=payload, timeout=120.0)  # local can be slow on first token
            response.raise_for_status()
            text = response.json()["message"]["content"]
            return text, True
        except httpx.ConnectError as exc:
            last_exc = exc
            if attempt < _OLLAMA_RETRIES:
                logger.warning(
                    "Cannot connect to Ollama at %s (attempt %d/%d) — retrying in %.1fs",
                    settings.OLLAMA_BASE_URL, attempt + 1, _OLLAMA_RETRIES + 1, _OLLAMA_RETRY_DELAY,
                )
                time.sleep(_OLLAMA_RETRY_DELAY)
                continue
        except Exception as exc:
            last_exc = exc
            break

    logger.error(
        "Cannot connect to Ollama at %s after %d attempt(s) — is it running? "
        "Start it with: ollama serve (error: %s)",
        settings.OLLAMA_BASE_URL, _OLLAMA_RETRIES + 1, last_exc,
    )
    return get_mock_response(system_prompt, user_message), False


# Regex matching CJK / Chinese / Japanese / Korean / Cyrillic scripts
_FOREIGN_SCRIPT_PATTERN = re.compile(
    r'[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF\u0400-\u04FF\u0500-\u052F\u2C00-\u2C5F\uA640-\uA69F]+'
)


def sanitize_llm_text(text: str) -> str:
    """
    Ensure only English (Latin), Marathi (Devanagari), and standard legal punctuation
    are allowed in LLM generated responses. Completely strips Chinese, CJK, and Cyrillic noise.
    """
    if not text or not isinstance(text, str):
        return ""
    # Strip Chinese / CJK / Cyrillic characters
    cleaned = _FOREIGN_SCRIPT_PATTERN.sub("", text)
    # Strip markdown bold asterisks
    cleaned = cleaned.replace("**", "")
    return cleaned


def call_model(system_prompt: str, user_message: str, response_schema: Optional[dict] = None) -> str:
    raw = _call_model_raw(system_prompt, user_message, response_schema)
    if raw:
        return sanitize_llm_text(raw)
    return raw



def _call_model_raw(system_prompt: str, user_message: str, response_schema: Optional[dict] = None) -> str:
    """
    Send one request to the active LLM provider and return its raw text reply.

    Provider routing (set LLM_PROVIDER in .env):
      "ollama"  → local Ollama instance, no API key needed, no rate limit
      "gemini"  → Google AI Studio with cache + rate-limit + exponential retry
    """
    provider = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER).lower()

    # ------------------------------------------------------------------ Ollama
    if provider == "ollama":
        cached = _cache.get(provider, system_prompt, user_message)
        if cached is not None:
            return cached
        text, is_real = _call_ollama(system_prompt, user_message, response_schema)
        if is_real:
            _cache.set(provider, system_prompt, user_message, text)
        return text

    # ------------------------------------------------------------------ Gemini
    api_key = os.getenv("LLM_API_KEY") or settings.LLM_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return get_mock_response(system_prompt, user_message)

    # 1. Cache lookup — skip network entirely if we have a cached answer
    cached = _cache.get(provider, system_prompt, user_message)
    if cached is not None:
        return cached

    # 2. Rate-limit — block until the token bucket allows
    _bucket.acquire()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.LLM_MODEL}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    payload: dict = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    if "json" in system_prompt.lower() and "drafting officer" not in system_prompt.lower():
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    # 3. HTTP call with exponential backoff on retryable errors
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=45.0)

            if response.status_code in _RETRYABLE_CODES:
                backoff = _BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini API %d on attempt %d/%d — retrying in %.1fs",
                    response.status_code, attempt + 1, _MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
                # Re-acquire token after backoff
                _bucket.acquire()
                continue

            response.raise_for_status()
            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]

            # 4. Store in cache before returning
            _cache.set(provider, system_prompt, user_message, text)
            return text

        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code in _RETRYABLE_CODES:
                backoff = _BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini HTTP %d on attempt %d/%d — retrying in %.1fs",
                    exc.response.status_code, attempt + 1, _MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
                _bucket.acquire()
            else:
                break   # Non-retryable HTTP error — give up immediately
        except Exception as exc:
            last_exc = exc
            break       # Network error, JSON parse error, etc.

    logger.error("Gemini call failed after %d attempt(s): %s — using mock.", _MAX_RETRIES, last_exc)
    return get_mock_response(system_prompt, user_message)


# =====================================================================
# JSON reply parser
# =====================================================================

def parse_json_reply(raw: str) -> Optional[dict | list]:
    """
    Parse JSON out of a model reply.

    Models wrap JSON in ```json fences roughly a third of the time even
    when told not to. Stripping them here saves you debugging a JSONDecodeError.
    """
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"[\{\[].*[\}\]]", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# =====================================================================
# Objective 2 — bilingual terminology
# =====================================================================

def map_terminology(text: str, language: Language) -> List[TermMapping]:
    """
    Extract legal terms and map them to their approved equivalents using the KnowledgeService.
    """
    from knowledge import get_knowledge_service
    ks = get_knowledge_service()
    kb_terms = ks.get_all_glossary_terms()

    # Dynamically build authoritative glossary dict from Knowledge Base
    glossary = {
        t["english"]: t["marathi"]
        for t in kb_terms
        if t.get("english") and t.get("marathi")
    }

    system_prompt = prompts.TERMINOLOGY_MAPPING
    user_msg = prompts.build_terminology_message(text, glossary)

    raw_reply = call_model(system_prompt, user_msg)
    parsed = parse_json_reply(raw_reply)

    results = []
    if parsed and isinstance(parsed, list):
        for item in parsed:
            try:
                src_term = item.get("source_term", "")
                src_lang = Language(item.get("source_language", "en"))
                tgt_term = item.get("target_term", "")
                note_str = item.get("note", "")

                en_t = src_term if src_lang == Language.ENGLISH else tgt_term
                mr_t = tgt_term if src_lang == Language.ENGLISH else src_term

                results.append(
                    TermMapping(
                        source_term=src_term,
                        source_language=src_lang,
                        target_term=tgt_term,
                        consistent_with_corpus=bool(item.get("consistent_with_corpus", True)),
                        note=note_str,
                        english_term=en_t,
                        marathi_term=mr_t,
                        definition=note_str,
                    )
                )
            except Exception as exc:
                logger.warning("Error parsing term item: %s", exc)

    if not results:
        # Fallback to direct Knowledge Base lookup across the full corpus glossary
        text_lower = text.lower()
        for term in kb_terms:
            en_term = term.get("english", "")
            mr_term = term.get("marathi", "")

            if en_term and en_term.lower() in text_lower:
                idx = text_lower.find(en_term.lower())
                exact_doc_term = text[idx:idx + len(en_term)]
                results.append(
                    TermMapping(
                        source_term=exact_doc_term,
                        source_language=Language.ENGLISH,
                        target_term=mr_term,
                        consistent_with_corpus=True,
                        note="Verified from Government Knowledge Base.",
                        english_term=en_term,
                        marathi_term=mr_term,
                        definition="Verified from Government Knowledge Base.",
                    )
                )
            elif mr_term and mr_term in text:
                idx = text.find(mr_term)
                exact_doc_term = text[idx:idx + len(mr_term)]
                results.append(
                    TermMapping(
                        source_term=exact_doc_term,
                        source_language=Language.MARATHI,
                        target_term=en_term,
                        consistent_with_corpus=True,
                        note="Verified from Government Knowledge Base.",
                        english_term=en_term,
                        marathi_term=mr_term,
                        definition="Verified from Government Knowledge Base.",
                    )
                )
    return results





# =====================================================================
# Health check
# =====================================================================

def is_configured() -> bool:
    """Whether the active LLM provider is ready. Surfaced on /health."""
    provider = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER).lower()
    if provider == "ollama":
        return True   # Ollama needs no API key — just needs to be running
    api_key = os.getenv("LLM_API_KEY") or settings.LLM_API_KEY
    return bool(api_key) and api_key != "your-api-key-here"
