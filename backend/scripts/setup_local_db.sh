#!/usr/bin/env bash
#
# setup_local_db.sh — provisions the local nirn_ai Postgres database and
# the restricted nirn_app role. Idempotent: safe to re-run.
#
# Reads credentials from the environment — never hardcoded, never
# echoed to stdout:
#   PGSUPERUSER      superuser role to connect as (default: postgres)
#   PGHOST/PGPORT    default localhost:5432
#   NIRN_APP_PASSWORD   password to set/use for the nirn_app role (required)
#
# Usage:
#   PGSUPERUSER=postgres NIRN_APP_PASSWORD='...' ./backend/scripts/setup_local_db.sh

set -euo pipefail

PGSUPERUSER="${PGSUPERUSER:-postgres}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
DB_NAME="nirn_ai"
APP_ROLE="nirn_app"

if [[ -z "${NIRN_APP_PASSWORD:-}" ]]; then
  echo "NIRN_APP_PASSWORD is not set. Export it before running this script:" >&2
  echo "  export NIRN_APP_PASSWORD='choose-a-password'" >&2
  exit 1
fi

PSQL=(psql -v ON_ERROR_STOP=1 -h "$PGHOST" -p "$PGPORT" -U "$PGSUPERUSER")

echo "==> Creating database '$DB_NAME' (skipped if it already exists)"
"${PSQL[@]}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
  || "${PSQL[@]}" -d postgres -c "CREATE DATABASE $DB_NAME"

echo "==> Enabling pgcrypto (gen_random_uuid) on '$DB_NAME'"
"${PSQL[@]}" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto"

echo "==> Creating role '$APP_ROLE' (skipped if it already exists)"
"${PSQL[@]}" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$APP_ROLE'" | grep -q 1 \
  || "${PSQL[@]}" -d postgres -c "CREATE ROLE $APP_ROLE WITH LOGIN"

# Always (re)apply the password — cheap, idempotent, and means rerunning
# this script after rotating NIRN_APP_PASSWORD does the right thing.
"${PSQL[@]}" -d postgres -c "ALTER ROLE $APP_ROLE WITH PASSWORD '$NIRN_APP_PASSWORD'"

echo "==> Granting connect/usage/DML privileges to '$APP_ROLE'"
"${PSQL[@]}" -d "$DB_NAME" <<SQL
GRANT CONNECT ON DATABASE $DB_NAME TO $APP_ROLE;
GRANT USAGE ON SCHEMA public TO $APP_ROLE;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $APP_ROLE;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $APP_ROLE;

-- So tables created by FUTURE migrations are automatically accessible
-- to nirn_app — without this the app breaks the next time a migration
-- adds a table, since nirn_app never gets CREATE/DROP on the schema.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $APP_ROLE;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO $APP_ROLE;
SQL

echo "==> Done. nirn_app has SELECT/INSERT/UPDATE/DELETE only — no CREATE, no DROP."
echo "==> Next: run Alembic migrations as the superuser, then seed.py as nirn_app."
