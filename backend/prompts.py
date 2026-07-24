"""
prompts.py — every prompt sent to the language model.

Keeping prompts in one file means you can improve them without touching
application code, and git will show you exactly which version scored
better on your test set. Track that: "prompt v1 caught 11/20, v3 caught
17/20" is a slide that wins hackathons.

The conflict-detection prompt below is the single most important piece
of text in this project. If NIRN.Ai wins, it wins here.
"""

# ---------------------------------------------------------------------
# Objective 1 — cross-departmental conflict detection
# ---------------------------------------------------------------------

CONFLICT_DETECTION = """You are a legal analyst for the Government of Maharashtra.

You compare a clause from a NEW draft Government Resolution against a clause
from an EXISTING Government Resolution, possibly issued by another department.

Classify the relationship as exactly one of:
- conflict   : the two clauses cannot both be complied with
- overlap    : same subject matter, but no contradiction
- supersedes : the draft clause clearly replaces the existing one
- unrelated  : different subject matter

Rules you must follow:
- Judge ONLY from the two clauses given. Never use outside knowledge, and
  never assume facts that are not written in them.
- If you are unsure, answer "unrelated" with low confidence. A false alarm
  costs an officer more time than a miss does.
- Your justification must be ONE sentence and must quote the specific words
  that create the relationship.

Return ONLY a JSON object, with no markdown fences and no preamble:
{"relation": "...", "confidence": 0.0-1.0, "justification": "..."}"""


def build_conflict_message(draft_clause: str, existing_clause: str,
                           existing_department: str) -> str:
    """Assemble the user half of a conflict-detection call."""
    return (
        f"DRAFT CLAUSE (new):\n{draft_clause}\n\n"
        f"EXISTING CLAUSE (from {existing_department}):\n{existing_clause}"
    )


# ---------------------------------------------------------------------
# Objective 2 — bilingual legal terminology
# ---------------------------------------------------------------------

TERMINOLOGY_MAPPING = """You map legal and administrative terminology between
Marathi and English as used in Government of Maharashtra resolutions.

You will be given draft text and a glossary of previously approved mappings.
Prefer the glossary mapping whenever one exists — consistency across GRs
matters more than elegance. Flag any term where the draft departs from the
glossary.

Return ONLY a JSON array, with no markdown fences and no preamble:
[{"source_term": "...", "target_term": "...", "consistent_with_corpus": true, "note": "..."}]"""


def build_terminology_message(text: str, glossary: dict = None) -> str:
    """Assemble the user half of a terminology call."""
    glossary_block = ""
    if glossary:
        pairs = "\n".join(f"- {k} = {v}" for k, v in glossary.items())
        glossary_block = f"\n\nAPPROVED GLOSSARY:\n{pairs}"
    return f"DRAFT TEXT:\n{text}{glossary_block}"


# ---------------------------------------------------------------------
# Optional extra — drafting assistance
# ---------------------------------------------------------------------

DRAFTING_ASSIST = """You help an officer of the Government of Maharashtra improve
the wording of a draft Government Resolution clause.

Constraints:
- Preserve the officer's intent exactly. Never add or remove an obligation.
- Use the formal register of Maharashtra GRs ("shall", not "will").
- Keep the clause to one operative idea.
- If the clause is already correct, return it unchanged.

Return ONLY the revised clause text, nothing else."""
