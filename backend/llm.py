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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

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
# Clause splitting — structural parser
# =====================================================================

@dataclass
class ClauseInfo:
    """A single parsed clause from a Government Resolution."""
    clause_id: str = ""
    clause_number: int = 0
    clause_type: str = "operative"   # header | read | background | operative | schedule | footer
    text: str = ""
    start_offset: int = 0
    end_offset: int = 0


# Patterns to detect boilerplate sections that should NOT be embedded or
# sent to the LLM as candidate clauses.
_HEADER_MARKERS_MR = [
    "महाराष्ट्र शासन", "शासन निर्णय क्रमांक", "मंत्रालय", "बांधकाम भवन",
    "दिनांक", "# Page 1", "Government of Maharashtra",
]
_HEADER_MARKERS_EN = [
    "Government of Maharashtra", "Government Resolution", "Mantralaya",
    "# Page 1", "Date:", "Hutatma Rajguru Chowk",
]
_READ_MARKERS = ["वाचा", "Read:-", "Read :-", "Reference:-", "संदर्भ"]
_BACKGROUND_MARKERS = ["प्रस्तावना", "Preamble", "Introduction:", "Background:"]
_FOOTER_MARKERS = [
    "प्रत", "Copy to", "By order", "सही/-", "(Signed)", "e-mail",
    "या शासन निर्णयाची सत्यप्रत", "This Government Resolution",
]


def _classify_section(text: str) -> str:
    """Classify a text section as header/read/background/operative/footer."""
    text_lower = text.lower()
    first_100 = text[:100]

    # Check footer markers first (they appear at the end)
    for m in _FOOTER_MARKERS:
        if m.lower() in text_lower:
            # Only classify as footer if the marker appears early in the chunk
            # or the chunk is short (signature block)
            if len(text) < 200 or m.lower() in text_lower[:150]:
                return "footer"

    # Check header markers
    for m in _HEADER_MARKERS_MR + _HEADER_MARKERS_EN:
        if m in first_100:
            return "header"

    # Check read section
    for m in _READ_MARKERS:
        if m in first_100:
            return "read"

    # Check background
    for m in _BACKGROUND_MARKERS:
        if m in first_100:
            return "background"

    return "operative"


def extract_clauses(text: str) -> List[ClauseInfo]:
    """
    Structural parser for Government Resolutions.

    Splits the text into classified sections, stripping administrative
    boilerplate (headers, dates, department names, Read sections, signatures)
    and preserving background and operative clauses.

    Returns a list of ClauseInfo objects with rich metadata.
    """
    if not text or not text.strip():
        return []

    # Step 1: Split on numbered clauses (Arabic + Devanagari)
    # This regex splits before lines starting with a number followed by . or )
    raw_parts = re.split(
        r"\n\s*(?=(?:\d+|[\u0966-\u096F]+)[.)]\s)",
        text,
    )

    clauses: List[ClauseInfo] = []
    offset = 0
    clause_counter = 0

    for part in raw_parts:
        stripped = part.strip()
        if len(stripped) < 20:
            offset += len(part)
            continue

        section_type = _classify_section(stripped)

        # Extract clause number from text if it starts with one
        num_match = re.match(r'^(?:(\d+)|([\u0966-\u096F]+))[.)]\s', stripped)
        if num_match:
            clause_counter += 1
            if num_match.group(1):
                clause_num = int(num_match.group(1))
            else:
                # Convert Devanagari digits to Arabic
                dev_str = num_match.group(2)
                clause_num = int(''.join(
                    str(ord(c) - 0x0966) for c in dev_str
                ))
            if section_type == "operative":
                section_type = "operative"  # confirm
        else:
            clause_num = clause_counter

        clauses.append(ClauseInfo(
            clause_id=f"clause_{clause_counter}",
            clause_number=clause_num,
            clause_type=section_type,
            text=stripped,
            start_offset=offset,
            end_offset=offset + len(part),
        ))
        offset += len(part)

    # If no clauses were found, treat the entire text as one clause
    if not clauses:
        return [ClauseInfo(
            clause_id="clause_1",
            clause_number=1,
            clause_type="operative",
            text=text.strip(),
            start_offset=0,
            end_offset=len(text),
        )]

    return clauses


