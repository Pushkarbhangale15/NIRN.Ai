"""add resolution_status tracking to draft_conflicts

Revision ID: 7e27eac7a712
Revises: a7a5368353a6
Create Date: 2026-08-06 00:00:00.000000

Bug fix: a conflict's "resolved" state was only reflected in the API
response of the resolve/accept call, never persisted as a durable status,
so a page reload (or a fresh /api/analysis/{draftId}/conflicts run) had
no record of it and re-attempted resolution from scratch — which then
failed because the draft content no longer contained the stale original
clause text. resolution_status makes the outcome of every resolve
attempt durable; resolved_clause_text stores what the clause was
rewritten to, independent of the draft's current content.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e27eac7a712'
down_revision: Union[str, Sequence[str], None] = 'a7a5368353a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "draft_conflicts",
        sa.Column("resolution_status", sa.String(length=32), nullable=False, server_default="not_attempted"),
    )
    op.add_column(
        "draft_conflicts",
        sa.Column("resolved_clause_text", sa.Text(), nullable=True),
    )
    # Backfill: any row already marked is_resolved=True (from before this
    # column existed) should read as resolved, not not_attempted.
    op.execute(
        "UPDATE draft_conflicts SET resolution_status = 'resolved' WHERE is_resolved = true"
    )


def downgrade() -> None:
    op.drop_column("draft_conflicts", "resolved_clause_text")
    op.drop_column("draft_conflicts", "resolution_status")
