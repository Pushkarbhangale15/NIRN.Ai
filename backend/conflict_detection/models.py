from pydantic import BaseModel, Field
from typing import List, Optional

class ConflictReportItem(BaseModel):
    draft_clause: str = Field(..., description="The clause from the draft GR being checked.")
    matched_gr: str = Field(..., description="The reference ID/No of the conflicting GR.")
    matched_clause: str = Field(..., description="The conflicting clause from the existing GR.")
    conflict: bool = Field(True, description="True if a conflict was detected.")
    category: str = Field(..., description="The category of the conflict (e.g. Funding Conflict).")
    severity: str = Field(..., description="Severity of the conflict (Low, Medium, High, Critical).")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    reason: str = Field(..., description="Detailed explanation of the contradiction.")
    recommendation: str = Field(..., description="Actionable recommendation to resolve the conflict.")
    detected_by: Optional[str] = Field(
        default=None, description="'rule_engine' or 'llm_verifier' — which stage found this."
    )
    draft_clause_index: Optional[int] = Field(
        default=None, description="0-based ordinal of the matched clause in the draft."
    )
    draft_clause_ref: Optional[str] = Field(
        default=None, description="Human clause label in OUR draft, e.g. 'Clause 4(b)'. None if unparseable."
    )
    source_clause_ref: Optional[str] = Field(
        default=None, description="Human clause label in the EXISTING GR. None if unparseable."
    )
    source_gr_title: Optional[str] = Field(default=None, description="Title of the existing GR, from the FAISS chunk.")
    source_gr_date: Optional[str] = Field(
        default=None, description="Raw issued_on string from the FAISS chunk metadata, if any."
    )
