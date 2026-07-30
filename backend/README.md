# NIRN.Ai backend — Postgres persistence

## 0. Team setup — one shared database (do this first)

The whole team should point at the **same** Postgres instance so
everyone sees the same officers/drafts, rather than each person having
an empty local copy. Pick a free hosted Postgres — [Neon](https://neon.tech)
is the easiest (generous free tier, no card required, gives you a
connection string immediately after creating a project).

**One teammate (the "owner") does this once:**

1. Create a Neon project → copy the connection string it shows you
   (looks like `postgresql://<user>:<pw>@<host>/<db>?sslmode=require`).
2. From `backend/`, run the setup script with that string:
   ```bash
   cd backend
   ADMIN_DATABASE_URL="postgresql://<user>:<pw>@<host>/<db>" \
   APP_DB_PASSWORD="pick-a-password-for-the-app-role" \
   ./scripts/init_db.sh
   ```
   This creates the restricted `nirn_app` role, runs every migration
   (creates all 5 tables + enums + indexes), grants `nirn_app`
   read/write access, and prints the `DATABASE_URL` to use.
3. Seed demo data once: `../venv/bin/python3 seed.py`
4. Generate a `JWT_SECRET` (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`)
   and share **both** `DATABASE_URL` and `JWT_SECRET` with the team over
   a private channel (Slack DM, password manager) — **never commit
   them to git**. Everyone must use the *same* `JWT_SECRET`, or tokens
   issued by one person's backend won't validate on another's.

**Everyone else just does this:**

1. `git pull`
2. Paste the shared `DATABASE_URL` and `JWT_SECRET` into their own
   local `backend/../.env` (copy `.env.example` as a starting point).
3. Run the backend as usual (see step 3 below) — no local Postgres, no
   migrations, no seeding needed; the schema and data already exist on
   the shared database.

If someone later adds a new migration, whoever pulls it runs
`alembic upgrade head` against the shared `DATABASE_URL` **once** (see
§3) — that updates the schema for the whole team, since everyone reads
the same database.

**On SSL:** Neon's connection string uses `?sslmode=require` — that's a
libpq/psycopg2-style parameter. This project's driver, `asyncpg`, has
no `sslmode` kwarg and raises `TypeError: connect() got an unexpected
keyword argument 'sslmode'` if it sees one; it wants `?ssl=require`
instead (same accepted values: `require`, `verify-full`, ...).
`init_db.sh` rewrites this automatically wherever it builds a
`postgresql+asyncpg://` URL, so the `DATABASE_URL` it prints is already
correct. You only need to think about this if you ever hand-build a
`postgresql+asyncpg://` URL yourself from a raw Neon/Supabase string.

---

## 1. Solo/offline alternative: your own local Postgres

If you'd rather not depend on a hosted database (e.g. offline dev),
each person can run their own local Postgres instead — you'll each
have separate data, not the shared team database above. Run once, as
a Postgres superuser / the database owner:

```sql
CREATE ROLE nirn_app WITH LOGIN PASSWORD 'change-me-locally';
CREATE DATABASE nirn_ai OWNER <your_admin_role>;

\c nirn_ai
GRANT CONNECT ON DATABASE nirn_ai TO nirn_app;
GRANT USAGE ON SCHEMA public TO nirn_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nirn_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nirn_app;
```

(Or run `./scripts/init_db.sh` against your local Postgres the same
way as in §0 — it works for local and hosted alike.)

The last line matters: it makes sure tables created by *future*
migrations are automatically granted to `nirn_app` too, without ever
giving it schema-altering rights.

## 2. Configure `.env`

```
DATABASE_URL=postgresql+asyncpg://nirn_app:change-me-locally@localhost:5432/nirn_ai
JWT_SECRET=<random, e.g. python3 -c "import secrets; print(secrets.token_urlsafe(48))">
```

`.env` is gitignored; `.env.example` (committed) documents the shape
with placeholders only.

## 3. Run migrations

Migrations run DDL, so they use a **separate, more privileged
connection** — `nirn_app` intentionally cannot `CREATE TABLE`. Point
`ALEMBIC_DATABASE_URL` at the database owner (or any role with `CREATE`
on schema `public`):

```bash
cd backend
export ALEMBIC_DATABASE_URL="postgresql+asyncpg://<owner_role>@localhost:5432/nirn_ai"
../venv/bin/python3 -m alembic upgrade head
```

If `ALEMBIC_DATABASE_URL` is unset, migrations fall back to
`DATABASE_URL` (fine for a CI environment that already grants the app
role DDL rights).

To roll back: `alembic downgrade base`. To regenerate a fresh revision
after changing `db/models.py`: `alembic revision --autogenerate -m "..."`.

## 4. Seed demo data

```bash
cd backend
../venv/bin/python3 seed.py
```

Creates 2 demo officers (`priya.deshmukh` / `anil.kulkarni`, password
`ChangeMe123!` for both) and 3 sample drafts with conflicts. Safe to
re-run — it skips rows that already exist.

## 5. Auth

- `POST /api/auth/register`, `POST /api/auth/login` (rate-limited to
  5/minute/IP via slowapi), `GET /api/officers/me`.
- All `/api/drafts*`, `/api/analysis/*`, and
  `/api/conflicts/{id}/dismiss` routes require a `Bearer` JWT and are
  scoped to the calling officer's own drafts, unless their role is
  `reviewer` or `admin` — enforced both in the route and again inside
  `db/repositories/*.py` (defence in depth).

## SQL injection prevention

Every query lives in `db/repositories/*.py` and uses the SQLAlchemy
ORM / `select()` — never string-built SQL. `ORDER BY` fields are
checked against a hardcoded allowlist (`drafts_repo.ALLOWED_SORT_FIELDS`)
before reaching a query, since column names can't be bound as
parameters. See the rule-1 comment block at the top of each repository
file.
