# NIRN.Ai — Setup on a New PC (no `backend/data/`, no `mahGRs-main/`)

This guide is for the specific transfer scenario where **`backend/data/`
and `mahGRs-main/` are NOT copied** to the new machine — only the rest of
the repo (code, configs, docs) travels. If you're instead copying the full
project including those two folders, use **`SETUP.md`** — it's a different
(easier) path.

Read the whole "Before you start" section before doing anything — the
missing folders create two real constraints that shape every step below.

---

## Before you start: what leaving these folders out actually means

### 1. `backend/data/glossary/` will also be missing — and the backend cannot start without it

`backend/data/glossary/` is **inside** `backend/data/`, so excluding the
whole `backend/data/` folder also excludes it. That subfolder is tiny
(~95 KB — six small JSON files: `government_knowledge_base.json`,
`legal_glossary.json`, `department_names.json`, `office_designations.json`,
`government_phrases.json`, `budget_heads.json`) but it is **required**:
`backend/knowledge/loader.py` raises `KnowledgeBaseLoadError` and the app
refuses to start if `government_knowledge_base.json` isn't found.

**Recommended:** copy just this one small subfolder separately (email,
Slack, a tiny zip — it's ~95 KB total), even though you're intentionally
leaving the rest of `backend/data/` behind. The automatic download in Step
4 below *might* also include it if whoever built the Google Drive folder
put it there, but don't rely on that — verify after Step 4, and copy it
by hand if it's missing.

### 2. There is no local fallback for rebuilding the search index

The only way this project's semantic search index
(`backend/data/index.faiss` + `backend/data/chunks.pkl`, ~6.4 GB combined)
gets onto a machine without a direct copy is the automatic Google Drive
download in Step 4 (`python setup.py`). Both other ways of getting these
files depend on data you've also chosen not to transfer:

- **Rebuilding locally from raw text** (`build_embeddings.py`) needs the
  `mahGRs-main/GRs` corpus — not present on this machine.
- **Rebuilding from scratch on Kaggle** (`kaggle/build_gr_index.ipynb`) also
  re-embeds the same `mahGRs-main` corpus — same problem.

So **Step 4 succeeding is a hard requirement**, not an optional
convenience. It needs a working internet connection and pulls several GB
from Google Drive. If it fails (quota, access, network), the fallback is
to get `index.faiss` + `chunks.pkl` from the original machine some other
way (USB drive, external SSD, direct transfer) — there's no local
regeneration path available on a machine without `mahGRs-main`.

---

## What changed in this project this session (for context / review)

These are the code and config changes made in the most recent working
session, in case you're reconciling this copy against another one or just
want to know what's different from an older snapshot.

### Conflict detection pipeline (recall improvements, no new dependencies)

- **`backend/config.py`** — added two new settings:
  - `MAX_CLAUSES_FOR_LLM` (=2): caps how many clauses get the *expensive*
    LLM verification pass. Previously one setting (`MAX_CLAUSES_ANALYSED`)
    capped both the deterministic rule engine *and* the LLM stage at the
    same small number; now the rule engine (free, local, no LLM call) runs
    over every clause, while the LLM budget stays exactly what it was.
  - `RULE_ENGINE_CANDIDATES_PER_CLAUSE` (=6): the deterministic rule engine
    now inspects a wider pool of retrieved candidates per clause than the
    LLM stage does (`CANDIDATES_PER_CLAUSE`, still 2). Fetched in a single
    retrieval call (no duplicate FAISS/embedding work) — only the top
    `CANDIDATES_PER_CLAUSE` of that same pool are ever sent to the LLM, so
    LLM-call volume/latency is unchanged.
- **`backend/conflict_detection/__init__.py`**:
  - The clause loop now runs over *every* extracted clause instead of just
    the first `MAX_CLAUSES_ANALYSED`. Deterministic rule-engine coverage is
    unconditional; the LLM stage is gated by a new `_priority_score()`
    ranking (funding/authority/timeline/committee/legal-reference/
    jurisdiction keyword presence, reusing existing keyword lists — no new
    keyword data) so the limited LLM slots go to the most likely-relevant
    clauses instead of simply "whichever came first in the document."
    Ties preserve original document order (stable sort).
- **`backend/conflict_detection/rule_engine.py`**:
  - Added a numeric-comparison fallback for **Timeline**, **Committee**,
    and **Funding-ratio** conflicts. The old rules only matched two
    hardcoded literal pairs each (e.g. "30 days" vs "90 days" specifically).
    The new fallback extracts actual numbers (day counts, member counts,
    N:N ratios) and compares them generically — only after the existing
    category keyword gate passes, only when both sides have an extractable
    number, and at a lower confidence (0.75) than the literal rules
    (0.85–0.95) since it's a heuristic match rather than a confirmed one.
    Funding-ratio extraction additionally requires a "ratio"/"प्रमाण" token
    in the same sentence, so unrelated colon-formatted numbers (GR numbers,
    times) are never misread as a ratio.

### PDF export fixes (`frontend/src/utils/pdfExport.js`)

- **Conflict Detection Report PDF**: removed the "Confidence: X%" tag from
  each conflict block and the "Highest Confidence Score" summary stat —
  confidence no longer appears anywhere in the downloaded conflict PDF
  (it's still shown on-screen in the app, only the PDF was changed).
- **Generated GR document PDF** (`generateGRDocumentPDF`): fixed a bug
  where the exported PDF showed a duplicated header and a broken/empty
  references block. Root cause: the Tiptap editor's content
  (`editor.getHTML()`, produced by `convertGRToHTML`) already **is** the
  complete document — header, references, body, and signature all
  included — but the PDF export was wrapping that in a *second*,
  separately-built header/subject/references/signature block on top. The
  export now renders the editor's HTML as-is, styled to match Tiptap's own
  fonts/sizes exactly (`GR_DOC_STYLES` mirrors `index.css`'s
  `.lang-marathi`/`.lang-english .ProseMirror` rules). Callers
  (`DraftViewer.jsx`, `History.jsx`) were updated to match the simplified
  function signature (`generateGRDocumentPDF(draft, bodyHtml)` — the
  `references`/`officer` params were dropped since that content is already
  inside `bodyHtml`).

### Environment

- **`.env`**: `ALEMBIC_DATABASE_URL` was pointed at a Postgres role
  (`kumarjayanttambe`) that only exists on a teammate's machine. Fixed to
  use the actual local superuser role for the machine it was tested on.
  **This value is machine-specific — on the new PC you must set this to
  whatever your own Postgres superuser role is** (see Step 6 below), not
  copy the value from this repo's `.env` verbatim.

None of the above touched FAISS, the embedding model, the LLM prompt, or
any database schema — safe to treat as drop-in on any machine once the
environment itself (Postgres, Ollama, Node, Python deps) is set up.

---

## 1. Prerequisites

Install these first, in this order:

| Tool | Version used | Get it |
|---|---|---|
| Python | 3.14.x (3.11+ should work) | https://www.python.org/downloads/ |
| Node.js | v22.x | https://nodejs.org |
| PostgreSQL | 18.x | macOS: `brew install postgresql@18` · Windows/Linux: https://www.postgresql.org/download/ |
| Ollama | latest | https://ollama.com/download |
| git | any recent version | usually already installed |

After installing Ollama, pull the model this project uses:
```bash
ollama pull gemma3:4b
```

## 2. Get the project onto the machine

Copy/clone everything **except** `backend/data/` and `mahGRs-main/` (per
the "Before you start" section above — copy `backend/data/glossary/`
separately by hand, it's tiny and required).

Also skip copying (all regenerated by the steps below, just wastes space
if transferred):
- `venv/`
- `frontend/node_modules/`
- `backend/__pycache__/` and any other `__pycache__/` folders
- `backend/data/nirn_store.db` (self-creates on first run — irrelevant here
  anyway since the whole `backend/data/` folder is excluded)

## 3. Backend: Python environment

```bash
cd "NIRN KUMAR"                 # or whatever the folder is named on this machine
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Download the search index (the step that must succeed)

From the project root, with the venv active:
```bash
python setup.py
```

This checks for `backend/data/index.faiss`, `chunks.pkl`, and
`metadata.json`; since none exist yet on this machine, it installs `gdown`
if needed and downloads the prebuilt embeddings from the project's shared
Google Drive folder (~6 GB — needs a real internet connection, will take a
while).

**After it finishes, verify:**
```bash
ls -la backend/data/
```
You must see `index.faiss` (~2.3 GB) and `chunks.pkl` (~4.1 GB) — those are
the only two files the running app actually reads
(`backend/retrieval.py`'s `_load_faiss()`). If `setup.py` reports it's
looking for `metadata.json` specifically and the download produced
`metadata.txt` instead, that's fine — `metadata.txt`/`.json` isn't loaded
by the running app at all, only `index.faiss` + `chunks.pkl` matter.

**Then check the glossary folder landed too:**
```bash
ls -la backend/data/glossary/
```
If it's empty or missing, copy the six JSON files there by hand (see
"Before you start" #1) — the backend will not start without
`government_knowledge_base.json` specifically.

If this step fails (network/quota/access error), see Troubleshooting below
— there is no quick local alternative on a machine without `mahGRs-main`.

## 5. PostgreSQL: create the database and app role

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
only has SELECT/INSERT/UPDATE/DELETE — no schema-modifying privileges.

## 6. Configure environment variables

```bash
cp .env.example .env
```
Edit `.env`:
- `DATABASE_URL` — set the password to match `NIRN_APP_PASSWORD` from Step 5.
- `ALEMBIC_DATABASE_URL` — set the user to **your own** Postgres superuser
  role name from Step 5. Do not reuse the value from another machine's
  `.env` — this is exactly the mistake that had to be fixed this session
  (see "What changed" above); it's always local-machine-specific.
- `JWT_SECRET` — generate a fresh one:
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
```
`seed.py` prints the seeded login credentials when it finishes — save that
output. Defaults if you don't have it:

| Login ID | Password | Role |
|---|---|---|
| `admin` | `NirnAdmin#2026` | Admin |
| `priya.sharma` | `Officer#Pass01` | Officer |
| `rahul.deshmukh` | `Officer#Pass02` | Officer |

Both officer accounts are forced to change their password on first login.
**Change these credentials before this ever runs anywhere other than your
own machine.**

## 7. Frontend

```bash
cd frontend
npm install
```

If you hit an error like `Cannot find module @rollup/rollup-<platform>`
or a `dlopen`/code-signature failure when you later run `npm run dev` —
this is a known npm optional-dependencies bug, not a project problem. Fix:
```bash
rm -rf node_modules package-lock.json
npm install
```

## 8. Run it

Three things running at once, each in its own terminal:

```bash
# Terminal 1 — Ollama (skip if already running as a background service)
ollama serve

# Terminal 2 — backend (from the project root, with venv active)
cd backend
uvicorn app:app --reload

# Terminal 3 — frontend
cd frontend
npm run dev
```

Open **http://localhost:3000**. The frontend dev server proxies `/api` and
`/health` to the backend on port 8000 automatically.

## 9. Verify it actually works

- Log in as `admin` / `NirnAdmin#2026`.
- Go to Draft GR, generate a draft — this calls Ollama, so the first
  generation can take 30–60s.
- Check the Policy Conflicts tab populates after generation.
- Try Search from the home page and confirm results come back — this is
  what proves `index.faiss`/`chunks.pkl` downloaded and loaded correctly.
- Download the generated draft as PDF and DOCX and confirm both open and
  read correctly (verifies the PDF export fix from this session).
- Download a Conflict Detection Report PDF and confirm it no longer shows
  a confidence score/percentage anywhere.

---

## Troubleshooting

**Backend won't start / crashes on startup with `KnowledgeBaseLoadError`**
`backend/data/glossary/government_knowledge_base.json` is missing. See
"Before you start" #1 — copy the `glossary/` subfolder by hand.

**`python setup.py` fails (quota, access, network error)**
There is no local rebuild fallback on this machine (see "Before you start"
#2 — both alternatives need `mahGRs-main`, which isn't here). Get
`backend/data/index.faiss` and `backend/data/chunks.pkl` from the original
machine directly (USB drive, external SSD, shared drive link) instead.

**`ModuleNotFoundError: No module named 'psycopg2'` when running `alembic upgrade head`**
Alembic needs the sync Postgres driver even though the app itself uses the
async one. It's in `requirements.txt` (`psycopg2-binary`) — make sure the
venv is active and `pip install -r requirements.txt` ran in it.

**Login returns 500, or `alembic`/`seed.py` fail with a role/connection error**
Almost always Postgres isn't running, or `ALEMBIC_DATABASE_URL` in `.env`
has the wrong superuser role name for *this* machine. Re-check Step 6.

**Search returns no results / draft generation says the corpus is empty**
`backend/data/index.faiss` and `chunks.pkl` are missing, empty, or in the
wrong place. Re-check Step 4.

**Frontend dev server crashes with a rollup/`@rollup/rollup-<platform>` error**
See Step 7 — `rm -rf node_modules package-lock.json && npm install`.

**Draft generation hangs or times out**
Ollama isn't running, or `gemma3:4b` wasn't pulled. Run `ollama list` to
check.

**Port already in use (3000 or 8000)**
Something else is using it. Stop that process, or change the port —
backend: `uvicorn app:app --reload --port 8001` and update the proxy
target in `frontend/vite.config.js`; frontend: `vite.config.js`'s
`server.port`.
