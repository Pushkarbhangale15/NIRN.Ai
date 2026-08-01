"""
repositories/gr_numbers.py — mints provisional GR numbers.

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens. If raw
SQL is ever unavoidable, use `text()` with bound (:named) parameters,
never interpolation.

Real GR numbers are assigned by the issuing department, which this app
cannot do. Instead we generate a clearly-provisional reference:

    NIRN/<DEPT-CODE>/<YYYY>/<6-digit sequence>

The sequence is per department per year, incremented atomically via
`SELECT ... FOR UPDATE` on a counter row (db.models.GrNumberCounter) —
never `COUNT(*) + 1`, which races under concurrent inserts and can hand
out the same number twice.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import department_code
from db.models import GrNumberCounter


async def get_next_gr_number(session: AsyncSession, department: str, *, year: int | None = None) -> str:
    dept_code = department_code(department)
    year = year or datetime.now(timezone.utc).year

    # Make sure the counter row exists before locking it. ON CONFLICT DO
    # NOTHING keeps this safe under concurrent first-of-the-year inserts.
    stmt = (
        pg_insert(GrNumberCounter)
        .values(dept_code=dept_code, year=year, next_seq=1)
        .on_conflict_do_nothing(index_elements=["dept_code", "year"])
    )
    await session.execute(stmt)

    # Lock the row so two concurrent requests can't read the same
    # next_seq before either has committed its increment.
    locked = (
        await session.execute(
            select(GrNumberCounter)
            .where(GrNumberCounter.dept_code == dept_code, GrNumberCounter.year == year)
            .with_for_update()
        )
    ).scalar_one()

    seq = locked.next_seq
    locked.next_seq = seq + 1
    await session.flush()

    return f"NIRN/{dept_code}/{year}/{seq:06d}"
