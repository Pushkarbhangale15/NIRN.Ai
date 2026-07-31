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
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Resolve .env from the project root (one level above backend/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path, override=True)

import httpx
import prompts
from config import settings
from schemas import ConflictHit, CorpusHit, Language, Relation, TermMapping

logger = logging.getLogger(__name__)
from profiler import perf

# =====================================================================
# Module-level constants — read once at import time, never per-call
# =====================================================================

# Provider and API key: cached so every call_model() invocation avoids
# repeated os.getenv() lookups and dict hashing.
_LLM_PROVIDER: str = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER).lower()
_LLM_API_KEY: str = os.getenv("LLM_API_KEY") or settings.LLM_API_KEY


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
# Persistent HTTP client for Ollama
# =====================================================================

# A single httpx.Client is reused for every Ollama request in this
# process.  Creating a new client per call (as httpx.post() does
# internally) pays TCP + TLS setup cost 40+ times per drafting request.
# Timeout matches the previous per-call value of 120 s.
_ollama_client = httpx.Client(timeout=120.0)


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

    def acquire(self, local: bool = False) -> None:
        """Acquire one token from the bucket.

        When *local* is True (i.e. the request is going to a locally
        running Ollama instance) the bucket is bypassed entirely — a
        local HTTP server has no external rate-limit, so sleeping here
        only wastes wall-clock time (up to 186 s for a 40-call request
        at the default 10 RPM setting).
        """
        if local:
            return  # no sleep for local Ollama

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


def _call_ollama(system_prompt: str, user_message: str, purpose: str) -> tuple[str, bool]:
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
        # Reuse the module-level persistent client — avoids TCP/TLS
        # setup overhead on every one of the 40+ sequential calls that
        # a single drafting request can make.
        with perf("Ollama HTTP Roundtrip"):
            response = _ollama_client.post(url, json=payload)
            response.raise_for_status()
            
        with perf("Response Parsing"):
            d = response.json()
            text = d["message"]["content"]
            
        try:
            p_eval_dur = d.get("prompt_eval_duration", 0)
            eval_dur = d.get("eval_duration", 0)
            p_eval_cnt = d.get("prompt_eval_count", 0)
            eval_cnt = d.get("eval_count", 0)
            
            p_tps = round(p_eval_cnt / (p_eval_dur / 1e9), 1) if p_eval_dur > 0 else 0
            e_tps = round(eval_cnt / (eval_dur / 1e9), 1) if eval_dur > 0 else 0

            perf.current_meta(
                model=d.get("model", settings.OLLAMA_MODEL),
                purpose=purpose,
                prompt_tokens=p_eval_cnt,
                generated_tokens=eval_cnt,
                load_duration=f"{d.get('load_duration', 0) / 1e9:.3f}s",
                prompt_eval_duration=f"{p_eval_dur / 1e9:.3f}s",
                decode_duration=f"{eval_dur / 1e9:.3f}s",
                total_duration=f"{d.get('total_duration', 0) / 1e9:.3f}s",
                prefill_tps=p_tps,
                decode_tps=e_tps
            )
        except Exception:
            pass

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


def call_model(system_prompt: str, user_message: str, purpose: str) -> str:
    raw = _call_model_raw(system_prompt, user_message, purpose)
    if raw:
        return sanitize_llm_text(raw)
    return raw


def _is_api_key_valid(key: str) -> bool:
    """Return True if the API key looks like a real key."""
    return bool(key) and key != "your-api-key-here"



