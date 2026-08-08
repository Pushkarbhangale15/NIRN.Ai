"""
export_pdf_lock.py — encrypts an already-rendered PDF with a password
before download.

PDF rendering stays 100% client-side (html2pdf.js, see
frontend/src/utils/pdfExport.js) to avoid the server-side Devanagari
font risk already documented in export_docx.py. This endpoint only
adds a password-encryption pass on top of bytes the browser already
rendered — it never renders or touches the document's content.

Requires the `pikepdf` package (see requirements.txt) and the `qpdf`
system library it binds to.
"""

import io
import logging
import secrets

import pikepdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from db.models import Officer
from deps import get_current_officer

logger = logging.getLogger("nirn.export_pdf_lock")

router = APIRouter()


@router.post("/api/export/pdf/encrypt", tags=["export"])
async def encrypt_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    officer: Officer = Depends(get_current_officer),
):
    """
    Locks a client-rendered PDF so `password` is required to open it in
    any PDF viewer (the "user" password). A random secret the officer
    never sees (the "owner" password) gates edit/print only. Wrapped
    end-to-end in try/except — never leak a raw traceback.
    """
    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A password is required.")

    try:
        pdf_bytes = await file.read()
        buffer = io.BytesIO()
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            pdf.save(
                buffer,
                encryption=pikepdf.Encryption(
                    owner=secrets.token_urlsafe(16),
                    user=password,
                ),
            )
    except Exception:
        logger.exception("PDF encryption failed for officer %s", officer.officer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not lock the document. Please try again.",
        )

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="GR_locked.pdf"'},
    )
