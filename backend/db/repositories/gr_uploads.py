"""
db/repositories/gr_uploads.py — SQL RULE: every query below is built with
select()/update() from SQLAlchemy. Never an f-string, never string
concatenation. See backend/README.md, "SQL injection prevention".

Covers the gr_uploads table: the OCR job lifecycle for scanned GR uploads
(pending -> processing -> needs_review/complete/failed), tracked
independently of generated_drafts since a row here must exist before OCR
has produced clean text/department to create one with. See
ocr_ingest/pipeline.py for the state machine itself.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import GrUpload, GrUploadStatus


async def get_by_hash(session: AsyncSession, file_hash: str) -> Optional[GrUpload]:
    stmt = select(GrUpload).where(GrUpload.file_hash == file_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(session: AsyncSession, upload_id: uuid.UUID) -> Optional[GrUpload]:
    stmt = select(GrUpload).where(GrUpload.upload_id == upload_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_pending_upload(
    session: AsyncSession,
    *,
    file_hash: str,
    original_filename: str,
    file_type: str,
    file_size_bytes: int,
    uploaded_by: uuid.UUID,
) -> GrUpload:
    """Inserted and flushed (not committed -- get_session commits when the
    route returns) before any OCR work starts, so a failure partway
    through processing is still traceable back to a real row rather than
    just an unlogged exception."""
    upload = GrUpload(
        file_hash=file_hash,
        original_filename=original_filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        uploaded_by=uploaded_by,
        status=GrUploadStatus.PENDING,
    )
    session.add(upload)
    await session.flush()
    return upload


async def mark_processing(session: AsyncSession, upload_id: uuid.UUID) -> Optional[GrUpload]:
    upload = await get_by_id(session, upload_id)
    if upload is None:
        return None
    upload.status = GrUploadStatus.PROCESSING
    await session.flush()
    return upload


async def mark_failed(session: AsyncSession, upload_id: uuid.UUID, *, error_message: str) -> Optional[GrUpload]:
    upload = await get_by_id(session, upload_id)
    if upload is None:
        return None
    upload.status = GrUploadStatus.FAILED
    upload.error_message = error_message
    await session.flush()
    return upload


async def save_ocr_results(
    session: AsyncSession,
    upload_id: uuid.UUID,
    *,
    raw_ocr_text: str,
    cleaned_text: str,
    block_confidences: list,
    extracted_metadata: dict,
) -> Optional[GrUpload]:
    upload = await get_by_id(session, upload_id)
    if upload is None:
        return None
    upload.raw_ocr_text = raw_ocr_text
    upload.cleaned_text = cleaned_text
    upload.block_confidences = block_confidences
    upload.extracted_metadata = extracted_metadata
    await session.flush()
    return upload


async def mark_complete(
    session: AsyncSession,
    upload_id: uuid.UUID,
    *,
    generated_draft_id: uuid.UUID,
    needs_review: bool,
) -> Optional[GrUpload]:
    upload = await get_by_id(session, upload_id)
    if upload is None:
        return None
    upload.generated_draft_id = generated_draft_id
    upload.status = GrUploadStatus.NEEDS_REVIEW if needs_review else GrUploadStatus.COMPLETE
    await session.flush()
    return upload
