"""
auth_routes.py — login, current-officer, change-password.

SQL RULE: this file never builds a query itself. Every read/write goes
through db.repositories.officers, which is the only place that talks
SQLAlchemy for the officers table. See backend/README.md, "SQL
injection prevention".

There is deliberately no public registration endpoint — officer
creation is admin-only (see admin_routes.py).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.base import get_session
from db.models import Officer
from db.repositories import officers as officers_repo
from db.security import create_access_token, verify_password
from deps import get_current_officer
from rate_limit import limiter
from schemas import ChangePasswordRequest, LoginRequest, LoginResponse, OfficerOut

logger = logging.getLogger("nirn.auth")

router = APIRouter()

# Same generic message for every failure mode (unknown login_id, wrong
# password, inactive account) — different messages would let an
# attacker enumerate valid officer IDs.
_GENERIC_LOGIN_ERROR = "Invalid login ID or password."


@router.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    try:
        officer = await officers_repo.get_by_login_id(session, payload.login_id)
    except SQLAlchemyError:
        logger.exception("Database error during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    if officer is None or not officer.is_active or not verify_password(payload.password, officer.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    await officers_repo.touch_last_login(session, officer.officer_id)
    token = create_access_token(officer.officer_id, officer.role.value)

    return LoginResponse(access_token=token, officer=OfficerOut.model_validate(officer))


@router.get("/api/officers/me", response_model=OfficerOut, tags=["auth"])
async def get_me(officer: Officer = Depends(get_current_officer)) -> OfficerOut:
    return OfficerOut.model_validate(officer)


@router.post("/api/officers/me/change-password", response_model=OfficerOut, tags=["auth"])
async def change_my_password(
    payload: ChangePasswordRequest,
    officer: Officer = Depends(get_current_officer),
    session: AsyncSession = Depends(get_session),
) -> OfficerOut:
    if not verify_password(payload.current_password, officer.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    try:
        updated = await officers_repo.set_password(
            session, officer.officer_id, payload.new_password, must_change=False
        )
    except SQLAlchemyError:
        logger.exception("Database error changing password")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unavailable.")

    return OfficerOut.model_validate(updated)
