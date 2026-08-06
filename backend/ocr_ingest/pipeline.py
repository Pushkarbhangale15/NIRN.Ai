"""
ocr_ingest/pipeline.py — orchestrates the scanned-GR ingestion job:
OCR -> clean -> clause-split (reusing conflict_detection's splitter) ->
metadata extraction -> create a normal GeneratedDraft -> run the *existing*
detect_cross_department_conflicts() unchanged -> persist conflicts,
tagging any whose source clause overlaps a low-OCR-confidence block.

Runs as a FastAPI BackgroundTasks callback (see routes.py's
POST /api/gr/upload), so it opens its own DB session -- the request-scoped
one is gone by the time this executes.
"""
import logging
import uuid

from db.base import async_session_factory
from db.repositories import drafts as drafts_repo
from db.repositories import gr_uploads as gr_uploads_repo
from config import settings
from conflict_detection import _extract_operative_clauses, detect_cross_department_conflicts
from retrieval import is_marathi_text

from . import clean, metadata
from .extract import ocr_document
from .storage import load_upload_bytes

logger = logging.getLogger("nirn.ocr_ingest")

_DEFAULT_DEPARTMENT = "General_Administration_Department"

# Mirrors routes.py's _to_db_severity -- kept local rather than imported to
# avoid a circular import (routes.py schedules this module's entrypoint as
# a background task, so this module can't import back from routes.py).
_DB_SEVERITY_MAP = {"low": "low", "medium": "medium", "high": "high", "critical": "high"}


def _to_db_severity(severity) -> str:
    return _DB_SEVERITY_MAP.get((severity or "").lower(), "medium")


def _clause_is_low_confidence(clause: str, low_confidence_spans: list) -> bool:
    """A clause is treated as low-confidence-sourced if a meaningful chunk
    of a flagged OCR span's text appears inside it. Exact offsets don't
    survive the cleaning/reflow step, so this is a text-overlap check
    rather than a position check."""
    for span in low_confidence_spans:
        span_text = span["text"].strip()
        if len(span_text) >= 8 and span_text in clause:
            return True
    return False


async def run_ocr_pipeline(upload_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        upload = await gr_uploads_repo.mark_processing(session, upload_id)
        if upload is None:
            logger.error("gr_uploads row %s vanished before processing started", upload_id)
            return
        file_hash = upload.file_hash
        original_filename = upload.original_filename
        file_type = upload.file_type
        uploaded_by = upload.uploaded_by
        await session.commit()

    # File bytes aren't kept in the DB (large binary, not queryable) -- see
    # routes.py's upload handler, which stashes them on disk keyed by hash
    # before scheduling this task.
    file_bytes = load_upload_bytes(file_hash)

    try:
        blocks = ocr_document(file_bytes, file_type)
        raw_ocr_text = "\n".join(b.text for b in blocks if b.text.strip())
        cleaned_text, low_confidence_spans = clean.clean_and_reassemble(blocks)

        if not cleaned_text.strip():
            raise ValueError(
                "OCR produced no usable text -- the scan may be blank, too low-resolution, "
                "or in a script/orientation Tesseract couldn't read."
            )

        block_confidences = [
            {"block_index": i, "text_preview": b.text[:80], "confidence": b.confidence, "needs_review": b.needs_review}
            for i, b in enumerate(blocks)
        ]
        extracted = metadata.extract_metadata(cleaned_text)

        async with async_session_factory() as session:
            await gr_uploads_repo.save_ocr_results(
                session, upload_id,
                raw_ocr_text=raw_ocr_text,
                cleaned_text=cleaned_text,
                block_confidences=block_confidences,
                extracted_metadata=extracted,
            )
            await session.commit()

        draft_language = "mr" if is_marathi_text(cleaned_text) else "en"
        department = extracted.get("department") or _DEFAULT_DEPARTMENT
        title = extracted.get("subject") or f"Scanned GR: {original_filename[:60]}"

        async with async_session_factory() as session:
            draft = await drafts_repo.create_draft_with_analysis(
                session,
                title=title,
                language=draft_language,
                drafted_by=uploaded_by,
                content=cleaned_text,
                content_plain=cleaned_text,
                department=department,
                brief=None,
            )
            draft_id = draft.generated_draft_id
            await session.commit()

        # The existing, unmodified conflict-detection pipeline -- same
        # function typed drafts use via /api/analysis/{draft_id}/conflicts.
        report_items = detect_cross_department_conflicts(cleaned_text, draft_language=draft_language)
        report_items = [item for item in report_items if item.confidence >= settings.CONFLICT_CONFIDENCE_FLOOR]

        # Correlate each conflict's source clause against the low-confidence
        # OCR spans (computed once, since clause boundaries don't change
        # per-candidate) to decide the low-confidence flag per conflict.
        clauses = _extract_operative_clauses(cleaned_text)
        low_confidence_clauses = {
            c for c in clauses if _clause_is_low_confidence(c, low_confidence_spans)
        }

        conflict_dicts = [
            {
                "source_of_conflict": item.existing_department or item.existing_gr_title,
                "conflicting_text": item.matched_clause,
                "draft_excerpt": item.draft_clause,
                "conflicting_gr_id": item.existing_gr_id,
                "source_gr_title": item.existing_gr_title,
                "severity": _to_db_severity(item.severity),
                "justification": item.reason,
                "detected_by": "llm_verifier",
                "source_ocr_low_confidence": item.draft_clause in low_confidence_clauses,
            }
            for item in report_items
        ]

        async with async_session_factory() as session:
            if conflict_dicts:
                await drafts_repo.persist_conflicts_for_draft(session, draft_id, conflict_dicts)
            needs_review = bool(low_confidence_spans) or bool(conflict_dicts)
            await gr_uploads_repo.mark_complete(
                session, upload_id, generated_draft_id=draft_id, needs_review=needs_review
            )
            await session.commit()

        logger.info(
            "OCR pipeline complete for upload %s -> draft %s (%d conflicts, needs_review=%s)",
            upload_id, draft_id, len(conflict_dicts), needs_review,
        )

    except Exception as exc:  # noqa: BLE001 -- must never crash silently; row has to end in a terminal state
        logger.exception("OCR pipeline failed for upload %s", upload_id)
        async with async_session_factory() as session:
            await gr_uploads_repo.mark_failed(session, upload_id, error_message=str(exc)[:2000])
            await session.commit()
