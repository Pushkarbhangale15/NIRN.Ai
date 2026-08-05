"""add conflict resolution fields

Revision ID: a7a5368353a6
Revises: 685491f43d1d
Create Date: 2026-08-06 00:00:00.000000

Adds is_resolved/resolved_reason to draft_conflicts, mirroring the
existing is_dismissed/dismissed_reason pair, so the Resolve Conflict
feature can mark a conflict cleared (as opposed to dismissed as a
false positive) without overloading the dismiss semantics.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7a5368353a6'
down_revision: Union[str, Sequence[str], None] = '685491f43d1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "draft_conflicts",
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "draft_conflicts",
        sa.Column("resolved_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_conflicts", "resolved_reason")
    op.drop_column("draft_conflicts", "is_resolved")
