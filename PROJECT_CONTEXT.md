# NIRN.Ai - Project Context Document

This document provides a comprehensive technical overview of the **NIRN.Ai** repository. It is designed to quickly onboard AI coding assistants, agents, or human engineers by explaining the architecture, data flow, key technologies, and recent architectural optimizations.

## 1. Project Overview

NIRN.Ai is an AI-assisted Government Resolution (GR) drafting and analysis platform built for the Government of Maharashtra. The primary goal is to help government officers draft new policies while automatically detecting conflicts with existing policies, ensuring standard legal terminology is used, and tracking references. 

It handles bilingual data natively, heavily focusing on **Marathi** and **English** text.

### Core Capabilities
1. **AI Copilot Drafting**: Generates a draft GR using a local LLM based on user prompts and retrieved context from the FAISS vector database.
2. **Conflict Detection**: Cross-references the generated draft against existing GRs to identify policy, funding, authority, or timeline contradictions.
3. **Reference Tracking**: Identifies which existing laws/GRs are explicitly or implicitly referenced in the new draft.
4. **Terminology Mapping**: Ensures standard bilingual legal glossaries are respected (e.g., translating informal English terms into authoritative Marathi administrative terms).

---

## 2. Technology Stack

- **Frontend**: React.js (Vite), Tailwind CSS.
- **Backend**: FastAPI (Python), Uvicorn.
- **Database**: PostgreSQL (hosted on Neon), accessed asynchronously via SQLAlchemy and `asyncpg`.
- **Vector Search**: FAISS (Facebook AI Similarity Search) running locally.
- **Embeddings Model**: `intfloat/multilingual-e5-base` (SentenceTransformers) for bilingual semantic search.
- **Language Model (LLM)**: Local execution via **Ollama** running `gemma3:4b`.

---

## 3. Key Architectural Components (Backend)

The backend (`backend/` directory) is where all AI and business logic resides.

### `routes.py`
The API entry point. Implements endpoints for authentication, document CRUD, Copilot chat, and the core `/api/copilot/draft` endpoint. All database queries are delegated to `db/repositories/`.

### `llm.py`
The single source of truth for communicating with the Language Model. 
- **`call_model`**: Manages the HTTP client (`httpx`) to the Ollama server. Implements rate-limiting, caching, and retry logic. 
- **`detect_conflicts`**: Takes a set of draft clauses and a set of retrieved candidate clauses, runs them through a deterministic rule engine first, and then sends the remaining candidates to the LLM in a single batched prompt.
- **`split_into_clauses`**: Rule-based text splitter that breaks a GR into operative clauses (supports both English and Devanagari numbering).

### `retrieval.py`
Handles semantic search over the corpus.
- **`search_batch`**: The highly optimized entry point for finding similar existing GRs. It takes multiple clauses, embeds them all in a *single forward pass* using `SentenceTransformer.encode()`, and queries the FAISS index simultaneously. 

### `conflict_detection/__init__.py`
The orchestration layer for conflict detection. 
1. Splits the draft text into clauses (`llm.py`).
2. Performs a batched retrieval of candidate clauses from the corpus (`retrieval.py`).
3. Sends the flattened candidates to the LLM for evaluation (`llm.py`).
4. Filters the results based on a confidence threshold (`settings.CONFLICT_CONFIDENCE_FLOOR`).

### `profiler.py`
A lightweight, thread-local performance profiling utility. 
- Enabled by setting `PROFILE_PERFORMANCE=True` in the `.env` file.
- Uses `time.perf_counter()` to trace the execution time of major pipeline stages (Retrieval, LLM, Database writes) and constructs a nested timing tree.
- Automatically injects a Base64 encoded `X-Performance-Profile` header into HTTP responses so the frontend can decode and print the metrics to the browser console.

---

## 4. Recent Performance Optimizations

The pipeline was heavily optimized to reduce latency (Drafting: ~40s -> ~20s, Conflict Detection: ~110s -> ~30s on Apple Silicon). If modifying this repository, **do not undo these optimizations**:

1. **Batched Embeddings**: Previously, `retrieval.py` embedded clauses inside a Python loop (one forward pass per clause). It now uses `search_batch` to embed all clauses simultaneously, allowing GPU/MPS hardware to parallelize the matrix multiplication.
2. **Batched LLM Verification**: Previously, conflict detection sent one Ollama HTTP request per `(clause, candidate)` pair (up to 40 sequential HTTP calls). Now, it batches all candidates for a single clause into one prompt, dropping the maximum LLM network calls to just the number of clauses (e.g., max 10).
3. **HTTP Keep-Alive**: `llm.py` now uses a persistent `httpx.Client()` singleton. This prevents tearing down and rebuilding TCP connections to the Ollama server 40+ times per request.
4. **Local Rate-Limiting Bypass**: The backend `_TokenBucket` previously forced `time.sleep()` delays between requests. This was bypassed for local Ollama calls, eliminating artificial blocking.

---

## 5. Schema Conventions & Rules

- **Database Queries**: Never use raw SQL. Always use SQLAlchemy's `select()` statements inside `backend/db/repositories/`.
- **Error Handling**: Use FastAPI's built-in validation (Pydantic schemas in `schemas.py`). Let FastAPI automatically return 422 errors for malformed requests.
- **Formatting**: The project uses strict JSON formatting for LLM responses. `parse_json_reply` handles cleaning up markdown fences (` ```json `) returned by the LLM.
- **Auth**: The `/api/copilot/*` endpoints require authentication. The frontend passes a Bearer token.

## 6. Development Workflow

- Backend server: `../venv/bin/uvicorn app:app --reload --port 8000`
- Frontend server: `npm run dev` (starts Vite on port 3000)
- The Vite config proxies `/api` and `/health` requests directly to port 8000 to bypass CORS restrictions during development.
