"""initial schema

Revision ID: 685491f43d1d
Revises:
Create Date: 2026-08-05 18:13:41.035709

Creates all five tables (officers, generated_drafts, draft_conflicts,
draft_references, draft_versions), the number_counters support table
backing the GR-number/conflict-ref generator, every enum, every index
listed in the spec (including the partial index on undismissed
high-severity-lookup and the GIN full-text index on
generated_drafts.content_plain), and the pgcrypto extension gen_random_uuid()
depends on.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '685491f43d1d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


officer_role = postgresql.ENUM('officer', 'reviewer', 'admin', name='officer_role', create_type=False)
draft_language = postgresql.ENUM('en', 'mr', name='draft_language', create_type=False)
draft_status = postgresql.ENUM('draft', 'under_review', 'finalised', 'archived', name='draft_status', create_type=False)
conflict_severity = postgresql.ENUM('low', 'medium', 'high', name='conflict_severity', create_type=False)
conflict_detected_by = postgresql.ENUM('rule_engine', 'llm_verifier', name='conflict_detected_by', create_type=False)
reference_script = postgresql.ENUM('latin', 'devanagari', name='reference_script', create_type=False)

_ALL_ENUMS = [officer_role, draft_language, draft_status, conflict_severity, conflict_detected_by, reference_script]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    bind = op.get_bind()
    for enum_type in _ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        'officers',
        sa.Column('officer_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('login_id', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('department', sa.String(160), nullable=True),
        sa.Column('designation', sa.String(120), nullable=True),
        sa.Column('role', officer_role, nullable=False, server_default='officer'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('must_change_password', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_officers_login_id', 'officers', ['login_id'])
    op.create_index('ix_officers_login_id', 'officers', ['login_id'])

    op.create_table(
        'generated_drafts',
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(400), nullable=False),
        sa.Column('language', draft_language, nullable=False),
        sa.Column('drafted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('officers.officer_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_plain', sa.Text, nullable=True),
        sa.Column('department', sa.String(160), nullable=False),
        sa.Column('brief', sa.Text, nullable=True),
        sa.Column('gr_number', sa.String(64), nullable=True),
        sa.Column('status', draft_status, nullable=False, server_default='draft'),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('template_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_generated_drafts_drafted_by', 'generated_drafts', ['drafted_by'])
    op.create_index('ix_generated_drafts_department_created_at', 'generated_drafts', ['department', sa.text('created_at DESC')])
    op.create_index('ix_generated_drafts_status', 'generated_drafts', ['status'])
    op.create_index('ix_generated_drafts_gr_number', 'generated_drafts', ['gr_number'])
    op.execute(
        "CREATE INDEX ix_generated_drafts_content_plain_fts ON generated_drafts "
        "USING GIN (to_tsvector('english', coalesce(content_plain, '')))"
    )

    op.create_table(
        'draft_conflicts',
        sa.Column('conflict_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.generated_draft_id', ondelete='CASCADE'), nullable=False),
        sa.Column('conflict_ref', sa.String(24), nullable=False),
        sa.Column('source_of_conflict', sa.String(200), nullable=False),
        sa.Column('conflicting_text', sa.Text, nullable=False),
        sa.Column('draft_excerpt', sa.Text, nullable=True),
        sa.Column('draft_clause_ref', sa.String(64), nullable=True),
        sa.Column('source_clause_ref', sa.String(64), nullable=True),
        sa.Column('conflicting_gr_id', sa.String(64), nullable=True),
        sa.Column('source_gr_title', sa.String(400), nullable=True),
        sa.Column('source_gr_date', sa.Date, nullable=True),
        sa.Column('severity', conflict_severity, nullable=False, server_default='medium'),
        sa.Column('justification', sa.Text, nullable=False),
        sa.Column('detected_by', conflict_detected_by, nullable=False),
        sa.Column('is_dismissed', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('dismissed_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_draft_conflicts_conflict_ref', 'draft_conflicts', ['conflict_ref'])
    op.create_index('ix_draft_conflicts_conflict_ref', 'draft_conflicts', ['conflict_ref'])
    op.create_index('ix_draft_conflicts_generated_draft_id', 'draft_conflicts', ['generated_draft_id'])
    op.create_index('ix_draft_conflicts_conflicting_gr_id', 'draft_conflicts', ['conflicting_gr_id'])
    op.execute(
        "CREATE INDEX ix_draft_conflicts_severity_undismissed ON draft_conflicts (severity) "
        "WHERE is_dismissed = FALSE"
    )

    op.create_table(
        'draft_references',
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.generated_draft_id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference_text', sa.Text, nullable=False),
        sa.Column('extracted_gr_number', sa.String(64), nullable=True),
        sa.Column('reference_date', sa.Date, nullable=True),
        sa.Column('script', reference_script, nullable=False),
        sa.Column('resolved', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_draft_references_generated_draft_id', 'draft_references', ['generated_draft_id'])

    op.create_table(
        'draft_versions',
        sa.Column('version_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.generated_draft_id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('edited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('officers.officer_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('change_note', sa.String(400), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_draft_versions_generated_draft_id', 'draft_versions', ['generated_draft_id'])
    op.create_unique_constraint(
        'uq_draft_versions_draft_number', 'draft_versions', ['generated_draft_id', 'version_number']
    )

    op.create_table(
        'number_counters',
        sa.Column('scope_key', sa.String(64), primary_key=True),
        sa.Column('last_value', sa.Integer, nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('number_counters')
    op.drop_table('draft_versions')
    op.drop_table('draft_references')
    op.execute("DROP INDEX IF EXISTS ix_draft_conflicts_severity_undismissed")
    op.drop_table('draft_conflicts')
    op.execute("DROP INDEX IF EXISTS ix_generated_drafts_content_plain_fts")
    op.drop_table('generated_drafts')
    op.drop_table('officers')

    bind = op.get_bind()
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)

    # pgcrypto is left in place on downgrade — other objects on this
    # Postgres instance may depend on gen_random_uuid() too, and DROP
    # EXTENSION has no "IF unused" form worth risking here.
