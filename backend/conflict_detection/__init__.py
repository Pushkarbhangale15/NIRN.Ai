import logging
import re
from typing import List, Optional

import retrieval
from config import settings

from .models import ClauseRetrievalTrace, ConflictReportItem, RetrievalCandidateTrace
from .rule_engine import check_deterministic_conflicts, _RULES_CONFIG
from .llm_verifier import verify_conflict_with_llm

logger = logging.getLogger("nirn.conflict_detection")

# Categories whose existing rules_config.json keyword lists double as a cheap signal for
# "this clause is likely high-value" when picking which clauses get the limited LLM budget
# (see _priority_score below). Read-only reuse of rule_engine's already-loaded config --
# no new keyword data, no change to rule_engine.py itself.
_PRIORITY_RULE_CATEGORIES = [
    "Funding Conflict",
    "Authority Conflict",
    "Timeline Conflict",
    "Committee Conflict",
    "Legal Reference Conflict",
]

# Standard Maharashtra GR section markers (see prompts.py's COPILOT_DRAFT template for the
# canonical form every GR in this system follows).
#
# Splitting the WHOLE document on numbered-line boundaries (the old approach) doesn't work:
# citation lists ("Read:"/"वाचा:") and copy-to lists ("Copy to:"/"प्रत,") are ALSO numbered by
# convention, so they get mistaken for operative directives. Worse, when the real operative
# content is a single unnumbered paragraph (common -- not every GR itemizes into 01./02./03.),
# it has no boundary separating it from the numbered citation/copy-to text next to it, so it gets
# merged into one giant "clause" alongside them. Confirmed directly on a real draft: the entire
# substantive paragraph (naming three departments whose approval it was bypassing) got silently
# dropped because it shared a merged clause with the Governor's-order sign-off, and every
# resulting "clause" the pipeline actually analyzed was citation/copy-to noise instead.
#
# Fix: isolate the operative section by its start/end markers FIRST, then split for numbered
# sub-clauses only within that isolated region -- so citation and copy-to text, which live
# outside the markers, are never in scope in the first place. If the isolated body has no
# internal numbering, it's kept whole as a single clause rather than being lost.
_OPERATIVE_START_MARKERS = ["Government Resolution:", "शासन परिपत्रक:", "शासन निर्णय:"]
_SIGNOFF_MARKERS = [
    "महाराष्ट्राचे राज्यपाल यांच्या आदेशानुसार",
    "By order and in the name of the Governor",
]


def _extract_operative_clauses(body_text: str) -> List[str]:
    start_idx = 0
    for marker in _OPERATIVE_START_MARKERS:
        idx = body_text.find(marker)
        if idx != -1:
            start_idx = idx + len(marker)
            break

    end_idx = len(body_text)
    for marker in _SIGNOFF_MARKERS:
        idx = body_text.find(marker, start_idx)
        if idx != -1:
            end_idx = min(end_idx, idx)

    operative_body = body_text[start_idx:end_idx].strip()
    if not operative_body:
        return []

    parts = re.split(r"\n\s*(?=(?:\d+|[०-९]+)[.)]\s)", operative_body)
    clauses = [p.strip() for p in parts if len(p.strip()) > 40]
    return clauses or [operative_body]