def _call_model_raw(system_prompt: str, user_message: str, purpose: str) -> str:
    """
    Send one request to the active LLM provider and return its raw text reply.

    Provider routing (set LLM_PROVIDER in .env):
      "ollama"  → local Ollama instance, no API key needed, no rate limit
      "gemini"  → Google AI Studio with cache + rate-limit + exponential retry

    _LLM_PROVIDER / _LLM_API_KEY are module-level constants read once at import
    time — os.getenv() is not called on every model call.
    """
    provider = _LLM_PROVIDER

    # ------------------------------------------------------------------ Ollama
    if provider == "ollama":
        cached = _cache.get(provider, system_prompt, user_message)
        if cached is not None:
            return cached
        # Acquire a bucket token — but Ollama is local so skip sleeping.
        _bucket.acquire(local=True)
        text, is_real = _call_ollama(system_prompt, user_message, purpose)
        if is_real:
            _cache.set(provider, system_prompt, user_message, text)
        return text

    # ------------------------------------------------------------------ Gemini
    api_key = _LLM_API_KEY
    if not _is_api_key_valid(api_key):
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
                # Re-acquire token after backoff (Gemini only — local=False)
                _bucket.acquire(local=False)
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
                _bucket.acquire(local=False)
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

# =====================================================================
# Conflict detection system prompts — pre-built module-level constants
#
# Motivation: detect_conflicts() is called once per clause (up to 10×).
# The original code reconstructed the ~1 977-char system prompt string
# from literals on every call. Moving these to module level:
#  - Eliminates string concatenation overhead × 10 calls
#  - Reduces the taxonomy from the verbose 42-item prose form to a
#    condensed comma-separated list (same category names, ~90 fewer tokens)
# =====================================================================

# Condensed conflict type list — identical category names, shorter surrounding
# prose. The model still receives every category name unchanged so output
# schema (ConflictHit.conflict_type) is unaffected.
_CONFLICT_TYPES = (
    "Authority Conflict, Department Responsibility Conflict, Funding Conflict, "
    "Budget Allocation Conflict, Budget Head Conflict, Fund Utilization Conflict, "
    "Fund Diversion Conflict, Administrative Approval Conflict, Technical Approval Conflict, "
    "Operational Conflict, Implementation Agency Conflict, Implementation Procedure Conflict, "
    "Tendering Procedure Conflict, Procurement Conflict, Policy Conflict, Legal Conflict, "
    "Legal Reference Conflict, Regulatory Conflict, Timeline Conflict, "
    "Monitoring & Reporting Conflict, Committee Structure Conflict, Governance Conflict, "
    "Jurisdiction Conflict, Responsibility Assignment Conflict, Financial Compliance Conflict, "
    "Expenditure Rule Conflict, Payment Authority Conflict, Quality Assurance Conflict, "
    "Inspection Procedure Conflict, Land Acquisition Conflict, Encroachment Procedure Conflict, "
    "Environmental Policy Conflict, Infrastructure Scope Conflict, Digital Compliance Conflict, "
    "Documentation Conflict, Terminology Conflict, Reference Conflict, "
    "Eligibility Criteria Conflict, Priority Conflict, Resource Allocation Conflict, "
    "Approval Hierarchy Conflict, Compliance Conflict"
)

_CONFLICT_BASE = (
    "You are a policy analyst for the Government of Maharashtra.\n"
    "Compare the DRAFT CLAUSE against each numbered CANDIDATE.\n"
    "Determine if any candidates represent a TRUE conflict (e.g. contradictory, superseding, overrides, funding conflict).\n\n"
    "If a candidate represents a TRUE conflict, assign one conflict_type from:\n"
    + _CONFLICT_TYPES + "\n"
    "And assign severity: Low | Medium | High | Critical.\n\n"
    "Return ONLY a JSON array containing candidates that have a TRUE conflict.\n"
    "If NO candidates conflict, you MUST return an empty array: []\n"
    "Do NOT generate JSON objects for independent, compatible, related, or non-conflicting candidates.\n\n"
    "Return ONLY a JSON array, no markdown:\n"
    '[{"candidate_idx": 0, "relation": "contradictory", "conflict_type": "...", '
    '"severity": "...", "confidence": 0.0-1.0, '
    '"justification": "explanation quoting clashing text"}]'
)