# Patterns that identify template placeholder headings or administrative-only
# text that should NOT be treated as operative policy clauses (Commented out / Non-conflicting).
# _PLACEHOLDER_PATTERNS: List[re.Pattern] = [
#     re.compile(r'^\d+\.?\s*regarding\b', re.IGNORECASE),       # "Regarding disciplinary action..."
#     re.compile(r'^\d+\.?\s*subject\s*:', re.IGNORECASE),       # "Subject: ..."
#     re.compile(r'^\[.{1,80}\]$'),                               # "[PLACEHOLDER]"
#     re.compile(r'^<.{1,80}>$'),                                 # "<CLAUSE_TEXT>"
#     re.compile(r'^#+\s'),                                       # Markdown headings
#     re.compile(r'^\d+\.?\s*(?:name|date|place|venue|location|designation|officer|authority)\s*:', re.IGNORECASE),
#     re.compile(r'^\d+\.?\s*(?:पदाचे नाव|दिनांक|ठिकाण)\s*:', re.IGNORECASE),  # Marathi equivalents
# ]


def _is_placeholder_clause(text: str) -> bool:
    """
    Return True if the clause text is a template heading or administrative
    placeholder with no operative policy language. (Currently disabled / non-conflicting)
    """
    # Placeholder checking disabled to maintain compatibility with Pushkar's pipeline
    return False


def split_into_clauses(text: str) -> List[str]:
    """
    Break a draft into its operative clauses (backward-compatible API).

    Internally uses the structural parser, but returns plain strings
    for callers that don't need ClauseInfo metadata.
    Only returns operative and background clauses, stripping headers,
    read sections, and footers.
    """
    all_clauses = extract_clauses(text)
    operative = [
        c.text for c in all_clauses
        if c.clause_type in ("operative", "background")
        and len(c.text.strip()) > 40
    ]
    return operative or [text.strip()]


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
# Objective 1 — conflict detection (Semantic-First Pipeline)
# =====================================================================

_SNIPPET_MAX = 600   # chars sent per candidate to the API

# =====================================================================
# Conflict categories — expanded taxonomy
# =====================================================================

_CONFLICT_TYPES = (
    "Amendment, Supersession, Withdrawal, Cancellation, Approval Change, "
    "Eligibility Change, Funding Conflict, Budget Allocation Conflict, "
    "Timeline Conflict, Legal Reference Conflict, Policy Conflict, "
    "Jurisdiction Conflict, Responsibility Transfer, Administrative Conflict, "
    "Authority Conflict, Monitoring & Reporting Conflict, "
    "Implementation Procedure Conflict, Procurement Conflict"
)

_NEGATION_WORDS = [
    "not",
    "shall not",
    "must not",
    "cannot",
    "withdraw",
    "withdrawn",
    "cancel",
    "cancelled",
    "revoke",
    "revoked",
    "deny",
    "denied",
    "prohibited",
    "ineligible",
    "नाही",
    "रद्द",
    "मागे",
    "अवैध",
    "अपात्र",
    "प्रतिबंधित",
    "अमान्य",
]

_RESPONSIBILITY_WORDS = [
    "responsible",
    "responsibility",
    "liable",
    "implement",
    "implementation",
    "ensure",
    "maintain",
    "supervise",
    "जबाबदार",
    "जबाबदारी",
    "अंमलबजावणी",
]

_RESERVATION_WORDS = [
    "sc",
    "st",
    "obc",
    "sebc",
    "ews",
    "open",
    "general",
    "vjnt",
    "nt",
    "sbc",
]

_ELIGIBILITY_WORDS = [
    "eligible",
    "eligibility",
    "qualification",
    "criteria",
    "qualified",
    "ineligible",
    "पात्र",
    "अपात्र",
    "अर्हता",
]

# =====================================================================
# Semantic-first conflict prompt — never bypasses the LLM
# =====================================================================

