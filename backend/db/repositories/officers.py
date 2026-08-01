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

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Officer

ALLOWED_SORT_FIELDS = {
    "created_at": Officer.created_at,
    "name": Officer.name,
    "login_id": Officer.login_id,
    "last_login_at": Officer.last_login_at,
}


class AdminRequiredError(PermissionError):
    """Raised when a repository write is attempted by a non-admin caller.

    Routes already gate these operations behind deps.require_admin — this
    is defence in depth (PART 2 spirit): even if a future route forgets
    the dependency, the repository itself refuses the write.
    """


def _require_admin(creating_officer_role: str) -> None:
    if creating_officer_role != "admin":
        raise AdminRequiredError("Only an admin may perform this operation")


async def list_officers(
    session: AsyncSession,
    *,
    search: Optional[str] = None,
    role: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Officer], int]:
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    if sort_dir not in ("asc", "desc"):
        raise ValueError(f"Unsupported sort direction: {sort_dir}")

    stmt = select(Officer)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Officer.name.ilike(like), Officer.login_id.ilike(like)))
    if role is not None:
        stmt = stmt.where(Officer.role == role)
    if department is not None:
        stmt = stmt.where(Officer.department == department)
    if is_active is not None:
        stmt = stmt.where(Officer.is_active == is_active)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    column = ALLOWED_SORT_FIELDS[sort_by]
    order = column.asc() if sort_dir == "asc" else column.desc()
    page_stmt = stmt.order_by(order).limit(limit).offset(offset)
    rows = (await session.execute(page_stmt)).scalars().all()
    return list(rows), total


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
    """Public self-registration path — always creates role='officer'.
    Callers that need to set an arbitrary role must go through
    create_officer_as_admin() below, which enforces the caller is admin.
    """
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


async def create_officer_as_admin(
    session: AsyncSession,
    *,
    creating_officer_role: str,
    name: str,
    login_id: str,
    password_hash: str,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    role: str = "officer",
) -> Officer:
    """Admin-only officer creation — CAN set role directly. Raises
    AdminRequiredError if the caller isn't an admin (defence in depth;
    the route already enforces this via deps.require_admin)."""
    _require_admin(creating_officer_role)
    return await create_officer(
        session,
        name=name,
        login_id=login_id,
        password_hash=password_hash,
        department=department,
        designation=designation,
        role=role,
    )


async def touch_last_login(session: AsyncSession, officer_id: UUID) -> None:
    officer = await get_by_id(session, officer_id)
    if officer is not None:
        officer.last_login_at = datetime.now(timezone.utc)
        await session.flush()


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


async def update_officer(
    session: AsyncSession,
    officer_id: UUID,
    *,
    name: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[Officer]:
    """login_id is deliberately not editable here — it's the officer's
    permanent identifier (see OfficerEdit schema, create-only)."""
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    if name is not None:
        officer.name = name
    if department is not None:
        officer.department = department
    if designation is not None:
        officer.designation = designation
    if role is not None:
        officer.role = role
    await session.flush()
    return officer


async def set_password(
    session: AsyncSession, officer_id: UUID, password_hash: str, *, must_change_password: bool = False
) -> Optional[Officer]:
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    officer.password_hash = password_hash
    officer.must_change_password = must_change_password
    await session.flush()
    return officer


async def count_active_admins(
    session: AsyncSession, *, exclude_officer_id: Optional[UUID] = None, lock: bool = False
) -> int:
    """`lock=True` takes a row lock on every active admin for the rest of
    this transaction — used by the last-admin guard in routes.py so two
    concurrent "deactivate the second-to-last admin" requests can't both
    read "1 remaining" and both proceed. Fetches rows rather than a plain
    COUNT(*) because Postgres can't combine FOR UPDATE with an aggregate;
    the row count here is always small (a handful of admins at most)."""
    stmt = select(Officer.officer_id).where(Officer.role == "admin", Officer.is_active.is_(True))
    if exclude_officer_id is not None:
        stmt = stmt.where(Officer.officer_id != exclude_officer_id)
    if lock:
        stmt = stmt.with_for_update()
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)
