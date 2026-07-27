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
from schemas import ConflictHit, CorpusHit, Language, Relation, TermMapping

logger = logging.getLogger(__name__)


# =====================================================================
# Clause splitting — rule-based on purpose
# =====================================================================

def split_into_clauses(text: str) -> List[str]:
    """
    Break a draft into its operative clauses.

    Deliberately rule-based. A language model here would be slower,
    cost money per call, and give a different answer each time — none
    of which you want in a step that runs before every analysis.
    """
    parts = re.split(r"\n\s*(?=\d+[.)]\s)", text)
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
    system_prompt_lower = system_prompt.lower()

    if "conflict" in system_prompt_lower:
        return json.dumps([
            {
                "candidate_idx": 0,
                "relation": "overlap",
                "confidence": 0.78,
                "justification": "Both clauses discuss the criteria for lateral entry and administrative sanctioning.",
            }
        ])
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
    elif "drafting" in system_prompt_lower or "draft" in system_prompt_lower:
        return (
            "शासन निर्णय: उच्च व तंत्र शिक्षण विभागांतर्गत येणाऱ्या शासकीय व अनुदानित महाविद्यालयांमधील "
            "मंजूर प्रवेश क्षमता (Sanctioned Intake) शैक्षणिक वर्ष २०२६-२७ पासून सुधारित करण्यात येत आहे."
        )
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


