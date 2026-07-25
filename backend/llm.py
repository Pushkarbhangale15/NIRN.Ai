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

def call_model(system_prompt: str, user_message: str) -> str:
    """
    Send one request to the language model and return its raw text reply.

    Every other function in this file goes through here, so there is
    exactly one place to add retries, logging, or a provider switch.

    TODO (Day 2) for Gemini:
        import google.generativeai as genai
        genai.configure(api_key=settings.LLM_API_KEY)
        model = genai.GenerativeModel(
            settings.LLM_MODEL, system_instruction=system_prompt)
        return model.generate_content(user_message).text
    """
    raise NotImplementedError("Wire up the model provider on Day 2")


def parse_json_reply(raw: str) -> Optional[dict | list]:
    """
    Parse JSON out of a model reply.

    Models wrap JSON in ```json fences roughly a third of the time even
    when told not to. Stripping them here saves you debugging a
    JSONDecodeError at one in the morning.

    Returns None on failure rather than raising — a single unparseable
    reply should downgrade one result, not crash the whole analysis.
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

    TODO (Day 2):
        for clause in draft_clauses:
            for hit in candidates:
                raw = call_model(
                    prompts.CONFLICT_DETECTION,
                    prompts.build_conflict_message(
                        clause, hit.snippet, hit.department),
                )
                parsed = parse_json_reply(raw)
                if not parsed:
                    continue
                if parsed["relation"] == "unrelated":
                    continue
                if parsed["confidence"] < settings.CONFLICT_CONFIDENCE_FLOOR:
                    continue
                results.append(ConflictHit(...))

    COST WARNING: this is clauses x candidates model calls. Ten clauses
    against eight candidates is eighty calls per analysis, which is slow
    and expensive enough to ruin a live demo. settings.MAX_CLAUSES_ANALYSED
    and settings.CANDIDATES_PER_CLAUSE cap it. Alternatively, batch
    several pairs into one call.
    """
    if not draft_clauses or not candidates:
        return []

    top = candidates[0]
    return [
        ConflictHit(
            draft_clause=draft_clauses[0][:280],
            existing_gr_id=top.gr_id,
            existing_gr_title=top.title,
            existing_department=top.department,
            existing_clause=top.snippet,
            relation=Relation.CONFLICT,
            confidence=0.81,
            justification=(
                "STUB RESULT — the draft sets a different threshold from the "
                "one fixed in the cited resolution."
            ),
            source_url=top.source_url,
        )
    ]


# ---------------------------------------------------------------------
# Objective 2 — bilingual terminology
# ---------------------------------------------------------------------

def map_terminology(text: str, language: Language) -> List[TermMapping]:
    """
    Extract legal terms and map them to their approved equivalents.

    TODO (Day 2): call the model with prompts.TERMINOLOGY_MAPPING plus
    your glossary, parse the JSON array, return real mappings.

    Build the glossary by extracting recurring term pairs from the
    bilingual corpus once, then pass it into every call. That is what
    makes the output consistent across drafts rather than plausible but
    varying.
    """
    target = Language.MARATHI if language == Language.ENGLISH else Language.ENGLISH
    return [
        TermMapping(
            source_term="sanctioned intake",
            source_language=language,
            target_term=("मंजूर प्रवेश क्षमता"
                         if target == Language.MARATHI else "sanctioned intake"),
            consistent_with_corpus=True,
            note="STUB RESULT",
        )
    ]


def is_configured() -> bool:
    """Whether an API key is present. Surfaced on /health."""
    return bool(settings.LLM_API_KEY)
