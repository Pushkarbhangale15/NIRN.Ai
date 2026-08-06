# Architecture

```
                              USER

                                │

                     React Frontend (Vite, :3000)

                                │  /api (proxied to :8000)

                        FastAPI Backend

          ┌──────────────┬─────────────┬───────────────┐

     PostgreSQL       SQLite       FAISS Index      Ollama LLM
   officers, drafts,  chat-session  (multilingual-  (Gemma 3:4b,
   conflicts,         cache /        e5-base          local, offline)
   references,        GR-URL cache   embeddings)
   versions           (backend/store.py)
   (backend/db/)
```

Two databases, deliberately: PostgreSQL holds everything with real
integrity/auth requirements (officers, drafts, conflicts, references,
draft version history — see `backend/db/models.py`); the older SQLite
store (`backend/store.py`) survives only for chat-session state and a
GR-URL lookup cache, neither of which needs relational guarantees.

## Draft generation flow

1. Officer submits a brief + department + language.
2. Backend retrieves similar existing GRs from the FAISS index
   (`backend/retrieval.py`) for style/reference context.
3. LLM generates the draft (`backend/prompts.py` + `backend/llm.py`),
   using the retrieved context and the day's actual date.
4. Output is cleaned (strips any stray markdown code fences) and
   validated for leftover placeholders before being persisted.

## Conflict detection flow

1. The draft's operative clauses are extracted and boilerplate/procedural
   clauses (fund-disbursement steps, committee evaluation language, etc.)
   are filtered out before they ever reach retrieval — see
   `backend/conflict_detection/__init__.py`.
2. Each remaining clause is checked against FAISS-retrieved candidates by:
   - a deterministic rule engine (`rule_engine.py`, no LLM call), then
   - an LLM verifier (`llm_verifier.py`) for semantic/ambiguous cases,
     which must report `beneficiary_match`/`scope_match` before assigning
     a verdict — a lexical-only match with no actual overlap on either
     axis gets auto-downgraded from `conflict` to `overlap`.
3. Conflicts are persisted per-draft (`db/repositories/conflicts.py`),
   deduplicated against that draft's own still-open conflicts on repeat
   analysis runs.

## Conflict resolution flow

`POST /api/conflicts/{id}/resolve` revises just the flagged clause (one
LLM call) and re-verifies it (a second call) — never the whole draft or
the full conflict batch. `POST /api/conflicts/{id}/resolve/accept` patches
only that clause into the draft and durably marks the conflict
`resolved`, so the state survives a page reload or a fresh analysis run
rather than being recomputed from scratch each time.

## Ingestion (offline, one-time)

1. Raw GRs (`mahGRs-main/`) are chunked (`backend/gr_assistant/`).
2. Chunks are embedded with `intfloat/multilingual-e5-base`
   (SentenceTransformers).
3. Vectors are stored in a FAISS index (`backend/data/index.faiss`) with a
   parallel chunk-metadata store (`backend/data/chunks.pkl`).

The corpus chunk schema carries `title`, `gr_number`, `issued_on`, and
`cited_references` fields — added when the index was rebuilt from a
partial (~4,929 GR) to a full-corpus (~98,929 GR) embed via
`kaggle/build_gr_index.ipynb`. See `SETUP.md` Step 5 for how to obtain or
regenerate `index.faiss`/`chunks.pkl`.
