"""
db/repositories/officers.py — SQL RULE: every query below is built with
select()/insert()/update() from SQLAlchemy. Never an f-string, never
string concatenation. See backend/README.md, "SQL injection prevention".

All officer reads/writes go through this file. Route handlers never
touch the `Officer` model or a session's query API directly.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import GeneratedDraft, Officer, OfficerRole
from db.security import hash_password


class OfficerHasDraftsError(Exception):
    def __init__(self, count: int):
        self.count = count
        super().__init__(f"Officer has {count} draft(s); deactivate instead of deleting.")


class LastActiveAdminError(Exception):
    pass


class CannotActOnSelfError(Exception):
    pass


class NotAdminError(Exception):
    """
    Raised by the admin_* wrappers below. Routes enforce admin-only
    access via Depends(require_admin); these wrappers are the second,
    independent check inside the repository layer itself, so a route
    that forgets the dependency still can't reach the data.
    """

    pass


def _assert_admin(acting_role: OfficerRole) -> None:
    if acting_role != OfficerRole.ADMIN:
        raise NotAdminError()


# Allowlist for GET /api/officers sort — client input is mapped through
# this dict, never used as a raw column name.
OFFICER_SORT_FIELDS = {
    "name": Officer.name,
    "login_id": Officer.login_id,
    "created_at": Officer.created_at,
    "last_login_at": Officer.last_login_at,
}


async def get_by_login_id(session: AsyncSession, login_id: str) -> Optional[Officer]:
    stmt = select(Officer).where(Officer.login_id == login_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(session: AsyncSession, officer_id: uuid.UUID) -> Optional[Officer]:
    stmt = select(Officer).where(Officer.officer_id == officer_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_officer(
    session: AsyncSession,
    *,
    name: str,
    login_id: str,
    password: str,
    department: Optional[str],
    designation: Optional[str],
    role: OfficerRole,
    must_change_password: bool = True,
) -> Officer:
    officer = Officer(
        name=name,
        login_id=login_id,
        password_hash=hash_password(password),
        department=department,
        designation=designation,
        role=role,
        must_change_password=must_change_password,
    )
    session.add(officer)
    await session.flush()
    return officer


async def update_officer(
    session: AsyncSession,
    officer_id: uuid.UUID,
    *,
    name: Optional[str] = None,
    department: Optional[str] = None,
    designation: Optional[str] = None,
    role: Optional[OfficerRole] = None,
) -> Optional[Officer]:
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


async def set_active(session: AsyncSession, officer_id: uuid.UUID, is_active: bool) -> Optional[Officer]:
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    officer.is_active = is_active
    await session.flush()
    return officer


async def set_password(session: AsyncSession, officer_id: uuid.UUID, new_password: str, *, must_change: bool) -> Optional[Officer]:
    officer = await get_by_id(session, officer_id)
    if officer is None:
        return None
    officer.password_hash = hash_password(new_password)
    officer.must_change_password = must_change
    await session.flush()
    return officer


async def touch_last_login(session: AsyncSession, officer_id: uuid.UUID) -> None:
    """
    Deliberately an ORM attribute assignment, not a bulk update(). A bulk
    update() bypasses the identity map, and SQLAlchemy's default
    synchronize_session='auto' strategy then EXPIRES last_login_at on
    the in-memory Officer object (since it can't evaluate func.now()
    client-side) — the next synchronous access, e.g. Pydantic's
    OfficerOut.model_validate() building the login response, then tries
    to lazily refresh it, which needs an await that can't happen inside
    Pydantic's validator and raises MissingGreenlet.
    """
    officer = await get_by_id(session, officer_id)
    if officer is not None:
        officer.last_login_at = datetime.now(timezone.utc)


async def count_drafts(session: AsyncSession, officer_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(GeneratedDraft).where(GeneratedDraft.drafted_by == officer_id)
    return (await session.execute(stmt)).scalar_one()


async def count_active_admins(session: AsyncSession, *, exclude: Optional[uuid.UUID] = None) -> int:
    stmt = select(func.count()).select_from(Officer).where(
        Officer.role == OfficerRole.ADMIN, Officer.is_active == True  # noqa: E712
    )
    if exclude is not None:
        stmt = stmt.where(Officer.officer_id != exclude)
    return (await session.execute(stmt)).scalar_one()


async def delete_officer(session: AsyncSession, officer_id: uuid.UUID, *, acting_officer_id: uuid.UUID) -> None:
    """
    Hard-deletes an officer. Raises rather than returning a bool so the
    route can map each failure to the right HTTP status:
      CannotActOnSelfError -> 400
      LastActiveAdminError -> 400
      OfficerHasDraftsError(count) -> 409

    Both guard checks run inside the same transaction as the delete
    itself (the caller's session), not as a separate pre-check, so a
    concurrent request can't slip an officer below the "last admin"
    floor between the check and the delete.
    """
    if officer_id == acting_officer_id:
        raise CannotActOnSelfError()

    officer = await get_by_id(session, officer_id)
    if officer is None:
        return

    draft_count = await count_drafts(session, officer_id)
    if draft_count > 0:
        raise OfficerHasDraftsError(draft_count)

    if officer.role == OfficerRole.ADMIN and officer.is_active:
        remaining = await count_active_admins(session, exclude=officer_id)
        if remaining == 0:
            raise LastActiveAdminError()

    await session.delete(officer)
    await session.flush()


async def list_officers(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: Optional[str] = None,
    role: Optional[OfficerRole] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_desc: bool = True,
) -> tuple[Sequence[Officer], int]:
    stmt = select(Officer)
    count_stmt = select(func.count()).select_from(Officer)

    if search:
        pattern = f"%{search}%"
        clause = or_(Officer.name.ilike(pattern), Officer.login_id.ilike(pattern))
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    if role is not None:
        stmt = stmt.where(Officer.role == role)
        count_stmt = count_stmt.where(Officer.role == role)
    if department:
        stmt = stmt.where(Officer.department == department)
        count_stmt = count_stmt.where(Officer.department == department)
    if is_active is not None:
        stmt = stmt.where(Officer.is_active == is_active)
        count_stmt = count_stmt.where(Officer.is_active == is_active)

    sort_col = OFFICER_SORT_FIELDS.get(sort_by, Officer.created_at)
    stmt = stmt.order_by(sort_col.desc() if sort_desc else sort_col.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).scalars().all()
    return rows, total


# ---------------------------------------------------------------------
# Admin-gated wrappers — the repository-layer half of "enforced in BOTH
# the route dependency and the repository function" (admin panel spec).
# Each takes the acting officer's role and asserts it before touching
# the table, independent of whatever the route's own Depends() did.
# ---------------------------------------------------------------------

async def admin_list_officers(session: AsyncSession, *, acting_role: OfficerRole, **kwargs):
    _assert_admin(acting_role)
    return await list_officers(session, **kwargs)


async def admin_create_officer(session: AsyncSession, *, acting_role: OfficerRole, **kwargs) -> Officer:
    _assert_admin(acting_role)
    return await create_officer(session, **kwargs)


async def admin_update_officer(session: AsyncSession, officer_id: uuid.UUID, *, acting_role: OfficerRole, **kwargs) -> Optional[Officer]:
    _assert_admin(acting_role)
    return await update_officer(session, officer_id, **kwargs)


async def admin_set_active(session: AsyncSession, officer_id: uuid.UUID, is_active: bool, *, acting_role: OfficerRole) -> Optional[Officer]:
    _assert_admin(acting_role)
    return await set_active(session, officer_id, is_active)


async def admin_reset_password(session: AsyncSession, officer_id: uuid.UUID, new_password: str, *, acting_role: OfficerRole) -> Optional[Officer]:
    _assert_admin(acting_role)
    return await set_password(session, officer_id, new_password, must_change=True)


async def admin_delete_officer(session: AsyncSession, officer_id: uuid.UUID, *, acting_officer_id: uuid.UUID, acting_role: OfficerRole) -> None:
    _assert_admin(acting_role)
    await delete_officer(session, officer_id, acting_officer_id=acting_officer_id)
