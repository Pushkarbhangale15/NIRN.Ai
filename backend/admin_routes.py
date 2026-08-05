"""
admin_routes.py — officer management + the admin "All Drafts" view.

Every endpoint here requires Depends(require_admin) AND calls one of
the admin_* repository wrappers, which re-check the role independently
(see db/repositories/officers.py). SQL RULE: this file never builds a
query itself — see backend/README.md, "SQL injection prevention".
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.base import get_session
from db.models import Officer, OfficerRole
from db.repositories import drafts as drafts_repo
from db.repositories import officers as officers_repo
from deps import require_admin
from schemas import (
    AdminSummaryCounts,
    DraftHistoryItem,
    OfficerCreate,
    OfficerOut,
    OfficerUpdate,
    PaginatedDraftHistory,
    PaginatedOfficers,
    ResetPasswordResponse,
)
from db.security import generate_strong_password

logger = logging.getLogger("nirn.admin")

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/api/officers", response_model=PaginatedOfficers, tags=["admin"])
async def list_officers(
    search: Optional[str] = Query(None, max_length=120),
    role: Optional[OfficerRole] = None,
    department: Optional[str] = Query(None, max_length=160),
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PaginatedOfficers:
    size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    try:
        rows, total = await officers_repo.admin_list_officers(
            session,
            acting_role=admin.role,
            search=search,
            role=role,
            department=department,
            is_active=is_active,
            page=page,
            page_size=size,
        )
    except SQLAlchemyError:
        logger.exception("Database error listing officers")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return PaginatedOfficers(
        items=[OfficerOut.model_validate(o) for o in rows], total=total, page=page, page_size=size
    )


@router.post("/api/officers", response_model=OfficerOut, status_code=status.HTTP_201_CREATED, tags=["admin"])
async def create_officer(
    payload: OfficerCreate,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    existing = await officers_repo.get_by_login_id(session, payload.login_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That login ID is already in use.")

    try:
        officer = await officers_repo.admin_create_officer(
            session,
            acting_role=admin.role,
            name=payload.name,
            login_id=payload.login_id,
            password=payload.password,
            department=payload.department,
            designation=payload.designation,
            role=payload.role,
        )
    except SQLAlchemyError:
        logger.exception("Database error creating officer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return OfficerOut.model_validate(officer)


@router.patch("/api/officers/{officer_id}", response_model=OfficerOut, tags=["admin"])
async def update_officer(
    officer_id: uuid.UUID,
    payload: OfficerUpdate,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    try:
        officer = await officers_repo.admin_update_officer(
            session,
            officer_id,
            acting_role=admin.role,
            name=payload.name,
            department=payload.department,
            designation=payload.designation,
            role=payload.role,
        )
    except SQLAlchemyError:
        logger.exception("Database error updating officer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    if officer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    return OfficerOut.model_validate(officer)


@router.patch("/api/officers/{officer_id}/deactivate", response_model=OfficerOut, tags=["admin"])
async def deactivate_officer(
    officer_id: uuid.UUID,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    if officer_id == admin.officer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")

    officer = await officers_repo.get_by_id(session, officer_id)
    if officer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found.")

    if officer.role == OfficerRole.ADMIN:
        remaining = await officers_repo.count_active_admins(session, exclude=officer_id)
        if remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last remaining active admin.",
            )

    try:
        updated = await officers_repo.admin_set_active(session, officer_id, False, acting_role=admin.role)
    except SQLAlchemyError:
        logger.exception("Database error deactivating officer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return OfficerOut.model_validate(updated)


@router.patch("/api/officers/{officer_id}/activate", response_model=OfficerOut, tags=["admin"])
async def activate_officer(
    officer_id: uuid.UUID,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    try:
        officer = await officers_repo.admin_set_active(session, officer_id, True, acting_role=admin.role)
    except SQLAlchemyError:
        logger.exception("Database error activating officer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    if officer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    return OfficerOut.model_validate(officer)


@router.post("/api/officers/{officer_id}/reset-password", response_model=ResetPasswordResponse, tags=["admin"])
async def reset_officer_password(
    officer_id: uuid.UUID,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ResetPasswordResponse:
    new_password = generate_strong_password()
    try:
        officer = await officers_repo.admin_reset_password(
            session, officer_id, new_password, acting_role=admin.role
        )
    except SQLAlchemyError:
        logger.exception("Database error resetting password")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    if officer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found.")
    return ResetPasswordResponse(officer_id=officer_id, new_password=new_password)


@router.delete("/api/officers/{officer_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
async def delete_officer(
    officer_id: uuid.UUID,
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await officers_repo.admin_delete_officer(
            session, officer_id, acting_officer_id=admin.officer_id, acting_role=admin.role
        )
    except officers_repo.CannotActOnSelfError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")
    except officers_repo.LastActiveAdminError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last remaining active admin."
        )
    except officers_repo.OfficerHasDraftsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"This officer has {exc.count} draft(s) and cannot be deleted. Deactivate instead.",
                "draft_count": exc.count,
            },
        )
    except SQLAlchemyError:
        logger.exception("Database error deleting officer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")


@router.get("/api/officers/{officer_id}/drafts", response_model=PaginatedDraftHistory, tags=["admin"])
async def get_officer_drafts(
    officer_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedDraftHistory:
    officer = await officers_repo.get_by_id(session, officer_id)
    if officer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Officer not found.")

    size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    try:
        rows, total = await drafts_repo.list_drafts_for_officer_admin_view(
            session, officer_id, page=page, page_size=size
        )
    except SQLAlchemyError:
        logger.exception("Database error listing officer drafts")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    items = [
        DraftHistoryItem(
            generated_draft_id=d.generated_draft_id,
            gr_number=d.gr_number,
            title=d.title,
            department=d.department,
            language=d.language.value if hasattr(d.language, "value") else d.language,
            status=d.status.value if hasattr(d.status, "value") else d.status,
            version=d.version,
            created_at=d.created_at,
            updated_at=d.updated_at,
            unresolved_conflict_count=count,
        )
        for d, count in rows
    ]
    return PaginatedDraftHistory(items=items, total=total, page=page, page_size=size)


@router.get("/api/admin/drafts", response_model=PaginatedDraftHistory, tags=["admin"])
async def admin_list_all_drafts(
    officer_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = Query(None, max_length=160),
    search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(default=None, ge=1, le=100),
    admin: Officer = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PaginatedDraftHistory:
    size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
    try:
        rows, total = await drafts_repo.list_drafts(
            session,
            requesting_officer_id=admin.officer_id,
            requesting_role=admin.role,
            page=page,
            page_size=size,
            status=status_filter,
            department=department,
            search=search,
            filter_officer_id=officer_id,
        )
    except SQLAlchemyError:
        logger.exception("Database error listing all drafts")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    items = [
        DraftHistoryItem(
            generated_draft_id=d.generated_draft_id,
            gr_number=d.gr_number,
            title=d.title,
            department=d.department,
            language=d.language.value if hasattr(d.language, "value") else d.language,
            status=d.status.value if hasattr(d.status, "value") else d.status,
            version=d.version,
            created_at=d.created_at,
            updated_at=d.updated_at,
            unresolved_conflict_count=count,
        )
        for d, count in rows
    ]
    return PaginatedDraftHistory(items=items, total=total, page=page, page_size=size)


@router.get("/api/admin/summary", response_model=AdminSummaryCounts, tags=["admin"])
async def admin_summary(
    session: AsyncSession = Depends(get_session),
) -> AdminSummaryCounts:
    try:
        counts = await drafts_repo.admin_summary_counts(session)
    except SQLAlchemyError:
        logger.exception("Database error computing admin summary")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")
    return AdminSummaryCounts(**counts)
