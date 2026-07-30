import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make `backend/` importable (config.py, db/models.py) regardless of the
# working directory alembic was invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings  # noqa: E402
from db.base import Base  # noqa: E402
from db import models  # noqa: E402  (registers all ORM models on Base.metadata)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Never hardcode credentials in alembic.ini — pull the URL from the same
# .env-backed settings the application uses.
#
# Migrations run DDL (CREATE TABLE, CREATE TYPE, ...). The app's runtime
# role (nirn_app, see DATABASE_URL) intentionally has no CREATE/DROP
# privileges (PART 2 rule 6), so migrations use a separate, more
# privileged connection string — ALEMBIC_DATABASE_URL — typically the
# database owner. Falls back to DATABASE_URL if unset (e.g. a CI
# environment that already grants the app role DDL rights).
migration_url = os.getenv("ALEMBIC_DATABASE_URL", settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", migration_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
