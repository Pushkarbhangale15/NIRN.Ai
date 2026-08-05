"""
alembic/env.py — reads ALEMBIC_DATABASE_URL (falling back to
DATABASE_URL) from config.settings and strips "+asyncpg", since
Alembic drives migrations with the sync psycopg2 driver while the app
itself talks to Postgres with asyncpg at request time. Alembic always
runs against the superuser connection (DDL); the app always runs
against nirn_app (DML only) — see backend/README.md.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# So `import config` / `import db.models` resolve the same way they do
# when the app itself runs from inside backend/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings  # noqa: E402
from db.base import Base  # noqa: E402
from db import models  # noqa: E402  (populates Base.metadata as a side effect)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    url = settings.ALEMBIC_DATABASE_URL or settings.DATABASE_URL
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
