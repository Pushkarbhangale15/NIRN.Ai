# NIRN.Ai — Setup Guide

This is the one file to read to get this project running on a new machine.
Follow it top to bottom in order — most setup failures are just a step done
out of order (e.g. seeding before Postgres is running).

## 0. Before you start — the one thing that makes or breaks this

This project has an **AI vector search index that is ~6.4 GB and is not
tracked in git** (`backend/data/index.faiss` + `backend/data/chunks.pkl`).
Without it, search, draft generation, and conflict detection will not work.
**These two files cannot be quickly regenerated** — see Step 5 — so the
single most important thing to get right is making sure you either already
have them, or that Step 5's download succeeds.

There is also `backend/data/index.faiss.flat.bak` (9 GB, uncompressed
predecessor of `index.faiss`) and `backend/data/metadata.txt` (115 MB) —
the running app never reads either one (only `index.faiss` +`chunks.pkl`
are loaded, see `backend/retrieval.py`'s `_load_faiss()`), so don't worry
about transferring or downloading them.

`backend/data/glossary/` (~95 KB, seven small JSON files) is also
**required** — `backend/knowledge/loader.py` raises `KnowledgeBaseLoadError`
and refuses to start without `government_knowledge_base.json` specifically.
It's small enough to always travel with the rest of the repo; called out
here because it's easy to lose track of inside a large, mostly-gitignored
`backend/data/` folder.

## 1. Prerequisites to install

Install these first, in this order:

| Tool | Version used here | Get it |
|---|---|---|
| Python | 3.14.x (3.11+ should also work) | https://www.python.org/downloads/ |
| Node.js | v22.x | https://nodejs.org (LTS or current) |
| PostgreSQL | 18.x | macOS: `brew install postgresql@18` · Windows/Linux: https://www.postgresql.org/download/ |
| Ollama | latest | https://ollama.com/download |
| git | any recent version | usually already installed |

After installing Ollama, pull the model this project uses:
```bash
ollama pull gemma3:4b
```

## 2. Get the code and check what data you have

```bash
git clone <repository-url>
cd "NIRN PRASAD"          # or whatever the cloned folder is named
ls -la backend/data/
```

- **If you see `index.faiss` and `chunks.pkl`, each several GB** — you have
  a full copy already (e.g. someone sent you the whole project directly).
  Skip to Step 3.
- **If `backend/data/` is missing or only has the small `glossary/`
  subfolder** — that's expected for a fresh `git clone` (those files are
  gitignored, see `.gitignore`). Continue to Step 3; Step 5 covers getting
  the index onto this machine.

## 3. Backend: Python environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

If you hit an error like `Cannot find module @rollup/rollup-<platform>`
or a `dlopen`/code-signature failure when you later run `npm run dev` —
this is a known npm optional-dependencies bug, not a project problem. Fix:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
cd ..
```

## 5. Get the search index onto this machine

Skip this step entirely if Step 2 already found `index.faiss` + `chunks.pkl`
in place.

Otherwise, from the project root, with the venv active:
```bash
python setup.py
```
This checks for `backend/data/index.faiss`, `chunks.pkl`, and
`metadata.json`; if they're missing it installs `gdown` and downloads the
prebuilt embeddings from the project's shared Google Drive folder (several
GB — needs a real internet connection, will take a while).

**After it finishes, verify:**
```bash
ls -la backend/data/
```
You must see `index.faiss` (~2.3 GB) and `chunks.pkl` (~4.1 GB). If
`setup.py` reports it's looking for `metadata.json` specifically and the
download produced `metadata.txt` instead, that's fine — neither
`metadata.txt` nor `.json` is loaded by the running app, only `index.faiss`
+ `chunks.pkl` matter.

**If `python setup.py` fails** (quota, access, or network error): there is
no quick local rebuild. The scripts in `backend/one_off_scripts/` are
one-off migration tools from this project's own history, not a repeatable
"build from scratch" pipeline (see that folder's own README.md) — not
imported by the running app. The actual from-scratch
build is `kaggle/build_gr_index.ipynb`, which re-embeds the entire
~2.9M-chunk `mahGRs` corpus — a substantial data-science job (GPU strongly
recommended), not a one-command fix. If you have `mahGRs-main/GRs` locally,
`python build_embeddings.py` is the local equivalent. **Strongly prefer
getting `index.faiss` + `chunks.pkl` directly from someone who already has
them** (USB drive, external SSD, shared drive link) over any of these
rebuild paths.

## 6. PostgreSQL: create the database and app role

Start Postgres if it isn't already running:
```bash
# macOS (Homebrew)
brew services start postgresql@18
```

Find your Postgres **superuser role name** — on a fresh install this is
often your OS username, not `postgres`:
```bash
psql postgres -c "\du"
```

Run the provisioning script (idempotent — safe to re-run), replacing
`YOUR_SUPERUSER_NAME` and choosing your own app password:
```bash
cd backend
PGSUPERUSER=YOUR_SUPERUSER_NAME NIRN_APP_PASSWORD='choose-a-password' ./scripts/setup_local_db.sh
cd ..
```
This creates the `nirn_ai` database and a restricted `nirn_app` role that
only has SELECT/INSERT/UPDATE/DELETE — no schema-modifying privileges (see
`backend/README.md`'s "SQL injection prevention" section for the full
threat model this supports).

## 7. Configure environment variables

```bash
cp .env.example .env
```
Edit `.env`:
- `DATABASE_URL` — set the password to match `NIRN_APP_PASSWORD` from Step 6.
- `ALEMBIC_DATABASE_URL` — set the user to **your own** Postgres superuser
  role name from Step 6 (this is the sync connection Alembic uses to run
  migrations — it needs DDL privileges, `nirn_app` does not have them). This
  is always machine-specific — never copy this value from someone else's
  `.env`.
- `JWT_SECRET` — generate a fresh one, don't reuse any example value:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- Leave `LLM_PROVIDER`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL` as-is if Ollama is
  running locally on the default port.

