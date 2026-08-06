# NIRN.Ai backend — local database, auth, admin

This backend runs entirely on-premise: local Ollama for the LLM, a
local FAISS index for retrieval, and a local PostgreSQL database for
officers/drafts/conflicts/references. No cloud services, no hosted
database, no external API calls.

## First-time setup

Run these **in order**, from the repository root, after copying
`.env.example` to `.env` and filling in real values (see that file for
what each variable means).

```bash
# 1. Install Python dependencies (adds asyncpg, alembic, passlib,
#    python-jose, slowapi, python-docx, pypdf on top of what was there)
pip install -r requirements.txt

# 2. Create the nirn_ai database, the nirn_app role, and grant it
#    exactly SELECT/INSERT/UPDATE/DELETE (see "Privileges" below).
#    Idempotent — safe to re-run.
export PGSUPERUSER=postgres            # your local Postgres superuser
export NIRN_APP_PASSWORD='choose-a-local-password'   # must match DATABASE_URL in .env
./backend/scripts/setup_local_db.sh

# 3. Apply migrations (creates all 5 tables + number_counters, every
#    enum, every index). Runs as the superuser (ALEMBIC_DATABASE_URL).
cd backend
alembic upgrade head

# 4. Seed demo data (idempotent — safe to re-run). Runs as nirn_app
#    (DATABASE_URL), since it only ever INSERTs/SELECTs.
python3 seed.py

# 5. Run the app as usual
uvicorn app:app --reload
```

Steps 3 and 4 are **not** run automatically by anything in this repo —
they're deliberate, explicit commands you run yourself.

## Privileges

`nirn_app` (used by the running app) gets exactly:

```sql
GRANT CONNECT ON DATABASE nirn_ai TO nirn_app;
GRANT USAGE ON SCHEMA public TO nirn_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nirn_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nirn_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nirn_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO nirn_app;
```

No `CREATE`, no `DROP` — schema changes only ever happen through
Alembic, run as the superuser. See `backend/scripts/setup_local_db.sh`
for the exact idempotent script.

## SQL injection prevention

1. **Every query is built with the ORM** (`select()` / `insert()` /
   `update()`), never an f-string or string concatenation. Every
   repository file (`db/repositories/*.py`) and every route file that
   touches the database carries a comment restating this at the top —
   if you're editing one of those files and reach for an f-string to
   build a query, stop and use `select()` instead.
2. If raw SQL is ever unavoidable, use `text()` with **named bound
   parameters** — never interpolate a value into the string. The one
   place raw SQL appears in this codebase is the Alembic migration
   (static DDL, no user input) and the `SELECT 1` health check.
3. Every request body is validated with Pydantic before it reaches the
   database: `login_id` is `constr(min_length=3, max_length=64,
   pattern=r'^[A-Za-z0-9._-]+$')`; `language`/`status`/`severity`/`role`
   are closed enums, never free strings; UUID path params are typed as
   `uuid.UUID` (FastAPI 422s a malformed one before your code runs);
   text fields have explicit max lengths.
4. **Column names and `ORDER BY` fields never come from user input
   directly.** Every sortable endpoint maps the client's `sort_by`
   string through a hardcoded allowlist dict (e.g.
   `db/repositories/drafts.py::DRAFT_SORT_FIELDS`,
   `db/repositories/officers.py::OFFICER_SORT_FIELDS`) before it
   touches a query — an unrecognised value silently falls back to the
   default sort column rather than being used verbatim.
5. Pagination (`page`, `page_size`) is typed as `int` with `ge`/`le`
   bounds; max page size is 100 (`config.settings.MAX_PAGE_SIZE`).
6. `nirn_app` has no `CREATE`/`DROP` — see "Privileges" above.
7. Every route catches `SQLAlchemyError`, logs it server-side, and
   returns a generic `503 Service unavailable.` — raw database errors
   (which can reveal schema/column names) are never echoed to the
   client.

Verify at any time with:
```bash
grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE\|" + ' backend/
```
This should return nothing (see the verification report for the actual
output).

## Seeded demo credentials

Printed to the console every time `seed.py` runs. For reference:

| Role      | Login ID          | Password          | Department                              |
|-----------|--------------------|--------------------|------------------------------------------|
| Admin     | `admin`            | `NirnAdmin#2026`   | General Administration Department         |
| Officer   | `priya.sharma`     | `Officer#Pass01`   | Higher and Technical Education Department |
| Officer   | `rahul.deshmukh`   | `Officer#Pass02`   | Public Health Department                  |

The admin account has `must_change_password = False`; both officer
accounts have it `True` and will be forced through the first-login
password-change screen. **Change these before this ever runs anywhere
other than your own machine.**

## Auth model

- `POST /api/auth/login` — rate-limited 5/minute per IP (slowapi).
  Returns the same generic error whether the login ID doesn't exist,
  the password is wrong, or the account is inactive.
- Search endpoints (`GET /api/corpus/search`, GR-ID lookup) are
  **public** — an `optional_auth` dependency resolves the officer when
  a token is present and returns `None` otherwise; results are
  identical either way.
- Generating a draft, saving, history, exports, and the admin panel all
  require a valid bearer token (`get_current_officer`).
- Admin-only routes are gated **twice**: once by
  `Depends(require_admin)` on the route, and again inside the
  repository layer itself (`db/repositories/officers.py`, the
  `admin_*` wrapper functions) — a route that forgot the dependency
  still can't reach the data.

## Conflict resolution

`POST /api/conflicts/{id}/resolve` revises a single flagged clause (one
LLM call) and re-verifies it (a second call) — never the whole draft, and
never the full conflict batch. `POST /api/conflicts/{id}/resolve/accept`
commits it: patches only that clause into the draft's content and marks
the conflict `resolved`. `resolution_status` (`not_attempted` / `resolved`
/ `attempted_still_conflicting` / `attempted_error`) is a durable column
on `draft_conflicts` (see `backend/alembic/versions/`), not recomputed on
each page load — a resolved conflict stays resolved across reloads and
fresh analysis runs, and a repeat resolve on an already-resolved conflict
short-circuits instead of regenerating against stale clause text.

## File upload (text-based only)

`POST /api/upload-gr/parse-file` extracts text from an uploaded
`.pdf`/`.docx`/`.txt` (`_extract_text_from_file` in `routes.py`, via
`pypdf`/`python-docx`). Scanned/image PDFs with no embedded text layer are
explicitly out of scope — no OCR is attempted; the endpoint returns a 400
if extraction comes back empty, and the frontend additionally flags a
near-empty result as likely-scanned.

## What's deliberately out of scope

- `store.py` still backs chat sessions and the official-GR-URL cache
  with SQLite — those aren't part of the officers/drafts schema and
  don't need officer attribution or an audit trail.
- No multi-machine setup, data-sharing tooling, or deployment config —
  this runs from a single machine, by design.