# Marathi-aware variant: appends language guidance once.
_CONFLICT_SYSTEM_PROMPT_MR: str = (
    _CONFLICT_BASE
    + "\n\nIMPORTANT: The draft clause is in Marathi (मराठी). "
    "Candidates may be Marathi or English. Compare semantically across languages, "
    "understanding administrative terms (शासन निर्णय, अनुदान, विभाग, पात्रता, "
    "प्रशासकीय मान्यता, वित्तीय मंजुरी)."
)
_CONFLICT_SYSTEM_PROMPT_EN: str = _CONFLICT_BASE

_UNIFIED_CONFLICT_BASE = (
    "You are a policy analyst for the Government of Maharashtra.\n"
    "You are provided with multiple numbered DRAFT CLAUSES and multiple numbered EXISTING CANDIDATES.\n"
    "Compare EVERY draft clause against EVERY existing candidate.\n"
    "Determine if any pairing represents a TRUE conflict (e.g. contradictory, superseding, overrides, funding conflict).\n\n"
    "If a pairing represents a TRUE conflict, assign one conflict_type from:\n"
    + _CONFLICT_TYPES + "\n"
    "And assign severity: Low | Medium | High | Critical.\n\n"
    "Return ONLY a JSON array containing the pairings that have a TRUE conflict.\n"
    "If NO pairings conflict, you MUST return an empty array: []\n"
    "Do NOT generate JSON objects for independent, compatible, related, or non-conflicting pairings.\n\n"
    "Return ONLY a JSON array, no markdown:\n"
    '[{"clause_idx": 0, "candidate_idx": 1, "relation": "contradictory", "conflict_type": "...", '
    '"severity": "...", "confidence": 0.0-1.0, '
    '"justification": "explanation quoting clashing text"}]'
)

_UNIFIED_CONFLICT_SYSTEM_PROMPT_MR: str = (
    _UNIFIED_CONFLICT_BASE
    + "\n\nIMPORTANT: The draft clauses are in Marathi (मराठी). "
    "Candidates may be Marathi or English. Compare semantically across languages, "
    "understanding administrative terms (शासन निर्णय, अनुदान, विभाग, पात्रता, "
    "प्रशासकीय मान्यता, वित्तीय मंजुरी)."
)
_UNIFIED_CONFLICT_SYSTEM_PROMPT_EN: str = _UNIFIED_CONFLICT_BASE


def check_authority_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    authorities = [
        "PCCF", "Principal Chief Conservator", "District Collector", "Collector", "Commissioner", "Secretary", "Minister", "Director",
        "जिल्हाधिकारी", "कलेक्टर", "आयुक्त", "सचिव", "मंत्री"
    ]
    draft_auths = [a for a in authorities if a.lower() in draft.lower()]
    exist_auths = [a for a in authorities if a.lower() in existing.lower()]
    if draft_auths and exist_auths:
        # Check if they are different (mismatch)
        if not set(draft_auths).intersection(set(exist_auths)):
            return (
                "Authority Conflict",
                "High",
                f"Controlling authority has been changed from {exist_auths[0]} to {draft_auths[0]}."
            )
    return None

def check_funding_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    csr_terms = ["csr", "निधी"]
    if any(c in draft.lower() for c in csr_terms) and any(c in existing.lower() for c in csr_terms):
        draft_prohibits = any(w in draft.lower() for w in ["shall not", "prohibit", "not allowed", "not be utilized", "no permission", "परवानगी नाही", "वापरू नये"])
        exist_permits = any(w in existing.lower() for w in ["permit", "allowed", "may be utilized", "utilized", "permission", "परवानगी आहे", "वापरता येईल", "मान्यता"])
        draft_permits = any(w in draft.lower() for w in ["permit", "allowed", "may be utilized", "utilized", "permission", "परवानगी आहे", "वापरता येईल", "मान्यता"])
        exist_prohibits = any(w in existing.lower() for w in ["shall not", "prohibit", "not allowed", "not be utilized", "no permission", "परवानगी नाही", "वापरू नये"])
        
        if (draft_prohibits and exist_permits) or (draft_permits and exist_prohibits):
            reason = "Draft prohibits CSR funding whereas the existing GR explicitly permits CSR funding." if draft_prohibits else "Draft permits CSR funding whereas the existing GR prohibits CSR funding."
            return ("Funding Conflict", "Critical", reason)
    return None

