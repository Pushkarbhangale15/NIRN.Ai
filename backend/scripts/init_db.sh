#!/usr/bin/env bash
#
# init_db.sh — one-time setup for a fresh Postgres database, local OR a
# hosted free tier (Neon, Supabase, Railway, ...). Run this ONCE, by
# whichever teammate owns the database. Everyone else just needs the
# resulting DATABASE_URL in their own .env — see backend/README.md.
#
# What it does:
#   1. Creates the restricted `nirn_app` role (best-effort — some hosted
#      free tiers don't allow CREATE ROLE; the script warns and moves on
#      if so, see the note it prints at the end).
#   2. Runs every Alembic migration, creating all tables/enums/indexes.
#   3. Grants nirn_app SELECT/INSERT/UPDATE/DELETE on every table (never
#      CREATE/DROP — see PART 2 rule 6 in the original spec).
#
# Usage:
#   cd backend
#   ADMIN_DATABASE_URL="postgresql://<owner-user>:<pw>@<host>:<port>/<db>" \
#   APP_DB_PASSWORD="pick-a-password-for-the-app-role" \
#   ./scripts/init_db.sh
#
# ADMIN_DATABASE_URL is whatever full-access connection string your
# Postgres host gave you (e.g. the one shown in the Neon/Supabase
# dashboard right after creating a project). Plain `postgresql://`,
# not `postgresql+asyncpg://` — this script adds the driver prefix
# where it's needed.

set -euo pipefail
cd "$(dirname "$0")/.."

: "${ADMIN_DATABASE_URL:?Set ADMIN_DATABASE_URL to your Postgres owner connection string}"
: "${APP_DB_PASSWORD:?Set APP_DB_PASSWORD to the password the nirn_app role should use}"

PYTHON="../venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

ADMIN_ASYNC_URL="${ADMIN_DATABASE_URL/postgresql:\/\//postgresql+asyncpg://}"

# libpq/psycopg2 clients (like psql, below) use `sslmode=`; asyncpg's
# connect() has no such kwarg and raises "unexpected keyword argument
# 'sslmode'" if it sees one — it wants `ssl=` instead, accepting the
# same values (require, verify-full, ...). Only the *Python/asyncpg*
# URL needs this rewritten; psql keeps using sslmode via
# $ADMIN_DATABASE_URL unchanged below.
ADMIN_ASYNC_URL="${ADMIN_ASYNC_URL/sslmode=/ssl=}"

echo "==> [1/3] Creating restricted 'nirn_app' role (best-effort)..."
if psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'nirn_app') THEN
      CREATE ROLE nirn_app WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
   ELSE
      ALTER ROLE nirn_app WITH PASSWORD '${APP_DB_PASSWORD}';
   END IF;
END
\$\$;
SQL
then
  ROLE_CREATED=1
else
  ROLE_CREATED=0
  echo "    Could not create/alter 'nirn_app' — some hosted free tiers block CREATE ROLE."
  echo "    Falling back: DATABASE_URL will use the admin connection directly (see note below)."
fi

echo "==> [2/3] Running Alembic migrations (creates all tables/enums/indexes)..."
ALEMBIC_DATABASE_URL="$ADMIN_ASYNC_URL" "$PYTHON" -m alembic upgrade head

if [ "$ROLE_CREATED" = "1" ]; then
  echo "==> [3/3] Granting nirn_app read/write on every table..."
  psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q <<'SQL'
GRANT USAGE ON SCHEMA public TO nirn_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nirn_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nirn_app;
SQL

  APP_URL=$("$PYTHON" - "$ADMIN_ASYNC_URL" "$APP_DB_PASSWORD" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit
url, pw = sys.argv[1], sys.argv[2]
parts = urlsplit(url)
netloc = f"nirn_app:{pw}@{parts.hostname}"
if parts.port:
    netloc += f":{parts.port}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, "")))
PY
)
else
  echo "==> [3/3] Skipped grants (using admin role directly instead)."
  APP_URL="$ADMIN_ASYNC_URL"
fi

echo ""
echo "Done. Put this in your .env (and share it with your team over a"
echo "private channel — NOT git):"
echo ""
echo "  DATABASE_URL=$APP_URL"
echo ""
echo "Next: seed demo data ONCE — anyone else pulling the same DATABASE_URL"
echo "will already see it:"
echo "  $PYTHON seed.py"