Now apply the database schema and seed the starter accounts:
```bash
cd backend
source ../venv/bin/activate      # if not already active
alembic upgrade head
python3 seed.py
cd ..
```
`seed.py` prints the seeded login credentials when it finishes — save that
output. If you don't have it, the defaults are:

| Login ID | Password | Role | Department |
|---|---|---|---|
| `admin` | `NirnAdmin#2026` | Admin | General Administration Department |
| `priya.sharma` | `Officer#Pass01` | Officer | Higher and Technical Education Department |
| `rahul.deshmukh` | `Officer#Pass02` | Officer | Public Health Department |

Both officer accounts are forced to change their password on first login.
**Change these credentials before this ever runs anywhere other than your
own machine.**

## 8. Run it

You need three things running at once, each in its own terminal:

```bash
# Terminal 1 — Ollama (skip if it's already running as a background service)
ollama serve

# Terminal 2 — backend (from the project root, with venv active)
cd backend
uvicorn app:app --reload

# Terminal 3 — frontend
cd frontend
npm run dev
```

Open **http://localhost:3000**. The frontend dev server proxies `/api` and
`/health` to the backend on port 8000 automatically — no extra config.

## 9. Verify it actually works

- Log in as `admin` / `NirnAdmin#2026`.
- Go to Draft GR, generate a draft — this calls Ollama, so the first
  generation can take 30–60s depending on the machine.
- Check the Policy Conflicts tab populates after generation.
- Try Search from the home page and confirm results come back (this is
  what proves `index.faiss`/`chunks.pkl` loaded correctly).
- Download the generated draft as PDF and DOCX and confirm both open and
  read correctly.
- On the Upload GR page, upload a text-based PDF and confirm the extracted
  text populates the textarea.

## Troubleshooting

**Backend won't start / crashes on startup with `KnowledgeBaseLoadError`**
`backend/data/glossary/government_knowledge_base.json` is missing — see
Step 0. Copy the `glossary/` subfolder from a working copy if it's absent.

**`ModuleNotFoundError: No module named 'psycopg2'` when running `alembic upgrade head`**
Alembic needs the sync Postgres driver even though the app itself uses the
async one. It's in `requirements.txt` (`psycopg2-binary`) — make sure the
venv is active and `pip install -r requirements.txt` ran in it.

**Login returns 500, or `alembic`/`seed.py` fail with a role/connection error**
Almost always means Postgres isn't running, or `ALEMBIC_DATABASE_URL` in
`.env` has the wrong superuser role name for *this* machine. Re-check Step 6/7.

**Search returns no results / draft generation says the corpus is empty**
`backend/data/index.faiss` and `chunks.pkl` are missing, empty, or in the
wrong place. Re-check Step 5.

**`python setup.py` fails (quota, access, network error)**
There's no quick local rebuild fallback — see Step 5's explanation. Get
`index.faiss` + `chunks.pkl` from someone who already has them instead.

**Frontend dev server crashes with a rollup/`@rollup/rollup-<platform>` error**
See Step 4 — `rm -rf node_modules package-lock.json && npm install`.

**Draft generation hangs or times out**
Ollama isn't running, or `gemma3:4b` wasn't pulled. Run `ollama list` to
check which models you have.

**Uploaded PDF says "appears to be a scanned document"**
Expected — only text-based PDFs (with an embedded text layer) are
supported. Scanned/image PDFs need OCR, which isn't implemented; paste the
text manually instead.

**Port already in use (3000 or 8000)**
Something else on your machine is already using it. Either stop that
process, or change the port — backend: `uvicorn app:app --reload --port 8001`
and update the proxy target in `frontend/vite.config.js`; frontend:
`vite.config.js`'s `server.port`.
