"""conflict registry: conflict_ref, clause location, source GR metadata

Revision ID: 177491864193
Revises: 864b1d6c071a
Create Date: 2026-08-01 20:25:09.741995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '177491864193'
down_revision: Union[str, Sequence[str], None] = '864b1d6c071a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conflict_ref_counters',
        sa.Column('year', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('next_seq', sa.Integer(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('year')
    )

    # conflict_ref starts NULLable — the table already has rows, and
    # Postgres can't add a NOT NULL column with no default in one step.
    # Backfilled below, then locked down to NOT NULL + UNIQUE once every
    # row has a value.
    op.add_column('draft_conflicts', sa.Column('conflict_ref', sa.String(length=24), nullable=True))
    op.add_column('draft_conflicts', sa.Column('draft_clause_ref', sa.String(length=64), nullable=True))
    op.add_column('draft_conflicts', sa.Column('draft_clause_index', sa.Integer(), nullable=True))
    op.add_column('draft_conflicts', sa.Column('source_clause_ref', sa.String(length=64), nullable=True))
    op.add_column('draft_conflicts', sa.Column('source_gr_title', sa.String(length=400), nullable=True))
    op.add_column('draft_conflicts', sa.Column('source_gr_date', sa.Date(), nullable=True))

    # Backfill every pre-existing row with a CFL-<year>-<seq> code, the
    # sequence numbered per year in created_at order — the same format
    # get_next_conflict_ref() mints for new rows going forward.
    op.execute("""
        WITH ranked AS (
            SELECT
                conflict_id,
                EXTRACT(YEAR FROM created_at)::int AS yr,
                ROW_NUMBER() OVER (
                    PARTITION BY EXTRACT(YEAR FROM created_at)
                    ORDER BY created_at
                ) AS rn
            FROM draft_conflicts
        )
        UPDATE draft_conflicts dc
        SET conflict_ref = 'CFL-' || ranked.yr || '-' || LPAD(ranked.rn::text, 6, '0')
        FROM ranked
        WHERE dc.conflict_id = ranked.conflict_id
    """)

    # Seed each year's counter to continue right after the highest
    # backfilled sequence, so the first new conflict of that year can't
    # collide with a backfilled ref.
    op.execute("""
        INSERT INTO conflict_ref_counters (year, next_seq)
        SELECT EXTRACT(YEAR FROM created_at)::int AS yr, COUNT(*) + 1
        FROM draft_conflicts
        GROUP BY yr
        ON CONFLICT (year) DO UPDATE
            SET next_seq = GREATEST(conflict_ref_counters.next_seq, EXCLUDED.next_seq)
    """)

    op.alter_column('draft_conflicts', 'conflict_ref', nullable=False)
    op.create_index(op.f('ix_draft_conflicts_conflict_ref'), 'draft_conflicts', ['conflict_ref'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_draft_conflicts_conflict_ref'), table_name='draft_conflicts')
    op.drop_column('draft_conflicts', 'source_gr_date')
    op.drop_column('draft_conflicts', 'source_gr_title')
    op.drop_column('draft_conflicts', 'source_clause_ref')
    op.drop_column('draft_conflicts', 'draft_clause_index')
    op.drop_column('draft_conflicts', 'draft_clause_ref')
    op.drop_column('draft_conflicts', 'conflict_ref')
    op.drop_table('conflict_ref_counters')