def check_timeline_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    timeline_terms = ["31 march", "financial year", "deadline", "timeline", "months", "days", "दिवस", "महिना", "मुदत"]
    if any(t in draft.lower() for t in timeline_terms) and any(t in existing.lower() for t in timeline_terms):
        if "continue next financial year" in draft.lower() and "before" in existing.lower():
            return (
                "Timeline Conflict",
                "Medium",
                "Draft allows expenditure to continue into the next financial year, whereas the existing GR mandates completion/expenditure before a strict deadline."
            )
    return None

def check_monitoring_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    intervals = ["monthly", "quarterly", "weekly", "annual", "six-monthly", "fortnightly", "मासिक", "तिमाही", "वार्षिक"]
    draft_intervals = [i for i in intervals if i in draft.lower()]
    exist_intervals = [i for i in intervals if i in existing.lower()]
    if draft_intervals and exist_intervals:
        if not set(draft_intervals).intersection(set(exist_intervals)):
            return (
                "Monitoring & Reporting Conflict",
                "Medium",
                f"Reporting frequency has been changed from {exist_intervals[0]} to {draft_intervals[0]}."
            )
    return None

def check_dept_responsibility_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    depts = [
        "Revenue Department", "Rural Development Department", "Public Health Department",
        "Water Supply", "School Education", "Higher and Technical", "Industries",
        "Home Department", "Finance Department", "महसूल विभाग", "ग्रामविकास विभाग", "आरोग्य विभाग"
    ]
    draft_depts = [d for d in depts if d.lower() in draft.lower()]
    exist_depts = [d for d in depts if d.lower() in existing.lower()]
    if draft_depts and exist_depts:
        if not set(draft_depts).intersection(set(exist_depts)):
            return (
                "Department Responsibility Conflict",
                "High",
                f"Implementing/Nodal department has been changed from {exist_depts[0]} to {draft_depts[0]}."
            )
    return None

def check_deterministic_conflict(draft_clause: str, existing_clause: str) -> Optional[tuple[str, str, str]]:
    res = check_authority_conflict(draft_clause, existing_clause)
    if res: return res
    res = check_funding_conflict(draft_clause, existing_clause)
    if res: return res
    res = check_timeline_conflict(draft_clause, existing_clause)
    if res: return res
    res = check_monitoring_conflict(draft_clause, existing_clause)
    if res: return res
    res = check_dept_responsibility_conflict(draft_clause, existing_clause)
    if res: return res
    return None

