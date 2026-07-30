"""
repositories/officers.py — every query against the officers table.

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens. If raw
SQL is ever unavoidable, use `text()` with bound (:named) parameters,
never interpolation.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Officer


async def list_officers(session: AsyncSession) -> list[Officer]:
    stmt = select(Officer).order_by(Officer.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_login_id(session: AsyncSession, login_id: str) -> Optional[Officer]:
    stmt = select(Officer).where(Officer.login_id == login_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, officer_id: UUID) -> Optional[Officer]:
    stmt = select(Officer).where(Officer.officer_id == officer_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_officer(
    session: AsyncSession,
    *,
    name: str,
    login_id: str,
    password_hash: str,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    role: str = "officer",
) -> Officer:
    officer = Officer(
        name=name,
        login_id=login_id,
        password_hash=password_hash,
        department=department,
        designation=designation,
        role=role,
    )
    session.add(officer)
    await session.flush()
    await session.refresh(officer)
    return officer


async def touch_last_login(session: AsyncSession, officer_id: UUID) -> None:
    officer = await get_by_id(session, officer_id)
    if officer is not None:
        officer.last_login_at = datetime.now(timezone.utc)
        await session.flush()


async def deactivate(session: AsyncSession, officer_id: UUID) -> bool:
    """Deactivate an officer instead of deleting them (drafts must survive for audit)."""
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return False
    officer.is_active = False
    await session.flush()
    return True


async def set_active(session: AsyncSession, officer_id: UUID, is_active: bool) -> Optional[Officer]:
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    officer.is_active = is_active
    await session.flush()
    return officer


async def set_role(session: AsyncSession, officer_id: UUID, role: str) -> Optional[Officer]:
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    officer.role = role
    await session.flush()
    return officer
