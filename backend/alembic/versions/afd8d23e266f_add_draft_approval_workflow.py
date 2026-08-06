"""add three-tier draft approval workflow

Revision ID: afd8d23e266f
Revises: bd393fbabd3f
Create Date: 2026-08-06 00:00:00.000001

Extends generated_drafts.status from
  draft / under_review / finalised / archived
to
  draft / submitted / reviewed / approved / returned / archived
Existing 'under_review' rows -> 'submitted'; 'finalised' rows ->
'approved'. Postgres has no ALTER TYPE ... DROP VALUE, so removing
under_review/finalised requires the rename-recreate-swap dance below
rather than a plain ALTER TYPE ADD VALUE.

Also adds:
  - draft_workflow_events: APPEND-ONLY audit trail for every handoff in
    the Drafting Officer -> Reviewing Officer -> Approving Authority
    chain (see db.models.DraftWorkflowEvent).
  - generated_drafts.returned_reason: surfaced to the drafting officer
    when their draft is sent back for rework.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'afd8d23e266f'
down_revision: Union[str, Sequence[str], None] = 'bd393fbabd3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_VALUES = ('draft', 'under_review', 'finalised', 'archived')
_NEW_VALUES = ('draft', 'submitted', 'reviewed', 'approved', 'returned', 'archived')

workflow_decision = postgresql.ENUM(
    'submitted', 'edited_and_forwarded', 'forwarded_unchanged',
    'accepted_reviewer_version', 'kept_original', 'returned',
    name='workflow_decision', create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # ---- 1. Swap draft_status's value set (rename-recreate-swap: no
    #         ALTER TYPE ... DROP VALUE exists in Postgres) ----
    op.execute("ALTER TABLE generated_drafts ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE draft_status RENAME TO draft_status_old")
    new_status_enum = postgresql.ENUM(*_NEW_VALUES, name="draft_status", create_type=False)
    new_status_enum.create(bind, checkfirst=False)
    op.execute(
        "ALTER TABLE generated_drafts ALTER COLUMN status TYPE draft_status USING "
        "(CASE status::text "
        "WHEN 'under_review' THEN 'submitted' "
        "WHEN 'finalised' THEN 'approved' "
        "ELSE status::text END)::draft_status"
    )
    op.execute("ALTER TABLE generated_drafts ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE draft_status_old")

    # ---- 2. returned_reason ----
    op.add_column("generated_drafts", sa.Column("returned_reason", sa.Text(), nullable=True))

    # ---- 3. draft_workflow_events ----
    workflow_decision.create(bind, checkfirst=True)
    op.create_table(
        'draft_workflow_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.generated_draft_id', ondelete='CASCADE'), nullable=False),
        sa.Column('from_status', sa.String(20), nullable=False),
        sa.Column('to_status', sa.String(20), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('officers.officer_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_role', sa.String(20), nullable=False),
        sa.Column('content_version_before', sa.Integer(), nullable=True),
        sa.Column('content_version_after', sa.Integer(), nullable=True),
        sa.Column('decision', workflow_decision, nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_draft_workflow_events_generated_draft_id', 'draft_workflow_events', ['generated_draft_id'])


def downgrade() -> None:
    op.drop_index('ix_draft_workflow_events_generated_draft_id', table_name='draft_workflow_events')
    op.drop_table('draft_workflow_events')
    workflow_decision.drop(op.get_bind(), checkfirst=True)

    op.drop_column("generated_drafts", "returned_reason")

    bind = op.get_bind()
    op.execute("ALTER TABLE generated_drafts ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE draft_status RENAME TO draft_status_new")
    old_status_enum = postgresql.ENUM(*_OLD_VALUES, name="draft_status", create_type=False)
    old_status_enum.create(bind, checkfirst=False)
    op.execute(
        "ALTER TABLE generated_drafts ALTER COLUMN status TYPE draft_status USING "
        "(CASE status::text "
        "WHEN 'submitted' THEN 'under_review' "
        "WHEN 'reviewed' THEN 'under_review' "
        "WHEN 'approved' THEN 'finalised' "
        "WHEN 'returned' THEN 'draft' "
        "ELSE status::text END)::draft_status"
    )
    op.execute("ALTER TABLE generated_drafts ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE draft_status_new")
