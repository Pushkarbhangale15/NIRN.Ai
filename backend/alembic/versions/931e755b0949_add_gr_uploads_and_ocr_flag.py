"""add gr_uploads table and source_ocr_low_confidence flag

Revision ID: 931e755b0949
Revises: e40fcc005348
Create Date: 2026-08-06 00:00:00.000000

Adds the scanned-GR OCR ingestion path: gr_uploads tracks the OCR job
lifecycle (pending -> processing -> needs_review/complete/failed)
independently of generated_drafts, since a row here must exist before OCR
has produced clean text/department -- generated_drafts requires those NOT
NULL. Once OCR succeeds, generated_draft_id links to the normal draft
created from the cleaned text, and everything downstream (conflicts,
resolve, edit) reuses the existing draft machinery unmodified.

source_ocr_low_confidence on draft_conflicts flags a conflict whose draft
clause was correlated with a low-OCR-confidence block, so the frontend can
distinguish "might be a misread" from a normal-confidence match.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '931e755b0949'
down_revision: Union[str, Sequence[str], None] = 'e40fcc005348'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

gr_upload_status = postgresql.ENUM(
    'pending', 'processing', 'needs_review', 'complete', 'failed',
    name='gr_upload_status', create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    gr_upload_status.create(bind, checkfirst=True)

    op.add_column(
        "draft_conflicts",
        sa.Column("source_ocr_low_confidence", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        'gr_uploads',
        sa.Column('upload_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('original_filename', sa.String(400), nullable=False),
        sa.Column('file_type', sa.String(16), nullable=False),
        sa.Column('file_size_bytes', sa.Integer, nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('officers.officer_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', gr_upload_status, nullable=False, server_default='pending'),
        sa.Column('raw_ocr_text', sa.Text, nullable=True),
        sa.Column('cleaned_text', sa.Text, nullable=True),
        sa.Column('block_confidences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extracted_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('generated_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_drafts.generated_draft_id', ondelete='SET NULL'), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_gr_uploads_file_hash', 'gr_uploads', ['file_hash'])
    op.create_index('ix_gr_uploads_file_hash', 'gr_uploads', ['file_hash'])
    op.create_index('ix_gr_uploads_uploaded_by', 'gr_uploads', ['uploaded_by'])
    op.create_index('ix_gr_uploads_status', 'gr_uploads', ['status'])
    op.create_index('ix_gr_uploads_generated_draft_id', 'gr_uploads', ['generated_draft_id'])


def downgrade() -> None:
    op.drop_table('gr_uploads')
    op.drop_column("draft_conflicts", "source_ocr_low_confidence")
    gr_upload_status.drop(op.get_bind(), checkfirst=True)
