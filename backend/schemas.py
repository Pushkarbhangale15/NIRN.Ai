"""
schemas.py — the API contract.

Every request and response shape in NIRN.Ai is defined here. Pydantic
validates incoming JSON automatically, and FastAPI turns these classes
into the interactive documentation at /docs.

THIS IS THE MOST IMPORTANT FILE IN THE PROJECT ON DAY 1.
Once these shapes are agreed, the frontend and the retrieval layer can
be built in parallel without either waiting on the other. Changing a
field here breaks someone else's work, so change deliberately and tell
the team.
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------
# Enums — fixed sets of allowed values.
# Using these instead of plain strings means a typo is caught by the
# API rather than silently producing a broken UI state.
# ---------------------------------------------------------------------

class Language(str, Enum):
    ENGLISH = "en"
    MARATHI = "mr"


class Severity(str, Enum):
    ERROR = "error"        # violates the Manual of Office Procedure
    WARNING = "warning"    # probably wrong, needs a human look
    INFO = "info"          # stylistic suggestion


class Relation(str, Enum):
    CONFLICT = "conflict"       # the two clauses cannot both be complied with
    OVERLAP = "overlap"         # same subject matter, no contradiction
    SUPERSEDES = "supersedes"   # the draft clause replaces the existing one
    UNRELATED = "unrelated"


class GRStatus(str, Enum):
    IN_FORCE = "in_force"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------

class DraftCreate(BaseModel):
    """What the frontend POSTs when an officer submits a draft GR."""
    title: str = Field(..., min_length=3,
                       examples=["Revision of lateral entry intake"])
    department: str = Field(...,
                            examples=["Higher and Technical Education Department"])
    body_text: str = Field(..., min_length=20)
    language: Language = Language.ENGLISH


class Draft(DraftCreate):
    """A stored draft: everything above, plus server-assigned fields."""
    id: str
    created_at: datetime
    gr_number: Optional[str] = None
    """Provisional/internal number (NIRN/<DEPT>/<YYYY>/<seq>) — NOT a
    real government-issued GR number. Label it as such in the UI."""


class DraftUpdate(BaseModel):
    """
    Payload for PATCH /api/drafts/{draft_id}. body_text now carries the
    editor's current HTML (Task 5c: "commits the current editor HTML");
    the previous content is snapshotted into draft_versions before the
    overwrite, so this field's minimum length is looser than the
    original full-GR-body constraint.
    """
    body_text: str = Field(..., min_length=1, max_length=200_000)
    content_plain: Optional[str] = Field(None, max_length=200_000)
    change_note: Optional[str] = Field(None, max_length=400)


# ---------------------------------------------------------------------
# Analysis results — one shape per hackathon objective
# ---------------------------------------------------------------------

class TemplateIssue(BaseModel):
    """Objective 4: a violation of the Manual of Office Procedure."""
    rule_id: str = Field(..., examples=["MOP-001"])
    severity: Severity
    message: str
    section: Optional[str] = None
    suggestion: Optional[str] = None


class ReferenceHit(BaseModel):
    """Objective 3: a citation to another GR found inside the draft."""
    raw_text: str = Field(..., examples=["GR No CTC-2019/Pr.Kra.252/TE-04"])
    gr_number: Optional[str] = None
    year: Optional[int] = None
    char_offset: int = 0          # position in the draft, for highlighting
    found_in_corpus: bool = False
    status: GRStatus = GRStatus.UNKNOWN
    corpus_gr_id: Optional[str] = None
    corpus_title: Optional[str] = None


class ConflictHit(BaseModel):
    """Objective 1: a draft clause that clashes with an existing GR."""
    conflict_id: Optional[uuid.UUID] = None
    draft_clause: str
    existing_gr_id: str
    existing_gr_title: str
    existing_department: str
    existing_clause: str
    relation: Relation
    confidence: float = Field(..., ge=0.0, le=1.0)
    justification: str
    source_url: Optional[str] = None
    conflict_type: Optional[str] = "Policy Conflict"
    severity: Optional[str] = "High"
    resolution_status: str = "not_attempted"
    resolved_clause_text: Optional[str] = None
    source_ocr_low_confidence: bool = False
    is_dismissed: bool = False
    dismissed_reason: Optional[str] = None


class TermMapping(BaseModel):
    """Objective 2: a legal term and its approved equivalent."""
    source_term: str
    source_language: Language
    target_term: str
    consistent_with_corpus: bool = True
    note: Optional[str] = None
    english_term: Optional[str] = None
    marathi_term: Optional[str] = None
    definition: Optional[str] = None



class AnalysisSummary(BaseModel):
    """Headline numbers. These drive the dashboard cards on the main screen."""
    template_error_count: int = 0
    template_warning_count: int = 0
    reference_count: int = 0
    unresolved_reference_count: int = 0
    conflict_count: int = 0
    highest_conflict_confidence: float = 0.0
    overall_status: str = "needs_review"   # clean | needs_review | blocked


class AnalysisReport(BaseModel):
    """Full response of POST /api/analysis/{draft_id}."""
    draft_id: str
    generated_at: datetime
    summary: AnalysisSummary
    template_issues: List[TemplateIssue] = []
    references: List[ReferenceHit] = []
    conflicts: List[ConflictHit] = []
    terms: List[TermMapping] = []


# ---------------------------------------------------------------------
# Corpus search
# ---------------------------------------------------------------------

class CorpusHit(BaseModel):
    """One result from semantic search over the GR corpus."""
    gr_id: str
    title: str
    department: str
    issued_on: Optional[str] = None
    snippet: str
    score: float = Field(..., ge=0.0, le=1.0)
    source_url: Optional[str] = None
    gr_number: Optional[str] = None
    cited_references: List[str] = []


class CorpusSearchResponse(BaseModel):
    query: str
    hits: List[CorpusHit]
    took_ms: int

class FullOCRResponse(BaseModel):
    gr_id: str
    department: str
    title: str
    text: str

class OfficialSourceResponse(BaseModel):
    status: str
    url: Optional[str] = None


class DraftGenerateRequest(BaseModel):
    prompt: str
    language: str = "english"
    department: Optional[str] = None

class DraftGenerateResponse(BaseModel):
    draft_id: str
    title: str
    department: str
    body_text: str
    references: List[CorpusHit] = []
    gr_number: Optional[str] = None
    language: Optional[str] = None

class ComparisonRequest(BaseModel):
    gr_id_1: str
    gr_id_2: str

class ComparisonResponse(BaseModel):
    gr_id_1: str
    gr_id_2: str
    comparison_report: str

class ClauseExplanationRequest(BaseModel):
    clause_text: str
    language: Language = Language.ENGLISH

class ClauseExplanationResponse(BaseModel):
    explanation: str


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    vector_db_connected: bool
    llm_configured: bool


class HealthDbResponse(BaseModel):
    status: str
    connected: bool
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------
# Auth / Officers
#
# Validation lives here, at the API boundary, before anything reaches
# the database — see backend/README.md, "SQL injection prevention".
# login_id is restricted to a safe character set; passwords have a
# minimum length; role is a closed enum, never a free string.
# ---------------------------------------------------------------------

LoginId = Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
NewPassword = Annotated[str, Field(min_length=10, max_length=128)]


class OfficerRoleEnum(str, Enum):
    OFFICER = "officer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class LoginRequest(BaseModel):
    login_id: LoginId
    password: Annotated[str, Field(min_length=1, max_length=128)]


class OfficerOut(BaseModel):
    """Never includes password_hash. Serialise from the ORM model via
    model_validate() — never hand the ORM model to the client directly."""
    model_config = ConfigDict(from_attributes=True)

    officer_id: uuid.UUID
    name: str
    login_id: str
    department: Optional[str] = None
    designation: Optional[str] = None
    role: OfficerRoleEnum
    is_active: bool
    must_change_password: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer: OfficerOut


class OfficerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    login_id: LoginId
    password: NewPassword
    department: Optional[str] = Field(None, max_length=160)
    designation: Optional[str] = Field(None, max_length=120)
    role: OfficerRoleEnum = OfficerRoleEnum.OFFICER


class OfficerUpdate(BaseModel):
    """login_id is immutable after creation — deliberately absent here."""
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    department: Optional[str] = Field(None, max_length=160)
    designation: Optional[str] = Field(None, max_length=120)
    role: Optional[OfficerRoleEnum] = None


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: NewPassword


class ResetPasswordResponse(BaseModel):
    """The generated password is shown to the admin exactly once."""
    officer_id: uuid.UUID
    new_password: str


class PaginatedOfficers(BaseModel):
    items: List[OfficerOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------
# Draft history, conflicts, references (Task 6) + admin draft views
# ---------------------------------------------------------------------

class DraftStatusEnum(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    FINALISED = "finalised"
    ARCHIVED = "archived"


class ConflictSeverityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_id: uuid.UUID
    conflict_ref: str
    source_of_conflict: str
    conflicting_text: str
    draft_excerpt: Optional[str] = None
    draft_clause_ref: Optional[str] = None
    source_clause_ref: Optional[str] = None
    conflicting_gr_id: Optional[str] = None
    source_gr_title: Optional[str] = None
    source_gr_date: Optional[date] = None
    severity: ConflictSeverityEnum
    justification: str
    detected_by: str
    is_dismissed: bool
    dismissed_reason: Optional[str] = None
    is_resolved: bool = False
    resolved_reason: Optional[str] = None
    resolution_status: str = "not_attempted"
    resolved_clause_text: Optional[str] = None
    source_ocr_low_confidence: bool = False
    created_at: datetime


class DraftReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference_id: uuid.UUID
    reference_text: str
    extracted_gr_number: Optional[str] = None
    reference_date: Optional[date] = None
    script: str
    resolved: bool


class DraftHistoryItem(BaseModel):
    generated_draft_id: uuid.UUID
    gr_number: Optional[str] = None
    title: str
    department: str
    language: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    unresolved_conflict_count: int


class PaginatedDraftHistory(BaseModel):
    items: List[DraftHistoryItem]
    total: int
    page: int
    page_size: int


class GeneratedDraftDetail(BaseModel):
    generated_draft_id: uuid.UUID
    gr_number: Optional[str] = None
    title: str
    department: str
    language: str
    status: str
    version: int
    content: str
    content_plain: Optional[str] = None
    brief: Optional[str] = None
    drafted_by: uuid.UUID
    drafted_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    conflicts: List[ConflictOut] = []
    references: List[DraftReferenceOut] = []


class DismissConflictRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


class ResolutionStrategy(str, Enum):
    REWORD = "reword"                    # rephrase the clause to remove the overlap
    ADD_CITATION = "add_citation"        # cite the existing GR explicitly
    ADD_CARVE_OUT = "add_carve_out"      # exclude the overlapping scope explicitly
    DEFER_TO_EXISTING = "defer_to_existing"  # subordinate this clause to the existing GR


class ResolveConflictRequest(BaseModel):
    strategy: ResolutionStrategy


class ReverificationResult(BaseModel):
    """Result of re-running the single revised clause through the conflict checker."""
    conflict: bool
    relation: Relation
    severity: Optional[str] = None
    confidence: Optional[float] = None
    justification: Optional[str] = None


class ResolveConflictResponse(BaseModel):
    conflict_id: uuid.UUID
    strategy: ResolutionStrategy
    original_clause: str
    revised_clause: str
    diff: str
    reverification: ReverificationResult
    cleared: bool
    still_conflicting_reason: Optional[str] = None


class AcceptConflictResolutionRequest(BaseModel):
    revised_clause: str = Field(..., min_length=1, max_length=20_000)


class AcceptConflictResolutionResponse(BaseModel):
    conflict: ConflictOut
    draft_id: uuid.UUID
    draft_version: int


class MarkResolvedRequest(BaseModel):
    revised_clause: str = Field(..., min_length=1, max_length=20_000)


class MarkResolvedResponse(BaseModel):
    conflict: ConflictOut


class ExportDocxRequest(BaseModel):
    draft_id: uuid.UUID


class AdminSummaryCounts(BaseModel):
    total_drafts: int
    total_unresolved_conflicts: int
    active_officers: int
    drafts_last_7_days: int


# ---------------------------------------------------------------------
# Scanned GR upload / OCR ingestion
# ---------------------------------------------------------------------

class GrUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    upload_id: uuid.UUID
    status: str
    original_filename: str
    file_type: str
    extracted_metadata: Optional[dict] = None
    block_confidences: Optional[List[dict]] = None
    generated_draft_id: Optional[uuid.UUID] = None
    error_message: Optional[str] = None
    created_at: datetime
