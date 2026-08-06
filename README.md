# NIRN.Ai

> **NIRN.Ai** is an AI-powered Government Resolution (GR) drafting and alignment assistant, built around the Maharashtra Government Resolution corpus.

It helps government officers draft new Government Resolutions, retrieve relevant existing GRs, detect cross-departmental policy conflicts, and resolve them — using Retrieval-Augmented Generation (RAG) over a 98,950+ GR corpus and a locally-run LLM.

---

## ✨ Features

- 📄 AI-assisted Government Resolution drafting with **Rich Text Editing (Tiptap)**
- 🔍 Semantic search across the Maharashtra GR corpus
- ⚠ Cross-departmental policy conflict detection (deterministic rule engine + LLM verification)
- 🩹 One-click conflict **resolution** — revise a flagged clause, re-verify it clears, and persist the fix
- 📎 Upload a GR as a text-based PDF/DOCX/TXT, or paste text directly, to check it against the corpus
- 📚 Automatic reference (citation) resolution against the corpus
- 🌐 Bilingual support (Marathi & English) with optimized font rendering
- 🔐 Officer/Admin authentication (JWT), draft history, and PDF/DOCX export
- ⚡ Runs 100% offline: local Ollama LLM, local FAISS vector search, local PostgreSQL

---

## 🏗 Tech Stack

| Layer | Technology |
|--------|------------|
| Frontend | React, Vite, Tiptap, Framer Motion |
| Backend | FastAPI, Uvicorn, SQLAlchemy (async) |
| Database | PostgreSQL (officers/drafts/conflicts), SQLite (chat-session cache only) |
| Embeddings | SentenceTransformers (`intfloat/multilingual-e5-base`) |
| Vector Search | FAISS |
| Text chunking | LangChain text splitters |
| LLM | Ollama (Gemma 3:4b), local and offline |
| Dataset | Maharashtra Government Resolution corpus (~98,950 GRs) |

`torch`/`transformers`/`scikit-learn` appear in `requirements.txt` as
transitive dependencies of `sentence-transformers` — they aren't imported
directly by application code, so don't read them as separate architectural
choices.

---

## 📂 Project Structure

```text
NIRN PRASAD/
├── backend/              # FastAPI app
│   ├── conflict_detection/   # rule engine + LLM verifier
│   ├── db/                   # SQLAlchemy models + repositories (Postgres)
│   ├── alembic/               # DB migrations
│   ├── knowledge/            # government terminology/glossary loader
│   ├── gr_assistant/         # corpus chunking / embedding / FAISS build tools
│   ├── data/                  # FAISS index, chunks, glossary JSON (mostly gitignored)
│   └── scripts/              # local Postgres provisioning
├── frontend/             # React + Vite app
├── docs/                 # architecture, API reference, viva handbook
├── kaggle/               # notebook for a from-scratch corpus re-embed
├── mahGRs-main/          # raw GR corpus (gitignored, not required at runtime)
├── requirements.txt
├── SETUP.md              # full setup guide — start here
└── README.md
```

---

## 🚀 Quick Start

Full instructions, including PostgreSQL setup, environment variables, and
troubleshooting, are in **[SETUP.md](SETUP.md)** — read that first if this
is a new machine. Short version:

```bash
git clone <repository-url>
cd "NIRN PRASAD"

# Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Postgres (see SETUP.md for the provisioning script + .env details)
cp .env.example .env   # then edit DATABASE_URL / ALEMBIC_DATABASE_URL / JWT_SECRET
cd backend && alembic upgrade head && python3 seed.py && cd ..

# Ollama
ollama pull gemma3:4b
```

Then, in three terminals:
```bash
ollama serve
cd backend && uvicorn app:app --reload
cd frontend && npm run dev
```

Open **http://localhost:3000** and log in with the seeded admin account
(`admin` / `NirnAdmin#2026` — see SETUP.md, change before any non-local use).

---

## 🗃️ Search Index / Embeddings

The FAISS index (`backend/data/index.faiss`, ~2.3 GB) and chunk store
(`backend/data/chunks.pkl`, ~4.1 GB) are **not tracked in git** — too large,
and rebuildable. See **[SETUP.md](SETUP.md) Step 5** for:
- Downloading the prebuilt index (`python setup.py`, pulls from Google Drive).
- Rebuilding locally from raw text (`python build_embeddings.py`, needs
  `mahGRs-main/GRs`).
- The from-scratch Kaggle rebuild (`kaggle/build_gr_index.ipynb`) — the
  scripts under `backend/one_off_scripts/` are one-off migration tools
  from this project's history, not a repeatable pipeline (see that
  folder's own README.md; none of them are imported by the running app).

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [SETUP.md](SETUP.md) | Full setup guide — Postgres, `.env`, seeding, running, troubleshooting |
| [backend/README.md](backend/README.md) | Backend internals: SQL injection prevention conventions, auth model, seeded credentials |
| [docs/architecture.md](docs/architecture.md) | System architecture diagram |
| [docs/api.md](docs/api.md) | API route map (auth, drafts, conflicts, admin) |
