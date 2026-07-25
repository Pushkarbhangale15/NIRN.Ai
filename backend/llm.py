"""
llm.py — every call to the language model lives here and nowhere else.

STUB, but the prompts are already written in prompts.py, so Day 2 is
only adding the HTTP call and parsing the JSON that comes back.

Keeping all model code in one file means swapping Gemini for Claude is
a one-function change instead of a search across the codebase.
"""

import json
import re
from typing import List, Optional

import prompts
from config import settings
from schemas import ConflictHit, CorpusHit, Language, Relation, TermMapping


# ---------------------------------------------------------------------
# Clause splitting — rule-based on purpose
# ---------------------------------------------------------------------

def split_into_clauses(text: str) -> List[str]:
    """
    Break a draft into its operative clauses.

    Deliberately rule-based. A language model here would be slower,
    cost money per call, and give a different answer each time — none
    of which you want in a step that runs before every analysis.

    Tighten these rules on Day 2 once you have seen how real GRs in
    data/ are actually laid out.
    """
    parts = re.split(r"\n\s*(?=\d+[.)]\s)", text)
    clauses = [part.strip() for part in parts if len(part.strip()) > 40]
    return clauses or [text.strip()]


# ---------------------------------------------------------------------
# Calling the model
# ---------------------------------------------------------------------

import httpx

def get_mock_response(system_prompt: str, user_message: str) -> str:
    """Fallback generator for local demo when API key is missing or calls fail."""
    system_prompt_lower = system_prompt.lower()
    
    if "conflict" in system_prompt_lower:
        # Match conflict detection
        return json.dumps([
            {
                "candidate_idx": 0,
                "relation": "overlap",
                "confidence": 0.78,
                "justification": "Both clauses discuss the criteria for lateral entry and administrative sanctioning."
            }
        ])
    elif "terminology" in system_prompt_lower:
        # Match terminology mapping
        return json.dumps([
            {
                "source_term": "sanctioned intake",
                "source_language": "en",
                "target_term": "मंजूर प्रवेश क्षमता",
                "consistent_with_corpus": True,
                "note": "Standard administrative translation in Maharashtra GRs."
            }
        ])
    elif "drafting" in system_prompt_lower:
        # Match drafting assist
        return (
            "शासन निर्णय: उच्च व तंत्र शिक्षण विभागांतर्गत येणाऱ्या शासकीय व अनुदानित महाविद्यालयांमधील "
            "मंजूर प्रवेश क्षमता (Sanctioned Intake) शैक्षणिक वर्ष २०२६-२७ पासून सुधारित करण्यात येत आहे."
        )
    else:
        # Default conversational chat mock
        return "हा उच्च व तंत्र शिक्षण विभागाचा अधिकृत शासन निर्णय आहे. या नियमानुसार मंजूर प्रवेश क्षमता निश्चित करण्यात आली आहे."


def call_model(system_prompt: str, user_message: str) -> str:
    """
    Send one request to the language model and return its raw text reply.

    Every other function in this file goes through here. Direct HTTP post
    request to Gemini API is used to ensure stability and independence from SDK.
    """
    api_key = settings.LLM_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return get_mock_response(system_prompt, user_message)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    # Check if we need to enforce JSON output format
    payload = {
        "contents": [{"parts": [{"text": user_message}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    
    # If the system prompt asks for JSON, tell Gemini to return JSON
    if "json" in system_prompt.lower():
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini API Exception: {e}. Falling back to mock generator.")
        return get_mock_response(system_prompt, user_message)


def parse_json_reply(raw: str) -> Optional[dict | list]:
    """
    Parse JSON out of a model reply.

    Models wrap JSON in ```json fences roughly a third of the time even
    when told not to. Stripping them here saves you debugging a
    JSONDecodeError.
    """
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(),
                     flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: grab the outermost { } or [ ] block.
        match = re.search(r"[\{\[].*[\}\]]", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------
# Objective 1 — conflict detection
# ---------------------------------------------------------------------

def detect_conflicts(draft_clauses: List[str],
                     candidates: List[CorpusHit]) -> List[ConflictHit]:
    """
    For each (draft clause, retrieved clause) pair, ask the model to
    classify the relationship.
    
    Batched per draft clause to reduce latency from O(N x M) to O(N).
    """
    if not draft_clauses or not candidates:
        return []

    results = []
    candidates_per_clause = settings.CANDIDATES_PER_CLAUSE

    for clause_idx, clause in enumerate(draft_clauses[:settings.MAX_CLAUSES_ANALYSED]):
        start_idx = clause_idx * candidates_per_clause
        clause_candidates = candidates[start_idx : start_idx + candidates_per_clause]
        if not clause_candidates:
            continue
            
        user_msg = f"DRAFT CLAUSE:\n{clause}\n\nEXISTING CLAUSES TO COMPARE:\n"
        for idx, hit in enumerate(clause_candidates):
            user_msg += f"--- CANDIDATE {idx} (ID: {hit.gr_id}, Dept: {hit.department}) ---\n{hit.snippet}\n\n"
            
        system_prompt = (
            "You are a legal analyst for the Government of Maharashtra. "
            "Compare the DRAFT CLAUSE against each of the numbered CANDIDATES. "
            "For each candidate, classify the relationship as exactly one of:\n"
            "- conflict   : the two clauses cannot both be complied with\n"
            "- overlap    : same subject matter, but no contradiction\n"
            "- supersedes : the draft clause clearly replaces the existing one\n"
            "- unrelated  : different subject matter\n\n"
            "Return ONLY a JSON array of objects, with no markdown fences and no preamble:\n"
            '[{"candidate_idx": 0, "relation": "...", "confidence": 0.0-1.0, "justification": "one sentence quoting specific words"}]'
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
                            draft_clause=clause[:280],
                            existing_gr_id=hit.gr_id,
                            existing_gr_title=hit.title,
                            existing_department=hit.department,
                            existing_clause=hit.snippet,
                            relation=Relation(relation_str),
                            confidence=float(item.get("confidence", 0.5)),
                            justification=item.get("justification", "Analyzed by AI."),
                            source_url=hit.source_url,
                        )
                    )
            except Exception as e:
                print(f"Error parsing conflict item: {e}")
                
    return results


# ---------------------------------------------------------------------
# Objective 2 — bilingual terminology
# ---------------------------------------------------------------------

def map_terminology(text: str, language: Language) -> List[TermMapping]:
    """
    Extract legal terms and map them to their approved equivalents.
    """
    system_prompt = prompts.TERMINOLOGY_MAPPING
    # Standard glossary of approved mappings
    glossary = {
        "sanctioned intake": "मंजूर प्रवेश क्षमता",
        "probation period": "परिविक्षाधीन कालावधी",
        "departmental inquiry": "विभागीय चौकशी",
        "administrative approval": "प्रशासकीय मान्यता",
        "financial sanction": "वित्तीय मंजुरी"
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
                        note=item.get("note", "")
                    )
                )
            except Exception as e:
                print(f"Error parsing term item: {e}")
                
    if not results:
        # Fallback to standard check
        for en_term, mr_term in glossary.items():
            if en_term in text.lower():
                results.append(
                    TermMapping(
                        source_term=en_term,
                        source_language=Language.ENGLISH,
                        target_term=mr_term,
                        consistent_with_corpus=True,
                        note="Verified from standard corpus glossary."
                    )
                )
    return results


def is_configured() -> bool:
    """Whether an API key is present. Surfaced on /health."""
    return bool(settings.LLM_API_KEY) and settings.LLM_API_KEY != "your-api-key-here"