def _call_ollama(system_prompt: str, user_message: str) -> tuple[str, bool]:
    """
    Send a request to a locally running Ollama instance.
    Returns (text_response, is_real_llm_response).
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
    if need_json:
        payload["format"] = "json"

    try:
        response = httpx.post(url, json=payload, timeout=120.0)  # local can be slow on first token
        response.raise_for_status()
        text = response.json()["message"]["content"]
        return text, True
    except httpx.ConnectError:
        logger.error(
            "Cannot connect to Ollama at %s — is it running? "
            "Start it with: ollama serve", settings.OLLAMA_BASE_URL
        )
        return get_mock_response(system_prompt, user_message), False
    except Exception as exc:
        logger.error("Ollama call failed: %s — using mock.", exc)
        return get_mock_response(system_prompt, user_message), False


def call_model(system_prompt: str, user_message: str) -> str:
    raw = _call_model_raw(system_prompt, user_message)
    if raw:
        return raw.replace("**", "")
    return raw


def _call_model_raw(system_prompt: str, user_message: str) -> str:
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
        text, is_real = _call_ollama(system_prompt, user_message)
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
# Objective 1 — conflict detection
# =====================================================================

_SNIPPET_MAX = 400   # chars sent per candidate to the API (saves tokens)


def detect_conflicts(
    draft_clauses: List[str],
    candidates: List[CorpusHit],
) -> List[ConflictHit]:
    """
    For each draft clause, send ONE batched call covering all its candidates.
    Batched per draft clause to reduce calls from O(N×M) to O(N).
    Snippets are capped at _SNIPPET_MAX chars to reduce token usage.
    """
    if not draft_clauses or not candidates:
        return []

    results = []
    candidates_per_clause = settings.CANDIDATES_PER_CLAUSE

    system_prompt = (
        "You are a policy analyst for the Government of Maharashtra.\n"
        "Compare the DRAFT CLAUSE against each of the numbered CANDIDATES.\n"
        "For each candidate, classify the relationship as exactly one of:\n"
        "- conflict   : the two clauses cannot both be complied with\n"
        "- overlap    : same subject matter, but no contradiction\n"
        "- supersedes : the draft clause replaces the existing one\n"
        "- unrelated  : different subject matter\n\n"
        "If there is a conflict/contradiction/mismatch, you MUST classify it into exactly one of these 42 conflict types:\n"
        "Authority Conflict, Department Responsibility Conflict, Funding Conflict, Budget Allocation Conflict, "
        "Budget Head Conflict, Fund Utilization Conflict, Fund Diversion Conflict, Administrative Approval Conflict, "
        "Technical Approval Conflict, Operational Conflict, Implementation Agency Conflict, Implementation Procedure Conflict, "
        "Tendering Procedure Conflict, Procurement Conflict, Policy Conflict, Legal Conflict, Legal Reference Conflict, "
        "Regulatory Conflict, Timeline Conflict, Monitoring & Reporting Conflict, Committee Structure Conflict, "
        "Governance Conflict, Jurisdiction Conflict, Responsibility Assignment Conflict, Financial Compliance Conflict, "
        "Expenditure Rule Conflict, Payment Authority Conflict, Quality Assurance Conflict, Inspection Procedure Conflict, "
        "Land Acquisition Conflict, Encroachment Procedure Conflict, Environmental Policy Conflict, Infrastructure Scope Conflict, "
        "Digital Compliance Conflict, Documentation Conflict, Terminology Conflict, Reference Conflict, Eligibility Criteria Conflict, "
        "Priority Conflict, Resource Allocation Conflict, Approval Hierarchy Conflict, Compliance Conflict.\n\n"
        "Also assign a severity: 'Low', 'Medium', 'High', or 'Critical'.\n\n"
        "Return ONLY a JSON array of objects, no markdown fences, no preamble:\n"
        '[{"candidate_idx": 0, "relation": "...", "conflict_type": "...", "severity": "...", "confidence": 0.0-1.0, '
        '"justification": "detailed explanation of the contradiction and what text is clashing"}]'
    )

    for clause_idx, clause in enumerate(draft_clauses[: settings.MAX_CLAUSES_ANALYSED]):
        start_idx = clause_idx * candidates_per_clause
        clause_candidates = candidates[start_idx : start_idx + candidates_per_clause]
        if not clause_candidates:
            continue

        user_msg = f"DRAFT CLAUSE:\n{clause[:500]}\n\nEXISTING CLAUSES TO COMPARE:\n"
        for idx, hit in enumerate(clause_candidates):
            snippet = hit.snippet[:_SNIPPET_MAX]
            user_msg += (
                f"--- CANDIDATE {idx} (ID: {hit.gr_id}, Dept: {hit.department}) ---\n"
                f"{snippet}\n\n"
            )

        raw_reply = call_model(system_prompt, user_msg)
        parsed = parse_json_reply(raw_reply)
        if not parsed or not isinstance(parsed, list):
            continue

        for item in parsed:
            try:
                c_idx = int(item.get("candidate_idx", -1))
                if 0 <= c_idx < len(clause_candidates):
                    hit = clause_candidates[c_idx]
                    relation_str = item.get("relation", "unrelated")
                    if relation_str == "unrelated":
                        continue
                    results.append(
                        ConflictHit(
                            draft_clause=clause[:350],
                            existing_gr_id=hit.gr_id,
                            existing_gr_title=hit.title,
                            existing_department=hit.department,
                            existing_clause=hit.snippet,
                            relation=Relation(relation_str),
                            confidence=float(item.get("confidence", 0.5)),
                            justification=item.get("justification", "Analyzed by AI."),
                            source_url=hit.source_url,
                            conflict_type=item.get("conflict_type", "Policy Conflict"),
                            severity=item.get("severity", "High"),
                        )
                    )
            except Exception as exc:
                logger.warning("Error parsing conflict item: %s", exc)

    return results


# =====================================================================
# Objective 2 — bilingual terminology
# =====================================================================

def map_terminology(text: str, language: Language) -> List[TermMapping]:
    """
    Extract legal terms and map them to their approved equivalents.
    """
    system_prompt = prompts.TERMINOLOGY_MAPPING
    glossary = {
        "sanctioned intake": "मंजूर प्रवेश क्षमता",
        "probation period": "परिविक्षाधीन कालावधी",
        "departmental inquiry": "विभागीय चौकशी",
        "administrative approval": "प्रशासकीय मान्यता",
        "financial sanction": "वित्तीय मंजुरी",
    }
    user_msg = prompts.build_terminology_message(text, glossary)

    raw_reply = call_model(system_prompt, user_msg)
    parsed = parse_json_reply(raw_reply)

    results = []
    if parsed and isinstance(parsed, list):
        for item in parsed:
            try:
                results.append(
                    TermMapping(
                        source_term=item.get("source_term", ""),
                        source_language=Language(item.get("source_language", "en")),
                        target_term=item.get("target_term", ""),
                        consistent_with_corpus=bool(item.get("consistent_with_corpus", True)),
                        note=item.get("note", ""),
                    )
                )
            except Exception as exc:
                logger.warning("Error parsing term item: %s", exc)

    if not results:
        for en_term, mr_term in glossary.items():
            if en_term in text.lower():
                results.append(
                    TermMapping(
                        source_term=en_term,
                        source_language=Language.ENGLISH,
                        target_term=mr_term,
                        consistent_with_corpus=True,
                        note="Verified from standard corpus glossary.",
                    )
                )
    return results


# =====================================================================
# Combined chat call — answer + suggestions in ONE API round-trip
# =====================================================================

def call_chat(
    system_prompt: str,
    user_message: str,
    fallback_suggestions: Optional[List[str]] = None,
) -> tuple[str, List[str]]:
    """
    Ask the model to return both the answer and follow-up suggestions in
    a single JSON response, cutting chat LLM calls from 3 → 1.

    Returns (answer_text, suggestions_list).
    """
    combined_system = (
        system_prompt
        + "\n\nReturn your final response strictly as a JSON object with two keys:\n"
        '{"answer": "<your full detailed response text>", '
        '"suggestions": ["short follow-up question 1", "short follow-up question 2", "short follow-up question 3"]}\n'
        "Output ONLY the JSON object with no preamble."
    )

    raw = call_model(combined_system, user_message)

    # 1. Direct JSON parse (works when model returns pure JSON or format: json is set)
    parsed = parse_json_reply(raw)
    if isinstance(parsed, dict):
        answer = parsed.get("answer")
        suggestions = parsed.get("suggestions", [])
        if answer and isinstance(answer, str) and len(answer.strip()) > 5:
            valid_sug = [str(s) for s in suggestions if isinstance(s, str)] if isinstance(suggestions, list) else []
            if not valid_sug:
                valid_sug = fallback_suggestions or [
                    "What are the implications?",
                    "Show me related resolutions.",
                    "Summarize the rules.",
                ]
            return answer.strip(), valid_sug[:3]

    # 2. Fallback: use raw text if JSON parsing failed
    _default = fallback_suggestions or [
        "What are the implications?",
        "Show me related resolutions.",
        "Summarize the rules.",
    ]
    return raw, _default


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
