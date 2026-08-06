from pydantic import BaseModel, Field
from typing import List, Optional

class ConflictReportItem(BaseModel):
    draft_clause: str = Field(..., description="The clause from the draft GR being checked.")
    matched_gr: str = Field(..., description="Human-readable label: GR id, title, and date.")
    matched_clause: str = Field(..., description="The conflicting clause from the existing GR.")
    conflict: bool = Field(True, description="True if a conflict was detected.")
    category: str = Field(..., description="The category of the conflict (e.g. Funding Conflict).")
    severity: str = Field(..., description="Severity of the conflict (Low, Medium, High, Critical).")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    reason: str = Field(..., description="Detailed explanation of the contradiction.")
    recommendation: str = Field(..., description="Actionable recommendation to resolve the conflict.")
    relation: str = Field(
        default="conflict",
        description=(
            "'conflict' or 'overlap'. Set to 'overlap' by deterministic post-processing "
            "when the model itself reports no beneficiary overlap and no scope overlap, "
            "regardless of the raw verdict it initially assigned."
        ),
    )
    beneficiary_match: Optional[bool] = Field(
        default=None, description="Whether the draft and matched clause target the same beneficiary."
    )
    scope_match: Optional[bool] = Field(
        default=None, description="Whether the draft and matched clause cover the same scope/jurisdiction."
    )

    # Structured fields (in addition to the human-readable matched_gr label above) so callers
    # like routes.py can convert this into schemas.ConflictHit without re-parsing matched_gr.
    existing_gr_id: str = Field(default="", description="GR id of the matched existing clause.")
    existing_gr_title: str = Field(default="", description="Title of the matched existing GR.")
    existing_department: str = Field(default="", description="Department that issued the matched GR.")
    source_url: Optional[str] = Field(default=None, description="Official source URL of the matched GR.")


# ---------------------------------------------------------------------------
# Retrieval observability -- see detect_cross_department_conflicts(trace=...).
# Distinct from ConflictReportItem: this exists for EVERY clause/candidate
# examined, whether or not it produced a conflict, so a "0 conflicts" result
# can be told apart from "no relevant candidates were ever retrieved."
# ---------------------------------------------------------------------------

class RetrievalCandidateTrace(BaseModel):
    gr_id: str
    department: str
    score: float = Field(..., description="retrieval.search()'s similarity score, 0.0-1.0.")
    source: str = Field(..., description="'top_k' (ordinary ranked retrieval) or 'jurisdiction' "
                                          "(guaranteed pass for a department the clause's keywords named).")
    reached_llm: bool = Field(..., description="Whether this candidate was within CANDIDATES_PER_CLAUSE "
                                                "(or a jurisdiction hit) AND its clause was within the "
                                                "MAX_CLAUSES_FOR_LLM budget -- i.e. an LLM call was made for it.")
    rule_engine_result: str = Field(..., description="'conflict' or 'no_conflict' -- the deterministic "
                                                        "rule engine runs on every candidate unconditionally.")


class ClauseRetrievalTrace(BaseModel):
    clause_index: int
    clause_preview: str = Field(..., description="First ~120 chars of the clause, for identification.")
    boilerplate_skipped: bool = Field(
        default=False,
        description="True if this clause was classified as procedural boilerplate and excluded from "
                    "retrieval entirely -- candidates/top_k below are meaningless (never searched) when true.",
    )
    llm_eligible_clause: bool = Field(
        ..., description="Whether this clause was within the MAX_CLAUSES_FOR_LLM priority-ranked budget "
                          "for the draft -- if false, only the rule engine ever examined this clause's "
                          "candidates, regardless of their score."
    )
    top_k: int = Field(..., description="RULE_ENGINE_CANDIDATES_PER_CLAUSE value used for this clause's search.")
    candidates_per_clause_budget: int = Field(..., description="CANDIDATES_PER_CLAUSE -- how many of the "
                                                                  "top_k candidates were LLM-eligible by rank.")
    candidates_returned: int = Field(..., description="Actual candidate count returned -- may be less than "
                                                         "top_k if the index has few relevant entries.")
    candidates: List[RetrievalCandidateTrace] = Field(default_factory=list)
