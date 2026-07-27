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
