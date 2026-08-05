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