# Jurisdiction-sensitive keyword triggers: when a clause mentions one of these, that department's
# candidates are guaranteed to be considered via search_within_department(), not left to chance
# in the unscoped top-K. Needed because a clause's phrasing can structurally resemble a different
# department's boilerplate more closely than the substantively responsible department's own
# writing style -- confirmed directly: a clause about using forest land returned zero Revenue &
# Forest Department hits in the top 30 unscoped results, despite that department holding 248k+
# highly relevant chunks. Seeded with the proven case; add more as they're found.
#
# NOTE: Marathi keywords use short, inflection-invariant stems rather than full nominative
# words. "वनजमीन" (forest land, nominative) never appears as a literal substring of the inflected
# form actually used in real GR text, e.g. "वनजमिनींपैकी" -- the vowel matra on the middle
# syllable changes (ी vs ि) between forms. The stem "वनजम" (the 4 characters before that matra)
# is common to every inflected form and was confirmed to match correctly where the full word
# didn't. Same reasoning applies to "जमिन" (land) as a fallback vs. "जमीन".
JURISDICTION_KEYWORD_DEPARTMENTS = {
    "Revenue_and_Forest_Department": [
        "वनजम", "वन विभाग", "गायरान", "महसूल", "जमिन",
        "forest land", "revenue department", "land diversion", "land allotment",
    ],
    "General_Administration_Department": [
        "प्रशासकीय मान्यता", "सामान्य प्रशासन",
        "general administration department", "administrative approval",
    ],
    "Finance_Department": [
        "वित्त विभाग", "आर्थिक मान्यता",
        "finance department", "financial concurrence", "tender approval",
    ],
}


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# Generic administrative/procedural boilerplate that appears near-identically
# across nearly every GR regardless of subject matter -- standard fund
# disbursement steps, committee-evaluation process, standard eligibility
# determination, standard budget-discipline closing language. Confirmed
# directly: a clause built almost entirely from this boilerplate (with only
# an incidental budget figure attached) surfaced as a "Critical" funding
# conflict against two completely unrelated GRs (afforestation funding,
# tribal welfare fund utilization) purely because the procedural phrasing is
# near-identical corpus-wide -- retrieval was matching on boilerplate
# structure, not policy substance. A clause is classified boilerplate (and
# excluded from retrieval/LLM verification entirely -- see
# detect_cross_department_conflicts below) only when it matches at least
# _BOILERPLATE_MIN_HITS of these markers, so a clause that merely mentions
# one of these phrases in passing alongside real substantive content isn't
# over-filtered.
_BOILERPLATE_CLAUSE_PATTERNS = [
    r"निधी वितरणाची कार्यपद्धती",
    r"fund disbursement procedure",
    r"प्रस्ताव सादर करणे आवश्यक",
    r"submit(?:s|ted)?\s+(?:a|the)\s+proposal",
    r"समितीद्वारे[^.]{0,25}मूल्यांकन",
    r"committee\s+(?:shall|will)\s+evaluate",
    r"अनुदानास पात्र ठरवले जाईल",
    r"eligible\s+for\s+the\s+grant",
    r"मंजूर निधीपेक्षा जास्त खर्च होणार नाही",
    r"expenditure\s+shall\s+not\s+exceed\s+the\s+approved",
    r"अंमलबजावणीचा कालमर्यादा",
    r"सदर शासन निर्णयानुसार अंमलबजावणी करण्यात यावी",
]
_BOILERPLATE_CLAUSE_RE = re.compile(
    "|".join(_BOILERPLATE_CLAUSE_PATTERNS), re.IGNORECASE | re.UNICODE
)
_BOILERPLATE_MIN_HITS = 2


def _is_boilerplate_clause(clause: str) -> bool:
    return len(_BOILERPLATE_CLAUSE_RE.findall(clause)) >= _BOILERPLATE_MIN_HITS


def _jurisdiction_hits_for(clause: str) -> List[tuple]:
    """
    Returns (department, focused_query) pairs -- one per triggered department, using the
    specific SENTENCE that mentions it as the query rather than the whole clause.

    A long clause's embedding is dominated by its majority content, which can drown out a single
    department mention elsewhere in the same clause: confirmed directly on a real draft, where
    the full 630-char procurement clause returned zero General Administration / Finance
    Department hits even fetching 500 candidates, while just the one sentence naming them
    ("...shall not require prior administrative approval from the General Administration
    Department, financial concurrence from the Finance Department...") returned hundreds from
    both. Falls back to the whole clause if sentence splitting finds no match (e.g. the keyword
    and the clause are already short/coextensive).
    """
    sentences = _SENTENCE_SPLIT_RE.split(clause)
    hits = []
    for dept, keywords in JURISDICTION_KEYWORD_DEPARTMENTS.items():
        match = None
        for sentence in sentences:
            lower = sentence.lower()
            if any(kw.lower() in lower for kw in keywords):
                match = sentence.strip()
                break
        if match is None and any(kw.lower() in clause.lower() for kw in keywords):
            match = clause
        if match:
            hits.append((dept, match))
    return hits


