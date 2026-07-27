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

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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


class TermMapping(BaseModel):
    """Objective 2: a legal term and its approved equivalent."""
    source_term: str
    source_language: Language
    target_term: str
    consistent_with_corpus: bool = True
    note: Optional[str] = None


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


# ---------------------------------------------------------------------
# Copilot / Chat
# ---------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    references: List[CorpusHit] = []
    follow_up_suggestions: List[str] = []

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
