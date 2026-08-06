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
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    FINALISED = "finalised"
    ARCHIVED = "archived"


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


class NumberCounter(Base):
    """
    Backs GR-number and conflict-ref sequences (see db/repositories/drafts.py).
    One row per scope, e.g. "GR:HTE:2026" or "CFL:2026". Incremented with a
    single atomic UPSERT so concurrent requests never collide.
    """

    __tablename__ = "number_counters"

    scope_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
