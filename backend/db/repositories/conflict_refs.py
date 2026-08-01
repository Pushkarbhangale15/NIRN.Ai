"""
repositories/conflict_refs.py — mints human-typeable conflict lookup
codes.

RULE (see PART 2 of the persistence spec): every query here MUST use the
SQLAlchemy ORM or `select()` constructs. Never build SQL with string
concatenation or f-strings — that is how SQL injection happens.

Format: CFL-<YYYY>-<6-digit zero-padded sequence>, e.g. CFL-2026-004217.
The sequence is global per year, incremented atomically via
`SELECT ... FOR UPDATE` on a counter row (db.models.ConflictRefCounter)
— never `COUNT(*) + 1`, which races under concurrent inserts and can
hand out the same code twice when several people demo at once against
the shared database. Mirrors db/repositories/gr_numbers.py exactly.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ConflictRefCounter


async def get_next_conflict_ref(session: AsyncSession, *, year: int | None = None) -> str:
    year = year or datetime.now(timezone.utc).year

    # Make sure the counter row exists before locking it. ON CONFLICT DO
    # NOTHING keeps this safe under concurrent first-of-the-year inserts.
    stmt = (
        pg_insert(ConflictRefCounter)
        .values(year=year, next_seq=1)
        .on_conflict_do_nothing(index_elements=["year"])
    )
    await session.execute(stmt)

    # Lock the row so two concurrent requests can't read the same
    # next_seq before either has committed its increment.
    locked = (
        await session.execute(
            select(ConflictRefCounter).where(ConflictRefCounter.year == year).with_for_update()
        )
    ).scalar_one()

    seq = locked.next_seq
    locked.next_seq = seq + 1
    await session.flush()

    return f"CFL-{year}-{seq:06d}"