def _priority_score(clause: str) -> int:
    """
    Presence-count score (0-6), used only to pick which clauses get the limited LLM
    verification budget -- deliberately NOT a frequency count, so a clause repeating one
    keyword several times doesn't outrank a clause touching two different high-value
    categories once each. Reuses keyword lists already loaded for the rule engine
    (_RULES_CONFIG) and the existing jurisdiction-detection helper -- no new keyword data.
    """
    lower = clause.lower()
    categories = _RULES_CONFIG.get("categories", {})
    score = 0
    for category_name in _PRIORITY_RULE_CATEGORIES:
        keywords = categories.get(category_name, {}).get("keywords", [])
        if any(kw.lower() in lower for kw in keywords):
            score += 1
    if _jurisdiction_hits_for(clause):
        score += 1
    return score


def detect_cross_department_conflicts(
    body_text: str,
    draft_language: Optional[str] = None,
    trace: Optional[List[ClauseRetrievalTrace]] = None,
) -> List[ConflictReportItem]:
    """
    Two-stage pipeline to detect policy, funding, authority, timeline, and operational
    conflicts between the draft GR text and existing GRs in the corpus.

    1. Isolates the operative section and splits it into clauses (see _extract_operative_clauses).
    2. Retrieves Top-K similar clauses from the vector DB, plus a guaranteed pass over any
       jurisdiction-sensitive department a clause's keywords point to.
    3. Runs Rule Engine for deterministic matches.
    4. Runs LLM Verification Layer for remaining semantic/ambiguous relations.

    draft_language: 'mr' or 'en'. Passed through to retrieval.search() so Marathi drafts get
    the language-matching score boost toward Marathi corpus chunks.

    trace: optional list to append a ClauseRetrievalTrace to for every extracted clause
    (including boilerplate-skipped ones and clauses outside the LLM budget) -- observability
    only, does not change return value/type or any retrieval/filtering behavior. Pass a list
    to opt in; existing callers that don't pass one are completely unaffected.
    """
    clauses = _extract_operative_clauses(body_text)
    if not clauses:
        return []

    conflicts: List[ConflictReportItem] = []

    # MAX_CLAUSES_FOR_LLM is now a safety ceiling (see config.py), not a
    # coverage budget -- every clause is LLM-eligible unless a draft is
    # pathologically large. Ranked by _priority_score purely to decide WHICH
    # clauses get dropped in that rare case (ties broken by document order),
    # not to pick "the 2 that matter" out of a normal-sized draft anymore.
    if len(clauses) > settings.MAX_CLAUSES_FOR_LLM:
        logger.warning(
            "Draft has %d operative clauses, exceeding MAX_CLAUSES_FOR_LLM safety "
            "ceiling (%d) -- %d clause(s) will only get rule-engine coverage, not "
            "LLM verification. This is the same coverage gap the ceiling exists to "
            "prevent unbounded LLM calls for; consider raising the ceiling if this "
            "draft size is expected to recur.",
            len(clauses), settings.MAX_CLAUSES_FOR_LLM,
            len(clauses) - settings.MAX_CLAUSES_FOR_LLM,
        )
    llm_eligible_indices = set(
        sorted(range(len(clauses)), key=lambda i: (-_priority_score(clauses[i]), i))[
            :settings.MAX_CLAUSES_FOR_LLM
        ]
    )

    # Process every extracted clause: the deterministic rule engine (cheap,
    # local, no LLM call) covers all of them, and so does the LLM stage now
    # that MAX_CLAUSES_FOR_LLM is a safety ceiling rather than a fixed budget
    # (see above) -- LLM-call volume scales with actual clause count instead
    # of being flat-capped at a small constant.
    for clause_index, clause in enumerate(clauses):
        # Boilerplate clauses (generic fund-disbursement procedure, committee
        # evaluation process, standard closing formula) are excluded from
        # candidate search entirely -- see _is_boilerplate_clause above. This
        # is the fix, not a downstream verdict downgrade: these clauses
        # should never reach retrieval or the LLM in the first place, so
        # there's nothing left for a downgrade rule to be inconsistent
        # about.
        if _is_boilerplate_clause(clause):
            if trace is not None:
                trace.append(ClauseRetrievalTrace(
                    clause_index=clause_index,
                    clause_preview=clause[:120],
                    boilerplate_skipped=True,
                    llm_eligible_clause=clause_index in llm_eligible_indices,
                    top_k=settings.RULE_ENGINE_CANDIDATES_PER_CLAUSE,
                    candidates_per_clause_budget=settings.CANDIDATES_PER_CLAUSE,
                    candidates_returned=0,
                    candidates=[],
                ))
            continue

        # Single retrieval call, fetched wide (RULE_ENGINE_CANDIDATES_PER_CLAUSE) so the rule
        # engine gets a bigger pool -- no second/duplicate retrieval call for a "narrow" pool.
        # retrieval.search() already returns results sorted by score descending, so the top
        # CANDIDATES_PER_CLAUSE of this same list is exactly what a separate narrow call would
        # have returned; slicing it here keeps LLM-call volume unchanged from before this pool
        # was widened.
        candidates = retrieval.search(
            clause, top_k=settings.RULE_ENGINE_CANDIDATES_PER_CLAUSE, draft_language=draft_language
        )
        llm_eligible_keys = {
            (h.gr_id, h.snippet) for h in candidates[:settings.CANDIDATES_PER_CLAUSE]
        }

        # Guarantee coverage for jurisdiction-sensitive departments the unscoped search might
        # have missed entirely (see JURISDICTION_KEYWORD_DEPARTMENTS above). These hits were
        # already LLM-eligible before this step and remain so -- unchanged.
        seen_keys = {(h.gr_id, h.snippet) for h in candidates}
        jurisdiction_keys = set()
        for department, focused_query in _jurisdiction_hits_for(clause):
            for hit in retrieval.search_within_department(focused_query, department, top_k=2):
                key = (hit.gr_id, hit.snippet)
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append(hit)
                    llm_eligible_keys.add(key)
                jurisdiction_keys.add(key)

        clause_is_llm_eligible = clause_index in llm_eligible_indices
        candidate_traces: List[RetrievalCandidateTrace] = []

        for hit in candidates:
            # Stage 1: Deterministic Rule Engine
            det_conflict = check_deterministic_conflicts(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet,
                matched_gr_date=hit.issued_on,
                matched_department=hit.department,
                source_url=hit.source_url,
            )

            key = (hit.gr_id, hit.snippet)
            # Stage 2 eligibility -- gated on BOTH:
            # (a) clause_index in llm_eligible_indices (MAX_CLAUSES_FOR_LLM budget, Step 2), and
            # (b) this hit being in llm_eligible_keys (top CANDIDATES_PER_CLAUSE of the widened
            #     pool, or a jurisdiction hit) -- so the wider RULE_ENGINE_CANDIDATES_PER_CLAUSE
            #     pool never reaches the LLM beyond what CANDIDATES_PER_CLAUSE already allowed.
            # An LLM call only actually happens if the rule engine didn't already resolve it.
            would_be_llm_eligible = clause_is_llm_eligible and key in llm_eligible_keys
            reached_llm = would_be_llm_eligible and not det_conflict

            if trace is not None:
                candidate_traces.append(RetrievalCandidateTrace(
                    gr_id=hit.gr_id,
                    department=hit.department,
                    score=hit.score,
                    source="jurisdiction" if key in jurisdiction_keys else "top_k",
                    reached_llm=reached_llm,
                    rule_engine_result="conflict" if det_conflict else "no_conflict",
                ))

            if det_conflict:
                conflicts.append(det_conflict)
                continue

            if not would_be_llm_eligible:
                continue

            llm_conflict = verify_conflict_with_llm(
                draft_clause=clause,
                matched_gr_id=hit.gr_id,
                matched_gr_title=hit.title,
                matched_clause=hit.snippet,
                matched_gr_date=hit.issued_on,
                cited_references=hit.cited_references,
                matched_department=hit.department,
                source_url=hit.source_url,
            )

            if llm_conflict:
                conflicts.append(llm_conflict)

        if trace is not None:
            trace.append(ClauseRetrievalTrace(
                clause_index=clause_index,
                clause_preview=clause[:120],
                boilerplate_skipped=False,
                llm_eligible_clause=clause_is_llm_eligible,
                top_k=settings.RULE_ENGINE_CANDIDATES_PER_CLAUSE,
                candidates_per_clause_budget=settings.CANDIDATES_PER_CLAUSE,
                candidates_returned=len(candidates),
                candidates=candidate_traces,
            ))

    return conflicts
