"""
deps.py — FastAPI dependencies for JWT authentication.

get_current_officer() decodes the bearer token, loads the officer from
Postgres, and rejects inactive/unknown officers. Route handlers depend
on this rather than reading the token themselves.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_session
from db.models import Officer
from db.repositories import officers as officers_repo
from db.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_officer(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Officer:
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        officer_id = UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    officer = await officers_repo.get_by_id(session, officer_id)
    if officer is None or not officer.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    return officer


def is_privileged(officer: Officer) -> bool:
    return officer.role in ("reviewer", "admin")


async def require_admin(current: Officer = Depends(get_current_officer)) -> Officer:
    if current.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current
