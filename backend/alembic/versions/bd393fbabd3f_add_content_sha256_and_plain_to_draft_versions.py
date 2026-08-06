"""add content_sha256 and content_plain to draft_versions

Revision ID: bd393fbabd3f
Revises: 931e755b0949
Create Date: 2026-08-06 00:00:00.000000

Task 1 (SHA-256 integrity hashing): content_sha256 proves, after the
fact, that a stored draft_versions snapshot matches exactly what was
written at that point in the workflow -- tamper-evidence for a
government audit trail, not a diff mechanism (see diffing.py for that,
introduced alongside this migration). Always computed server-side via
hashlib.sha256; a client-supplied hash is never accepted. Backfilled
for existing rows before the NOT NULL constraint is applied.

content_plain is added alongside it because the word-level diff engine
must operate on plain text, not raw HTML -- draft_versions previously
only stored the HTML `content` field, and diffing HTML tags directly
produces unreadable noise. Backfilled by stripping tags from the
existing `content` as a best-effort plain-text reconstruction for rows
written before this migration; every row written after it (see
db.repositories.drafts.patch_draft_content) snapshots the real
content_plain the caller already tracked.
"""
import hashlib
import re
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bd393fbabd3f'
down_revision: Union[str, Sequence[str], None] = '931e755b0949'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def upgrade() -> None:
    op.add_column("draft_versions", sa.Column("content_plain", sa.Text(), nullable=True))
    op.add_column("draft_versions", sa.Column("content_sha256", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT version_id, content FROM draft_versions")).fetchall()
    for version_id, content in rows:
        content = content or ""
        bind.execute(
            sa.text(
                "UPDATE draft_versions SET content_sha256 = :hash, content_plain = :plain "
                "WHERE version_id = :id"
            ),
            {
                "hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "plain": _strip_html(content),
                "id": version_id,
            },
        )

    op.alter_column("draft_versions", "content_sha256", nullable=False)


def downgrade() -> None:
    op.drop_column("draft_versions", "content_sha256")
    op.drop_column("draft_versions", "content_plain")
