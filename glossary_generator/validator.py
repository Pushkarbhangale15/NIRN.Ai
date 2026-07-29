"""
validator.py — Optional LLM validation layer for low-confidence alignments.

The LLM is ONLY used as a final validation pass for review_candidates.
It must never invent new terminology — it only confirms or rejects
candidates already extracted by the deterministic pipeline.
"""

import json
import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def validate_candidates_with_llm(
    candidates: list,  # List[AlignedPair]
    provider: str = "ollama",
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "gemma3:4b",
    gemini_api_key: str = "",
) -> Tuple[list, list]:
    """
    Validate low-confidence bilingual pairs using an LLM.

    The LLM receives an English term and Marathi candidate and answers:
      - Is this a correct translation? (yes/no)
      - If no, what is the correct Marathi equivalent?

    Returns:
        (validated_pairs, still_uncertain_pairs)
    """
    if not candidates:
        return [], []

    validated = []
    uncertain = []

    for pair in candidates:
        result = _ask_llm_single(pair, provider, ollama_base_url, ollama_model, gemini_api_key)
        if result is None:
            uncertain.append(pair)
        elif result:
            pair.confidence = min(pair.confidence + 0.15, 0.95)
            pair.method = pair.method + "+llm_validated"
            validated.append(pair)
        else:
            uncertain.append(pair)

    return validated, uncertain


def _ask_llm_single(
    pair,
    provider: str,
    ollama_base_url: str,
    ollama_model: str,
    gemini_api_key: str,
) -> Optional[bool]:
    """
    Ask the LLM whether an English→Marathi pair is correct.

    Returns:
        True  — confirmed correct
        False — confirmed incorrect
        None  — uncertain / call failed
    """
    system_prompt = (
        "You are a bilingual legal expert for the Government of Maharashtra. "
        "You will be given an English administrative term and a candidate Marathi translation. "
        "Answer ONLY with a JSON object in this exact format (no other text):\n"
        '{"correct": true, "note": "optional explanation"}\n'
        "or\n"
        '{"correct": false, "note": "reason and correct translation if known"}\n\n'
        "Be conservative — only confirm if you are certain. "
        "Do NOT invent or hallucinate translations."
    )
    user_msg = (
        f'English term: "{pair.english}"\n'
        f'Candidate Marathi: "{pair.marathi}"\n'
        f'Category context: "{pair.category}"\n\n'
        "Is this Marathi translation correct for official Maharashtra Government Resolutions?"
    )

    raw_response = None

    try:
        if provider == "ollama":
            raw_response = _call_ollama(system_prompt, user_msg, ollama_base_url, ollama_model)
        elif provider == "gemini" and gemini_api_key:
            raw_response = _call_gemini(system_prompt, user_msg, gemini_api_key)
    except Exception as e:
        logger.warning("LLM call failed for pair '%s' / '%s': %s", pair.english, pair.marathi, e)
        return None

    if not raw_response:
        return None

    try:
        import re
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw_response.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        return bool(data.get("correct", False))
    except Exception:
        logger.debug("Failed to parse LLM JSON response: %s", raw_response[:200])
        return None


def _call_ollama(system_prompt: str, user_msg: str, base_url: str, model: str) -> Optional[str]:
    """Call a local Ollama instance."""
    try:
        import httpx
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            "stream": False,
            "format": "json",
        }
        resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        logger.warning("Ollama call error: %s", e)
        return None


def _call_gemini(system_prompt: str, user_msg: str, api_key: str) -> Optional[str]:
    """Call Gemini API."""
    try:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": user_msg}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {"responseMimeType": "application/json"},
        }
        resp = httpx.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning("Gemini call error: %s", e)
        return None
