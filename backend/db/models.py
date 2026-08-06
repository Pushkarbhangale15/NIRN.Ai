"""
db/models.py — SQL RULE: this file only defines table shape. No query in
this codebase is ever built from f-strings or string concatenation — see
backend/README.md, "SQL injection prevention". Queries against these
tables live exclusively in db/repositories/*.py.

Five tables:
  officers          — who can log in
  generated_drafts  — one row per draft GR (drafted_by is a FK, RESTRICT
                       on delete: an officer with drafts can't be deleted,
                       only deactivated)
  draft_conflicts    — many rows per draft, one per detected conflict
  draft_references    — many rows per draft, one per extracted citation
  draft_versions     — audit trail: a snapshot before every overwrite
  draft_workflow_events — append-only audit trail for the three-tier
                       draft approval chain (submit/forward/approve/return)

Plus number_counters, a small support table backing the provisional
GR-number / conflict-ref generator (see db/repositories/drafts.py:
next_sequence_value). A plain COUNT(*) + 1 races under concurrent
requests and produces duplicate numbers; this table is updated with a
single atomic INSERT ... ON CONFLICT DO UPDATE ... RETURNING, so two
concurrent requests can never receive the same value.
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class OfficerRole(str, enum.Enum):
    OFFICER = "officer"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class DraftLanguage(str, enum.Enum):
    EN = "en"
    MR = "mr"


class DraftStatus(str, enum.Enum):
    """
    Three-tier approval chain: draft (Drafting Officer writing it) ->
    submitted (Reviewing Officer's queue) -> reviewed (Approving
    Authority's queue) -> approved (final, immutable — see
    db.repositories.drafts.patch_draft_content). 'returned' exists in
    the DB enum for completeness but is not currently persisted as a
    status by the app — a returned draft goes straight back to 'draft'
    with returned_reason set (see db.repositories.drafts.return_draft),
    which is simpler for the officer's own view to react to than a
    transient extra state.
    """
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    RETURNED = "returned"
    ARCHIVED = "archived"


class WorkflowDecision(str, enum.Enum):
    SUBMITTED = "submitted"
    EDITED_AND_FORWARDED = "edited_and_forwarded"
    FORWARDED_UNCHANGED = "forwarded_unchanged"
    ACCEPTED_REVIEWER_VERSION = "accepted_reviewer_version"
    KEPT_ORIGINAL = "kept_original"
    RETURNED = "returned"


class ConflictSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictDetectedBy(str, enum.Enum):
    RULE_ENGINE = "rule_engine"
    LLM_VERIFIER = "llm_verifier"


class ReferenceScript(str, enum.Enum):
    LATIN = "latin"
    DEVANAGARI = "devanagari"


class GrUploadStatus(str, enum.Enum):
    """Lifecycle of a scanned GR upload, tracked independently of
    GeneratedDraft.status since a gr_uploads row exists before any draft
    does (OCR must succeed before there's clean text/department to create
    one with)."""
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    COMPLETE = "complete"
    FAILED = "failed"


def _pg_enum(enum_cls, name: str):
    """
    Plain PgEnum(SomeEnum, name=...) binds the Python member's NAME
    ("ADMIN") by default, not its .value ("admin") — but the Postgres
    enum type (created in the Alembic migration) only has the lowercase
    values. values_callable forces SQLAlchemy to bind .value instead,
    matching what's actually in the database.
    """
    return PgEnum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


def _uuid_pk():
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class Officer(Base):
    __tablename__ = "officers"

    officer_id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    login_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[OfficerRole] = mapped_column(
        _pg_enum(OfficerRole, "officer_role"), nullable=False, default=OfficerRole.OFFICER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    drafts: Mapped[list["GeneratedDraft"]] = relationship(
        back_populates="officer", foreign_keys="GeneratedDraft.drafted_by"
    )


class GeneratedDraft(Base):
    __tablename__ = "generated_drafts"

    generated_draft_id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    language: Mapped[DraftLanguage] = mapped_column(
        _pg_enum(DraftLanguage, "draft_language"), nullable=False
    )
    drafted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("officers.officer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(160), nullable=False)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    gr_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[DraftStatus] = mapped_column(
        _pg_enum(DraftStatus, "draft_status"), nullable=False, default=DraftStatus.DRAFT, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template_score: Mapped[object | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Per-clause retrieval observability (list[ClauseRetrievalTrace], JSON-encoded) --
    # top_k/candidates/scores/LLM-eligibility for the most recent conflict-detection
    # run against this draft, so a "0 conflicts" result is traceable back to
    # "candidates checked and cleared" vs. "nothing relevant was ever retrieved" vs.
    # "candidates were filtered out before reaching the LLM" without re-running
    # detection. Overwritten (not appended) each time analysis re-runs.
    retrieval_trace: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Set when a Reviewing Officer or Approving Authority sends this draft
    # back to the Drafting Officer (POST .../return); surfaced as an amber
    # banner on their Draft/History views. Cleared on the next submit.
    returned_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    officer: Mapped["Officer"] = relationship(back_populates="drafts", foreign_keys=[drafted_by])
    conflicts: Mapped[list["DraftConflict"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )
    references: Mapped[list["DraftReference"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )
    versions: Mapped[list["DraftVersion"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )
    workflow_events: Mapped[list["DraftWorkflowEvent"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan",
        foreign_keys="DraftWorkflowEvent.generated_draft_id",
    )

    __table_args__ = (
        Index("ix_generated_drafts_department_created_at", "department", "created_at"),
    )


class DraftConflict(Base):
    __tablename__ = "draft_conflicts"

    conflict_id: Mapped[uuid.UUID] = _uuid_pk()
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conflict_ref: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    source_of_conflict: Mapped[str] = mapped_column(String(200), nullable=False)
    conflicting_text: Mapped[str] = mapped_column(Text, nullable=False)
    draft_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_clause_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_clause_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflicting_gr_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_gr_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_gr_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    severity: Mapped[ConflictSeverity] = mapped_column(
        _pg_enum(ConflictSeverity, "conflict_severity"), nullable=False, default=ConflictSeverity.MEDIUM
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    detected_by: Mapped[ConflictDetectedBy] = mapped_column(
        _pg_enum(ConflictDetectedBy, "conflict_detected_by"), nullable=False
    )
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Durable per-conflict resolve-attempt state, so a resolved conflict
    # stays resolved across page reloads/re-analysis instead of being
    # recomputed from scratch each time. "not_attempted" | "resolved" |
    # "attempted_still_conflicting" | "attempted_error".
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_attempted")
    resolved_clause_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when this conflict's draft_clause was correlated (see
    # ocr_ingest/pipeline.py) with an OCR block that scored below
    # settings.OCR_CONFIDENCE_THRESHOLD -- lets the frontend flag "this
    # conflict might be a misread, not a real match" distinctly from a
    # normal-confidence one. Always False for typed/pasted drafts.
    source_ocr_low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="conflicts")

    __table_args__ = (
        Index(
            "ix_draft_conflicts_severity_undismissed",
            "severity",
            postgresql_where=(is_dismissed == False),  # noqa: E712
        ),
    )


class DraftReference(Base):
    __tablename__ = "draft_references"

    reference_id: Mapped[uuid.UUID] = _uuid_pk()
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_gr_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    script: Mapped[ReferenceScript] = mapped_column(
        _pg_enum(ReferenceScript, "reference_script"), nullable=False
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="references")


class DraftVersion(Base):
    __tablename__ = "draft_versions"

    version_id: Mapped[uuid.UUID] = _uuid_pk()
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Plain-text mirror of `content`, snapshotted alongside it so the diff
    # engine (diffing.py) can operate on plain text even for historical
    # versions instead of raw HTML tags.
    content_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SHA-256 of `content`, computed server-side at write time
    # (db.integrity.hash_content) — tamper-evidence for the audit trail,
    # never accepted from the client. See GET
    # /api/drafts/{id}/versions/{version_number}/verify.
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    edited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("officers.officer_id", ondelete="RESTRICT"), nullable=False
    )
    change_note: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("generated_draft_id", "version_number", name="uq_draft_versions_draft_number"),
    )


class DraftWorkflowEvent(Base):
    """
    Audit trail for the three-tier approval chain — one row per handoff
    (submit / forward / approve / return). APPEND-ONLY: no code path in
    this codebase ever updates or deletes a row here.

    actor_role is the role the acting officer held AT THE TIME of the
    action — deliberately a plain string snapshot, not a live join to
    officers.role, because a role can change later (e.g. promoted from
    officer to reviewer) and the audit trail must reflect what was true
    when the action happened, not what's true now.
    """

    __tablename__ = "draft_workflow_events"

    event_id: Mapped[uuid.UUID] = _uuid_pk()
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("officers.officer_id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    content_version_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(
        _pg_enum(WorkflowDecision, "workflow_decision"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(
        back_populates="workflow_events", foreign_keys=[generated_draft_id]
    )
    actor: Mapped["Officer"] = relationship(foreign_keys=[actor_id])

    @property
    def actor_name(self) -> str | None:
        return self.actor.name if self.actor is not None else None


class GrUpload(Base):
    """
    One row per scanned GR upload (image/PDF, OCR'd) — tracks the OCR job
    lifecycle independently of GeneratedDraft, since this row must exist
    (status=pending) before OCR has even run, and GeneratedDraft requires
    NOT NULL content/department that don't exist yet at that point.

    Once OCR + cleaning + metadata extraction succeed, a normal
    GeneratedDraft is created from cleaned_text and generated_draft_id is
    set here -- from then on this row is purely an audit/status record;
    every downstream action (view, edit, conflict resolve) goes through
    the ordinary draft endpoints unmodified.
    """

    __tablename__ = "gr_uploads"

    upload_id: Mapped[uuid.UUID] = _uuid_pk()
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(400), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("officers.officer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[GrUploadStatus] = mapped_column(
        _pg_enum(GrUploadStatus, "gr_upload_status"),
        nullable=False,
        default=GrUploadStatus.PENDING,
        index=True,
    )
    raw_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[{block_index, text_preview, confidence, needs_review}]
    block_confidences: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # {gr_number, date, department, subject, extraction_method}
    extracted_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class NumberCounter(Base):
    """
    Backs GR-number and conflict-ref sequences (see db/repositories/drafts.py).
    One row per scope, e.g. "GR:HTE:2026" or "CFL:2026". Incremented with a
    single atomic UPSERT so concurrent requests never collide.
    """

    __tablename__ = "number_counters"

    scope_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