def detect_conflicts(
    draft_clauses: List[str],
    candidates: List[CorpusHit],
    draft_language: str = "en",
) -> List[ConflictHit]:
    """
    For each draft clause, check deterministic rule engine first. If no conflict
    is found, send a batched LLM call covering all remaining candidates.

    Parameters
    ----------
    draft_clauses   : Operative clauses extracted from the draft GR.
    candidates      : Corpus chunks retrieved as potential conflict candidates.
    draft_language  : 'mr' for Marathi drafts, 'en' for English drafts.
                      When 'mr', the LLM prompt instructs the model to compare
                      Marathi text and reason about Maharashtra administrative
                      context in that language.
    """
    if not draft_clauses or not candidates:
        return []

    results = []
    candidates_per_clause = settings.CANDIDATES_PER_CLAUSE

    # Select the pre-built module-level system prompt — no string construction
    # per call. The MR variant appends Marathi-language guidance once.
    system_prompt = (
        _CONFLICT_SYSTEM_PROMPT_MR if draft_language == "mr"
        else _CONFLICT_SYSTEM_PROMPT_EN
    )
    unified_system_prompt = (
        _UNIFIED_CONFLICT_SYSTEM_PROMPT_MR if draft_language == "mr"
        else _UNIFIED_CONFLICT_SYSTEM_PROMPT_EN
    )

    # -------------------------------------------------------------------------
    # EXPERIMENTAL: Unified Conflict Orchestration
    # -------------------------------------------------------------------------
    if getattr(settings, "USE_UNIFIED_CONFLICT_PROMPT", False):
        try:
            with perf("Unified Conflict Workflow"):
                llm_pending_unified = []
                # Map unified indices back to (clause_idx, clause, original_candidate_idx, hit)
                candidate_mapping = {}
                unified_candidate_idx = 0
                
                unified_clauses_msg = []
                unified_candidates_msg = []
                
                # Deduplicate candidates across clauses so we don't send the same hit multiple times
                seen_candidates = {}

                for clause_idx, clause in enumerate(draft_clauses[: settings.MAX_CLAUSES_ANALYSED]):
                    unified_clauses_msg.append(f"--- DRAFT CLAUSE {clause_idx} ---\n{clause[:500]}\n")
                    
                    start_idx = clause_idx * candidates_per_clause
                    clause_candidates = candidates[start_idx : start_idx + candidates_per_clause]
                    
                    for idx, hit in enumerate(clause_candidates):
                        # Step 1: Run deterministic engine immediately
                        det_res = check_deterministic_conflict(clause, hit.snippet)
                        if det_res:
                            category, severity, reason = det_res
                            results.append(
                                ConflictHit(
                                    draft_clause=clause[:350],
                                    existing_gr_id=hit.gr_id,
                                    existing_gr_title=hit.title,
                                    existing_department=hit.department,
                                    existing_clause=hit.snippet,
                                    relation=Relation.CONFLICT,
                                    confidence=1.0,
                                    justification=reason,
                                    source_url=hit.source_url,
                                    conflict_type=category,
                                    severity=severity,
                                )
                            )
                        else:
                            # Add to unified LLM list
                            if hit.gr_id not in seen_candidates:
                                seen_candidates[hit.gr_id] = unified_candidate_idx
                                unified_candidates_msg.append(
                                    f"--- EXISTING CANDIDATE {unified_candidate_idx} (ID: {hit.gr_id}) ---\n{hit.snippet[:_SNIPPET_MAX]}\n"
                                )
                                unified_candidate_idx += 1
                                
                            c_uidx = seen_candidates[hit.gr_id]
                            candidate_mapping[(clause_idx, c_uidx)] = (clause, hit)

                if candidate_mapping:
                    user_msg = (
                        "DRAFT CLAUSES TO EVALUATE:\n" + "\n".join(unified_clauses_msg) +
                        "\n\nEXISTING CANDIDATES TO COMPARE:\n" + "\n".join(unified_candidates_msg)
                    )
                    
                    with perf("Unified Ollama Call"):
                        raw_reply = call_model(unified_system_prompt, user_msg, purpose="conflict_detection")
                    
                    with perf("Ollama JSON Parsing"):
                        parsed = parse_json_reply(raw_reply)
                        
                    if not isinstance(parsed, list):
                        raise ValueError(f"Unified parser expected list, got {type(parsed)}")
                    
                    with perf("Confidence Filtering"):
                        for item in parsed:
                            c_idx = int(item.get("clause_idx", -1))
                            cand_idx = int(item.get("candidate_idx", -1))
                            
                            if (c_idx, cand_idx) not in candidate_mapping:
                                if c_idx != -1 and cand_idx != -1:
                                    logger.warning(f"Unified LLM hallucinated index pairing: clause {c_idx}, cand {cand_idx}")
                                continue
                                
                            clause, hit = candidate_mapping[(c_idx, cand_idx)]
                            relation_str = item.get("relation", "independent")
                            if relation_str in ["contradictory", "conflict", "true conflict"]:
                                relation_enum = Relation.CONFLICT
                            elif relation_str in ["superseding", "overrides", "supersedes"]:
                                relation_enum = Relation.SUPERSEDES
                            elif relation_str in ["compatible", "duplicate", "overlap"]:
                                relation_enum = Relation.OVERLAP
                            else:
                                continue
                                
                            results.append(
                                ConflictHit(
                                    draft_clause=clause[:350],
                                    existing_gr_id=hit.gr_id,
                                    existing_gr_title=hit.title,
                                    existing_department=hit.department,
                                    existing_clause=hit.snippet,
                                    relation=relation_enum,
                                    confidence=float(item.get("confidence", 0.5)),
                                    justification=item.get("justification", item.get("reason", "Analyzed by AI.")),
                                    source_url=hit.source_url,
                                    conflict_type=item.get("conflict_type", "Policy Conflict"),
                                    severity=item.get("severity", "High"),
                                )
                            )
            # If we get here successfully, return immediately (skipping sequential loop)
            return results
        except Exception as exc:
            logger.error(f"Unified conflict detection failed: {exc}. Falling back to sequential mode.")
            # Clear any results we might have partially accumulated during the deterministic phase
            results = []

    # -------------------------------------------------------------------------
    # STANDARD: Sequential Orchestration Loop
    # -------------------------------------------------------------------------
    for clause_idx, clause in enumerate(draft_clauses[: settings.MAX_CLAUSES_ANALYSED]):
        start_idx = clause_idx * candidates_per_clause
        clause_candidates = candidates[start_idx : start_idx + candidates_per_clause]
        if not clause_candidates:
            continue

        clause_label = f"Clause {clause_idx + 1}"
        with perf(clause_label) as clause_ctx:

            # Step 1: Run Rule Engine
            with perf("Rule Engine"):
                llm_pending = []
                for idx, hit in enumerate(clause_candidates):
                    det_res = check_deterministic_conflict(clause, hit.snippet)
                    if det_res:
                        category, severity, reason = det_res
                        results.append(
                            ConflictHit(
                                draft_clause=clause[:350],
                                existing_gr_id=hit.gr_id,
                                existing_gr_title=hit.title,
                                existing_department=hit.department,
                                existing_clause=hit.snippet,
                                relation=Relation.CONFLICT,
                                confidence=1.0,
                                justification=reason,
                                source_url=hit.source_url,
                                conflict_type=category,
                                severity=severity,
                            )
                        )
                    else:
                        llm_pending.append((idx, hit))

            if not llm_pending:
                clause_ctx.meta(candidates=len(clause_candidates), llm_skipped=True)
                continue

            clause_ctx.meta(candidates=len(clause_candidates), llm_pending=len(llm_pending))

            # Step 2: Build LLM message for remaining candidates.
            # Use list-join instead of += to avoid O(N²) string copying.
            with perf("Prompt Build"):
                parts = [f"DRAFT CLAUSE:\n{clause[:500]}\n\nEXISTING CLAUSES TO COMPARE:\n"]
                for llm_idx, (orig_idx, hit) in enumerate(llm_pending):
                    parts.append(
                        f"--- CANDIDATE {llm_idx} (ID: {hit.gr_id}, Dept: {hit.department}) ---\n"
                        f"{hit.snippet[:_SNIPPET_MAX]}\n\n"
                    )
                user_msg = "".join(parts)

            with perf(f"Ollama Call [{clause_idx + 1}]"):
                raw_reply = call_model(system_prompt, user_msg, purpose="conflict_detection")

            with perf("Ollama JSON Parsing"):
                parsed = parse_json_reply(raw_reply)
            if not parsed or not isinstance(parsed, list):
                continue

            with perf("Confidence Filtering"):
                for item in parsed:
                    try:
                        c_idx = int(item.get("candidate_idx", -1))
                        if 0 <= c_idx < len(llm_pending):
                            orig_idx, hit = llm_pending[c_idx]
                            relation_str = item.get("relation", "independent")
                            if relation_str in ["contradictory", "conflict", "true conflict"]:
                                relation_enum = Relation.CONFLICT
                            elif relation_str in ["superseding", "overrides", "supersedes"]:
                                relation_enum = Relation.SUPERSEDES
                            elif relation_str in ["compatible", "duplicate", "overlap"]:
                                relation_enum = Relation.OVERLAP
                            else:
                                continue
                            results.append(
                                ConflictHit(
                                    draft_clause=clause[:350],
                                    existing_gr_id=hit.gr_id,
                                    existing_gr_title=hit.title,
                                    existing_department=hit.department,
                                    existing_clause=hit.snippet,
                                    relation=relation_enum,
                                    confidence=float(item.get("confidence", 0.5)),
                                    justification=item.get("justification", item.get("reason", "Analyzed by AI.")),
                                    source_url=hit.source_url,
                                    conflict_type=item.get("conflict_type", "Policy Conflict"),
                                    severity=item.get("severity", "High"),
                                )
                            )
                    except Exception as exc:
                        logger.warning("Error parsing conflict item: %s", exc)

    return results


