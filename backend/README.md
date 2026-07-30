# NIRN.Ai backend — Postgres persistence

## 1. Create the database and the restricted app role

The application connects as `nirn_app`, a role that can read/write the
app's own tables but cannot run DDL (no `CREATE`, no `DROP`) — it is
**not** a superuser and cannot alter the schema. Run once, as a
Postgres superuser / the database owner:

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