_SEMANTIC_CONFLICT_SYSTEM_PROMPT = (
    "You are a senior Government Resolution policy analyst.\n\n"
    "Compare ONE draft clause against multiple existing clauses.\n\n"
    "For each candidate decide whether the relationship is:\n"
    "compatible\n"
    "independent\n"
    "related\n"
    "superseded\n"
    "contradictory\n\n"
    "A contradiction exists when BOTH clauses cannot legally remain valid simultaneously.\n\n"
    "Treat the following as contradictions:\n"
    "• responsibility transferred\n"
    "• responsibility removed\n"
    "• obligation reversed\n"
    "• permission revoked\n"
    "• mandatory becomes optional\n"
    "• optional becomes mandatory\n"
    "• eligible becomes ineligible\n"
    "• ineligible becomes eligible\n"
    "• reservation/category changes\n"
    "• benefit withdrawn\n"
    "• grant cancelled\n"
    "• approval withdrawn\n"
    "• financial entitlement changed\n"
    "• legal definition changed\n\n"
    "DO NOT treat these alone as contradictions:\n"
    "• different department\n"
    "• different authority\n"
    "• different dates\n"
    "• administrative wording\n"
    "• formatting\n\n"
    "Ignore headers, signatures, references and boilerplate.\n\n"
    "Semantic hints:\n"
    "{hints}\n\n"
    "Return ONLY contradictory or superseded clauses as JSON."
)

_SEMANTIC_CONFLICT_MR_SUFFIX = (
    "\n\nLANGUAGE: The draft clause is in Marathi (मराठी). "
    "Candidates may be Marathi or English. Compare SEMANTICALLY across languages, "
    "understanding administrative terms (शासन निर्णय = Government Resolution, "
    "अनुदान = Grant, विभाग = Department, पात्रता = Eligibility, "
    "प्रशासकीय मान्यता = Administrative Approval, वित्तीय मंजुरी = Financial Sanction)."
)

# =====================================================================
# Legacy prompts — kept for backward compat with USE_UNIFIED_CONFLICT_PROMPT
# =====================================================================

_CONFLICT_BASE = _SEMANTIC_CONFLICT_SYSTEM_PROMPT.replace("{hints}", "No hints available.")
_CONFLICT_SYSTEM_PROMPT_MR = _CONFLICT_BASE + _SEMANTIC_CONFLICT_MR_SUFFIX
_CONFLICT_SYSTEM_PROMPT_EN = _CONFLICT_BASE
_UNIFIED_CONFLICT_BASE = _CONFLICT_BASE
_UNIFIED_CONFLICT_SYSTEM_PROMPT_MR = _CONFLICT_BASE + _SEMANTIC_CONFLICT_MR_SUFFIX
_UNIFIED_CONFLICT_SYSTEM_PROMPT_EN = _CONFLICT_BASE


# =====================================================================
# Semantic Hint Generators (formerly deterministic conflict rules)
#
# These functions NO LONGER return ConflictHit objects and NO LONGER
# bypass the LLM. They return hint strings that are injected into the
# LLM prompt to guide its analysis.
# =====================================================================

# Lightweight lexical heuristics only. These helpers never decide
# conflicts themselves. They only add advisory hints that guide the
# final LLM judgment.
def _hint_negation(draft: str, existing: str) -> Optional[str]:
    """Detect possible legal obligation reversals with lightweight keywords."""
    draft_lower = draft.lower()
    existing_lower = existing.lower()

    draft_has_negation = any(term in draft_lower for term in _NEGATION_WORDS)
    existing_has_negation = any(term in existing_lower for term in _NEGATION_WORDS)

    if draft_has_negation != existing_has_negation:
        return "HINT: Possible obligation reversal or policy negation detected."
    return None


# Lightweight lexical heuristics only. These helpers never decide
# conflicts themselves. They only add advisory hints that guide the
# final LLM judgment.
def _hint_responsibility(draft: str, existing: str) -> Optional[str]:
    """Detect possible responsibility transfer or removal with simple matching."""
    draft_lower = draft.lower()
    existing_lower = existing.lower()

    draft_has_responsibility = any(term in draft_lower for term in _RESPONSIBILITY_WORDS)
    existing_has_responsibility = any(term in existing_lower for term in _RESPONSIBILITY_WORDS)
    draft_has_negation = any(term in draft_lower for term in _NEGATION_WORDS)
    existing_has_negation = any(term in existing_lower for term in _NEGATION_WORDS)

    if draft_has_responsibility or existing_has_responsibility:
        if draft_has_negation != existing_has_negation or draft_has_responsibility != existing_has_responsibility:
            return "HINT: Possible responsibility transfer or removal detected."
    return None