# =====================================================================
# Glossary dict cache — built once, reused on every terminology call
# =====================================================================

# The {english: marathi} dict is identical for every request since the
# knowledge base is loaded once at startup. Building it fresh on each
# call wastes CPU and allocates ~8 KB of dicts per request.
_glossary_dict_cache: Optional[Dict[str, str]] = None
_glossary_cache_lock = threading.Lock()


def _get_full_glossary_dict() -> Dict[str, str]:
    """Return the cached {english: marathi} glossary dict, building it once."""
    global _glossary_dict_cache
    if _glossary_dict_cache is not None:
        return _glossary_dict_cache
    with _glossary_cache_lock:
        if _glossary_dict_cache is None:
            from knowledge import get_knowledge_service
            kb_terms = get_knowledge_service().get_all_glossary_terms()
            _glossary_dict_cache = {
                t["english"]: t["marathi"]
                for t in kb_terms
                if t.get("english") and t.get("marathi")
            }
    return _glossary_dict_cache


# =====================================================================
# Objective 2 — bilingual terminology
# =====================================================================

def map_terminology(text: str, language: Language) -> List[TermMapping]:
    """
    Extract legal terms and map them to their approved equivalents using the KnowledgeService.

    Glossary filtering: only inject terms whose English form appears in the
    draft text (case-insensitive substring match). This reduces prompt size
    from ~800 tokens (full 96-term glossary) to ~80–150 tokens for typical
    drafts, a ~85% token reduction with zero quality impact: terms not
    present in the text cannot be mapped from the text anyway.

    If the filtered glossary is very small (< 3 terms), we fall back to the
    full glossary to ensure the model has sufficient context.
    """
    from knowledge import get_knowledge_service
    ks = get_knowledge_service()
    kb_terms = ks.get_all_glossary_terms()

    # Step 1: Get the cached full glossary dict (no per-call dict construction)
    full_glossary = _get_full_glossary_dict()

    # Step 2: Filter to only terms that appear in the draft text.
    text_lower = text.lower()
    filtered_glossary = {
        en: mr for en, mr in full_glossary.items()
        if en.lower() in text_lower
    }

    # Step 3: Fall back to full glossary if filtering leaves too few entries
    # (e.g., Marathi-only draft where English terms don’t appear literally).
    glossary = filtered_glossary if len(filtered_glossary) >= 3 else full_glossary

    system_prompt = prompts.TERMINOLOGY_MAPPING
    user_msg = prompts.build_terminology_message(text, glossary)

    raw_reply = call_model(system_prompt, user_msg, purpose="terminology_mapping")
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

    raw = call_model(combined_system, user_message, purpose="chat_response")

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
    if _LLM_PROVIDER == "ollama":
        return True   # Ollama needs no API key — just needs to be running
    return _is_api_key_valid(_LLM_API_KEY)
