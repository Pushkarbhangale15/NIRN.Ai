"""add retrieval_trace to generated_drafts

Revision ID: e40fcc005348
Revises: 7e27eac7a712
Create Date: 2026-08-06 00:00:00.000000

Observability fix: "0 conflicts" was indistinguishable between "checked N
candidates, none conflicted" and "no relevant candidates were ever
retrieved" for a clause. retrieval_trace stores per-clause retrieval
metadata (top_k used, candidates returned with GR id/department/score,
whether each reached the LLM stage or was filtered out earlier) from the
most recent conflict-detection run against the draft.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e40fcc005348'
down_revision: Union[str, Sequence[str], None] = '7e27eac7a712'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generated_drafts",
        sa.Column("retrieval_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_drafts", "retrieval_trace")