# Lightweight lexical heuristics only. These helpers never decide
# conflicts themselves. They only add advisory hints that guide the
# final LLM judgment.
def _hint_reservation(draft: str, existing: str) -> Optional[str]:
    """Detect possible reservation or category reclassification with lightweight matching."""
    draft_lower = draft.lower()
    existing_lower = existing.lower()

    draft_terms = [term for term in _RESERVATION_WORDS if term in draft_lower]
    existing_terms = [term for term in _RESERVATION_WORDS if term in existing_lower]

    if draft_terms and existing_terms and draft_terms != existing_terms:
        return "HINT: Possible reservation/category reclassification detected."
    return None


# Lightweight lexical heuristics only. These helpers never decide
# conflicts themselves. They only add advisory hints that guide the
# final LLM judgment.
def _hint_eligibility(draft: str, existing: str) -> Optional[str]:
    """Detect possible eligibility criteria change with simple keyword matching."""
    draft_lower = draft.lower()
    existing_lower = existing.lower()

    draft_terms = [term for term in _ELIGIBILITY_WORDS if term in draft_lower]
    existing_terms = [term for term in _ELIGIBILITY_WORDS if term in existing_lower]
    draft_has_negation = any(term in draft_lower for term in _NEGATION_WORDS)
    existing_has_negation = any(term in existing_lower for term in _NEGATION_WORDS)

    if draft_terms and existing_terms and (draft_terms != existing_terms or draft_has_negation != existing_has_negation):
        return "HINT: Possible eligibility criteria change detected."
    return None


def _hint_authority(draft: str, existing: str) -> Optional[str]:
    """Generate a hint if different authority names are detected."""
    authorities = [
        "PCCF", "Principal Chief Conservator", "District Collector", "Collector",
        "Commissioner", "Secretary", "Minister", "Director",
        "जिल्हाधिकारी", "कलेक्टर", "आयुक्त", "सचिव", "मंत्री",
    ]
    draft_auths = [a for a in authorities if a.lower() in draft.lower()]
    exist_auths = [a for a in authorities if a.lower() in existing.lower()]
    if draft_auths and exist_auths and not set(draft_auths).intersection(set(exist_auths)):
        return (
            f"HINT: Different authorities detected (draft: {draft_auths[0]}, "
            f"existing: {exist_auths[0]}). Verify whether approval authority "
            f"has actually changed in a conflicting way."
        )
    return None


def _hint_funding(draft: str, existing: str) -> Optional[str]:
    """Generate a hint if funding source keywords differ."""
    fund_terms = ["csr", "निधी", "funding", "grant", "अनुदान", "budget"]
    draft_has = any(t in draft.lower() for t in fund_terms)
    exist_has = any(t in existing.lower() for t in fund_terms)
    if draft_has and exist_has:
        return (
            "HINT: Both clauses mention funding/financial terms. "
            "Verify whether funding sources or amounts are contradictory."
        )
    return None


def _hint_timeline(draft: str, existing: str) -> Optional[str]:
    """Generate a hint if timeline keywords are detected."""
    time_terms = ["deadline", "days", "months", "financial year", "दिवस", "महिना", "मुदत"]
    draft_has = any(t in draft.lower() for t in time_terms)
    exist_has = any(t in existing.lower() for t in time_terms)
    if draft_has and exist_has:
        return (
            "HINT: Both clauses contain timeline references. "
            "Check whether the timelines are contradictory."
        )
    return None


def _hint_monitoring(draft: str, existing: str) -> Optional[str]:
    """Generate a hint if monitoring/reporting intervals differ."""
    intervals = ["monthly", "quarterly", "weekly", "annual", "मासिक", "तिमाही", "वार्षिक"]
    draft_int = [i for i in intervals if i in draft.lower()]
    exist_int = [i for i in intervals if i in existing.lower()]
    if draft_int and exist_int and not set(draft_int).intersection(set(exist_int)):
        return (
            f"HINT: Different reporting frequencies detected "
            f"(draft: {draft_int[0]}, existing: {exist_int[0]}). "
            f"Verify whether this represents a genuine reporting conflict."
        )
    return None


