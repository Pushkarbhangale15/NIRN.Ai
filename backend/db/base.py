"""
db/base.py — SQL RULE (applies to every file in this package and every
repository built on top of it): all queries go through the ORM / the
SQLAlchemy select()/insert()/update() constructs. Never build SQL with
f-strings or string concatenation. If raw SQL is ever unavoidable, use
text() with named bound parameters — never interpolate a value into the
string itself. See backend/README.md, "SQL injection prevention".

Declarative Base, the async engine, the session factory, and the
get_session FastAPI dependency live here. Nothing else should construct
an engine or session directly.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger("nirn.db")


class Base(DeclarativeBase):
    pass


# Local Postgres needs no SSL parameter — do not add one here.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Commits once the route handler returns normally;
    rolls back the whole unit of work if anything raised. Route handlers
    should never call session.commit() themselves — this is the one place
    that decides.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
