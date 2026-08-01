"""
models.py — SQLAlchemy ORM models for officers, generated GR drafts, and
their conflicts / references / edit history.

All queries against these models MUST go through the ORM or `select()`
constructs (see backend/db/repositories/*.py) — never string-built SQL.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

officer_role_enum = PGEnum(
    "officer", "reviewer", "admin", name="officer_role", create_type=False
)
draft_language_enum = PGEnum("en", "mr", name="draft_language", create_type=False)
draft_status_enum = PGEnum(
    "draft", "under_review", "finalised", "archived",
    name="draft_status", create_type=False,
)
conflict_severity_enum = PGEnum(
    "low", "medium", "high", name="conflict_severity", create_type=False
)
conflict_detected_by_enum = PGEnum(
    "rule_engine", "llm_verifier", name="conflict_detected_by", create_type=False
)
reference_script_enum = PGEnum(
    "latin", "devanagari", name="reference_script", create_type=False
)
draft_source_enum = PGEnum(
    "generated", "uploaded", name="draft_source", create_type=False
)


class Officer(Base):
    __tablename__ = "officers"

    officer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    login_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(officer_role_enum, nullable=False, server_default="officer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    drafts: Mapped[list["GeneratedDraft"]] = relationship(
        back_populates="officer", foreign_keys="GeneratedDraft.drafted_by"
    )


class GeneratedDraft(Base):
    __tablename__ = "generated_drafts"

    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    language: Mapped[str] = mapped_column(draft_language_enum, nullable=False)
    drafted_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("officers.officer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(160), nullable=False)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    gr_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(draft_status_enum, nullable=False, server_default="draft")
    source: Mapped[str] = mapped_column(draft_source_enum, nullable=False, server_default="generated")
    # A draft is persisted the moment it's generated/uploaded (conflict
    # detection etc. need a row to attach to), but stays invisible to
    # GET /api/drafts (History) until the officer explicitly confirms it
    # via PATCH .../save — otherwise every accidental/experimental
    # generation would clutter History. See db/repositories/drafts.py.
    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    template_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
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
        Index("ix_generated_drafts_department_created_at", "department", created_at.desc()),
        Index("ix_generated_drafts_status", "status"),
        Index("ix_generated_drafts_source", "source"),
        Index(
            "ix_generated_drafts_content_plain_fts",
            text("to_tsvector('english', coalesce(content_plain, ''))"),
            postgresql_using="gin",
        ),
    )


class DraftConflict(Base):
    __tablename__ = "draft_conflicts"

    conflict_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Human-typeable lookup code, "CFL-<year>-<6-digit seq>" — see
    # db/repositories/conflict_refs.py for the collision-safe generator.
    # Existing rows are backfilled by the migration that adds this column.
    conflict_ref: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    source_of_conflict: Mapped[str] = mapped_column(String(200), nullable=False)
    conflicting_text: Mapped[str] = mapped_column(Text, nullable=False)
    draft_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_gr_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(
        conflict_severity_enum, nullable=False, server_default="medium"
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    detected_by: Mapped[str] = mapped_column(conflict_detected_by_enum, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where in OUR draft this conflict was found — parsed at detection
    # time from the matched clause block via clause_numbering.clause_ref,
    # never guessed after the fact. Null when the clause opened with no
    # recognisable numbering.
    draft_clause_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 0-based ordinal of the matched clause within llm.split_into_clauses()
    # output, for scroll-to-highlight in the editor.
    draft_clause_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Where in the EXISTING GR the clashing text came from, and that GR's
    # denormalised metadata — from the retrieved FAISS chunk, never
    # fabricated. Null when the chunk carried no such info.
    source_clause_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_gr_title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_gr_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="conflicts")

    __table_args__ = (
        Index(
            "ix_draft_conflicts_severity_active",
            "severity",
            postgresql_where=text("is_dismissed = false"),
        ),
    )


class DraftReference(Base):
    __tablename__ = "draft_references"

    reference_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_gr_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    script: Mapped[str] = mapped_column(reference_script_enum, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="references")


class DraftVersion(Base):
    __tablename__ = "draft_versions"

    version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    generated_draft_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generated_drafts.generated_draft_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("officers.officer_id"), nullable=False
    )
    change_note: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    draft: Mapped["GeneratedDraft"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("generated_draft_id", "version_number", name="uq_draft_version_number"),
    )


class GrNumberCounter(Base):
    """Backs the per-department-per-year sequence used to mint provisional
    GR numbers (NIRN/<DEPT>/<YYYY>/<seq>). A plain Postgres SEQUENCE can't
    be created dynamically per department at request time — the app's
    runtime role has no CREATE privilege by design (PART 2 rule 6), and
    departments aren't known ahead of time as a fixed enum. A counter row
    incremented under `SELECT ... FOR UPDATE` gives the same atomicity
    without ever running DDL outside a migration."""

    __tablename__ = "gr_number_counters"

    dept_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ConflictRefCounter(Base):
    """Backs the global-per-year sequence used to mint conflict_ref codes
    (CFL-<YYYY>-<seq>) — see db/repositories/conflict_refs.py. Same
    SELECT ... FOR UPDATE pattern as GrNumberCounter, for the same
    reason: COUNT(*) + 1 races under concurrent inserts."""

    __tablename__ = "conflict_ref_counters"

    # autoincrement=False: this is a natural key (the calendar year, e.g.
    # 2026), not a surrogate counter — a lone Integer primary key
    # otherwise defaults to SERIAL, which would be meaningless here since
    # every insert supplies the year explicitly (see conflict_refs.py).
    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
