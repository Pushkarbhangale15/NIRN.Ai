"""
deps.py — FastAPI auth dependencies.

optional_auth resolves the officer when a valid bearer token is present
and returns None otherwise — never raises. It backs the public,
read-only search endpoints (Task 2: PUBLIC access rules) where a login
is welcome but not required.

get_current_officer / require_admin build on it and DO raise, for
routes that are login-required or admin-only.

SQL RULE: this file issues no queries itself — it delegates to
db.repositories.officers, which is the auditable boundary. See
backend/README.md, "SQL injection prevention".
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_session
from db.models import Officer, OfficerRole
from db.repositories.officers import get_by_id
from db.security import decode_access_token

# auto_error=False so a missing header falls through to `None` instead
# of a 403 — the deciding dependency is optional_auth / get_current_officer.
_bearer = HTTPBearer(auto_error=False)


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Optional[Officer]:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    try:
        officer_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None
    officer = await get_by_id(session, officer_id)
    if officer is None or not officer.is_active:
        return None
    return officer


async def get_current_officer(officer: Optional[Officer] = Depends(optional_auth)) -> Officer:
    if officer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return officer


async def require_admin(officer: Officer = Depends(get_current_officer)) -> Officer:
    if officer.role != OfficerRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    return officer


async def require_reviewer_or_admin(officer: Officer = Depends(get_current_officer)) -> Officer:
    if officer.role not in (OfficerRole.REVIEWER, OfficerRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer or admin privileges required."
        )
    return officer