def _hint_department(draft: str, existing: str) -> Optional[str]:
    """Generate a hint if different departments are mentioned.

    CRITICAL: This is a hint ONLY. Different department names NEVER
    automatically imply a conflict. The LLM must verify semantically.
    """
    depts = [
        "Revenue Department", "Rural Development", "Public Health",
        "Water Supply", "School Education", "Higher and Technical",
        "Industries", "Home Department", "Finance Department",
        "महसूल विभाग", "ग्रामविकास विभाग", "आरोग्य विभाग",
    ]
    draft_depts = [d for d in depts if d.lower() in draft.lower()]
    exist_depts = [d for d in depts if d.lower() in existing.lower()]
    if draft_depts and exist_depts and not set(draft_depts).intersection(set(exist_depts)):
        return (
            f"HINT: Cross-department reference detected "
            f"(draft: {draft_depts[0]}, existing: {exist_depts[0]}). "
            f"This is likely a cross-department reference, NOT a conflict. "
            f"Only flag as conflict if implementation RESPONSIBILITY has genuinely transferred."
        )
    return None


def generate_semantic_hints(draft_clause: str, existing_clause: str) -> List[str]:
    """Run all hint generators and return the list of triggered hints."""
    hints = []
    for fn in [
        _hint_negation,
        _hint_responsibility,
        _hint_reservation,
        _hint_eligibility,
        _hint_authority,
        _hint_funding,
        _hint_timeline,
        _hint_monitoring,
        _hint_department,
    ]:
        result = fn(draft_clause, existing_clause)
        if result:
            hints.append(result)
    return hints


# =====================================================================
# Legacy API: check_deterministic_conflict — kept for backward compat
# but now returns None always (hints are used instead)
# =====================================================================

def check_authority_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    return None  # Converted to semantic hint

def check_funding_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    return None  # Converted to semantic hint

def check_timeline_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    return None  # Converted to semantic hint

def check_monitoring_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    return None  # Converted to semantic hint

def check_dept_responsibility_conflict(draft: str, existing: str) -> Optional[tuple[str, str, str]]:
    return None  # Converted to semantic hint

def check_deterministic_conflict(draft_clause: str, existing_clause: str) -> Optional[tuple[str, str, str]]:
    return None  # All rules converted to semantic hints


# =====================================================================
# Confidence bands
# =====================================================================

_CONF_AUTO = 0.85       # >= this: auto-confirmed conflict
_CONF_REVIEW = 0.60     # >= this: needs officer review
# < _CONF_REVIEW: discarded


def _confidence_recommendation(confidence: float) -> str:
    """Return an officer recommendation based on confidence band."""
    if confidence >= _CONF_AUTO:
        return "High-confidence conflict. Immediate review recommended."
    elif confidence >= _CONF_REVIEW:
        return "Moderate confidence. Officer verification required."
    else:
        return "Low confidence. May be discarded."


# =====================================================================
# Main conflict detection — semantic-first pipeline
# =====================================================================

def detect_conflicts(
    draft_clauses: List[str],
    candidates: Union[List[CorpusHit], List[List[CorpusHit]]],
    draft_language: str = "en",
) -> List[ConflictHit]:
    """
    Semantic-first conflict detection pipeline.

    For each draft clause:
    1. Gather candidates from retrieval
    2. Generate semantic hints
    3. Build prompt with hints and complete clause objects
    4. Send to LLM for semantic verification
    5. Apply confidence filtering and return ConflictHit objects with quotes

    Parameters
    ----------
    draft_clauses   : Operative clauses extracted from the draft GR.
    candidates      : Corpus hits retrieved as potential conflict candidates (flat or nested per clause).
    draft_language  : 'mr' for Marathi drafts, 'en' for English drafts.
    """
    if not draft_clauses or not candidates:
        return []

    results: List[ConflictHit] = []
    candidates_per_clause = settings.CANDIDATES_PER_CLAUSE
    mr_suffix = _SEMANTIC_CONFLICT_MR_SUFFIX if draft_language == "mr" else ""

    # Normalize candidate structure: handle both List[List[CorpusHit]] and flat List[CorpusHit]
    is_nested = isinstance(candidates[0], list) if candidates else False

    for clause_idx, clause in enumerate(draft_clauses[:settings.MAX_CLAUSES_ANALYSED]):
        if is_nested:
            if clause_idx < len(candidates):
                clause_candidates = candidates[clause_idx]
            else:
                clause_candidates = []
        else:
            start_idx = clause_idx * candidates_per_clause
            clause_candidates = candidates[start_idx:start_idx + candidates_per_clause]

        if not clause_candidates:
            continue

        clause_label = f"Clause {clause_idx + 1}"
        with perf(clause_label) as clause_ctx:

            # Step 1: Generate semantic hints for ALL candidates
            with perf("Hint Generation"):
                all_hints: List[str] = []
                for hit in clause_candidates:
                    hints = generate_semantic_hints(clause, hit.snippet)
                    all_hints.extend(hints)
                unique_hints = list(dict.fromkeys(all_hints))
                hints_text = "\n".join(unique_hints)

            # Step 2: Build the prompt with hints and full clause text
            with perf("Prompt Build"):
                system_prompt = _SEMANTIC_CONFLICT_SYSTEM_PROMPT.replace("{hints}", hints_text) + mr_suffix

                parts = [f"DRAFT CLAUSE:\n{clause}\n\nEXISTING CLAUSES TO COMPARE:\n"]
                for cand_idx, hit in enumerate(clause_candidates):
                    parts.append(
                        f"--- CANDIDATE {cand_idx} ---\n"
                        f"GR ID: {hit.gr_id}\n"
                        f"Department: {hit.department}\n"
                        f"Subject/Title: {hit.title}\n"
                        f"Clause Type: {getattr(hit, 'clause_type', 'operative') or 'operative'}\n"
                        f"Clause Number: {getattr(hit, 'clause_number', 'N/A') or 'N/A'}\n"
                        f"Similarity Score: {hit.score:.3f}\n"
                        f"Text:\n{hit.snippet}\n\n"
                    )
                user_msg = "".join(parts)

            clause_ctx.meta(
                candidates=len(clause_candidates),
                hints=len(unique_hints),
                llm_skipped=False,
            )

            # Step 3: Call LLM — always, no bypass
            with perf(f"LLM Call [{clause_idx + 1}]"):
                raw_reply = call_model(system_prompt, user_msg, purpose="conflict_detection")

            # Step 4: Parse response
            with perf("JSON Parsing"):
                parsed = parse_json_reply(raw_reply)
            if not parsed or not isinstance(parsed, list):
                continue

            # Step 5: Apply confidence filtering and build ConflictHit objects
            with perf("Confidence Filtering"):
                for item in parsed:
                    try:
                        c_idx = int(item.get("candidate_idx", -1))
                        if not (0 <= c_idx < len(clause_candidates)):
                            logger.warning("LLM hallucinated candidate_idx=%d (max=%d)", c_idx, len(clause_candidates) - 1)
                            continue

                        hit = clause_candidates[c_idx]
                        confidence = float(item.get("confidence", 0.5))

                        # Discard low-confidence results
                        if confidence < _CONF_REVIEW:
                            logger.debug("Discarding low-confidence (%.2f) conflict for GR %s", confidence, hit.gr_id)
                            continue

                        relation_str = str(item.get("relation", "independent")).lower()
                        if relation_str in ["contradictory", "conflict", "true conflict"]:
                            relation_enum = Relation.CONFLICT
                        elif relation_str in ["superseding", "overrides", "supersedes"]:
                            relation_enum = Relation.SUPERSEDES
                        elif relation_str in ["compatible", "duplicate", "overlap"]:
                            relation_enum = Relation.OVERLAP
                        else:
                            if settings.DEBUG:
                                print(f"Discarding conflict - Reason: Unknown relation ({relation_str})")
                            continue  # independent/related — not a conflict

                        # Build rich justification with exact clause quotes
                        draft_quote = str(item.get("draft_quote", "")).strip()
                        existing_quote = str(item.get("existing_quote", "")).strip()
                        raw_justification = str(item.get("justification", item.get("reason", "Analyzed by AI."))).strip()
                        recommendation = _confidence_recommendation(confidence)

                        justification_parts = []
                        if draft_quote:
                            justification_parts.append(f'Draft Quote: "{draft_quote}"')
                        if existing_quote:
                            justification_parts.append(f'Existing Quote: "{existing_quote}"')
                        justification_parts.append(f"Reason: {raw_justification}")
                        justification_parts.append(f"Recommendation: {recommendation}")
                        full_justification = " | ".join(justification_parts)

                        results.append(
                            ConflictHit(
                                draft_clause=clause,
                                existing_gr_id=hit.gr_id,
                                existing_gr_title=hit.title,
                                existing_department=hit.department,
                                existing_clause=hit.snippet,
                                relation=relation_enum,
                                confidence=confidence,
                                justification=full_justification,
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
