# Backend changes needed for the new GR index

> **Status: implemented on the `prasad` branch already.** Sections 1–4 below have been applied to
> `backend/schemas.py`, `backend/retrieval.py`, and `backend/conflict_detection/`. If the other
> machine is working from a copy of this repo, pull/merge `prasad` first — this doc is then just a
> record of *what* changed and *why*, useful for review or for reapplying against a divergent copy.

## Context

The old `backend/data/index.faiss` + `chunks.pkl` only covered ~4,929 of the ~98,929 GRs in the
corpus (built from a partial run). A new index is being rebuilt on Kaggle (2x T4 GPUs) from the
full corpus at `orgpedia/mahGRs`, using `intfloat/multilingual-e5-base` embeddings — same model
`retrieval.py` already loads, so no embedding-side changes are needed.

The rebuild is a **drop-in replacement**: same three filenames, same directory
(`backend/data/index.faiss`, `backend/data/chunks.pkl`, `backend/data/metadata.json`). Just copy
the new files over the old ones. But the **chunk schema has grown** — new fields are populated
that used to be absent — and the conflict-detection pipeline should be updated to actually use
them, since that's the whole point of rebuilding.

## Old chunk schema (what's in `chunks.pkl` today)

```python
{"gr_id": str, "department": str, "language": "mr"|"en", "chunk_id": int, "text": str}
```

## New chunk schema (what the rebuilt `chunks.pkl` will contain)

```python
{
    "gr_id": str,
    "department": str,
    "language": "mr" | "en",
    "chunk_id": int,
    "text": str,                    # now clause-level, with a compact header line prepended:
                                     # "[Department | Title | GR Number | Date]\n\n<clause text>"
    "title": str | None,            # parsed GR subject line
    "gr_number": str | None,        # parsed "Government Resolution No" / "शासन निर्णय क्रमांक"
    "issued_on": str | None,        # ISO date (YYYY-MM-DD), parsed from the header
    "cited_references": list[str], # raw "Read-" / "वाचा" citation lines from this GR's own header
}
```

`metadata.json` is regenerated as one entry per source file (`gr_id` + `language`) with the same
new fields (minus `text`/`chunk_id`), always in sync with `chunks.pkl` since both come from the
same build run.

## Required changes

### 1. `backend/retrieval.py` — mostly already compatible, verify and extend

- `search()` already does `chunk.get("title", ...)` and `chunk.get("issued_on")` — these will now
  resolve to real values instead of always falling back to defaults. No change needed there.
- Add `gr_number` and `cited_references` to the `CorpusHit` construction in `search()` and
  `lookup_by_gr_number()` / `get_full_ocr()` so they flow through to the rest of the app instead of
  being dropped at the retrieval boundary.

### 2. `backend/schemas.py` — extend `CorpusHit`

Add fields so the new metadata survives past retrieval:
```python
gr_number: Optional[str] = None
cited_references: List[str] = []
```

### 3. `backend/conflict_detection/` — use the new fields for higher-trust conflict checks

- `backend/conflict_detection/__init__.py` currently builds `matched_gr_title=hit.title` — this
  alone gets fixed for free once `title` is populated (no more `"GR {gr_id}"` placeholders in the
  LLM verifier prompt).
- Extend the conflict pipeline to also pass `issued_on` and `gr_number` into
  `llm_verifier.py`'s prompt (currently only `matched_gr_id` + `matched_gr_title` are passed) —
  giving the LLM a date lets it reason about supersession ("is this an older GR the draft's clause
  would contradict, or a newer one that already updated the rule").
- New opportunity: use `cited_references` as a second signal alongside embedding similarity. When
  a corpus hit's `cited_references` mentions a `gr_number` that matches another candidate/hit
  already in play, treat that as a stronger, citation-backed relationship rather than a purely
  semantic one — this is the main lever for making conflict detection "most trustable" rather than
  just similarity-based guessing. Where to hook this in is a design call for whoever implements it
  (likely inside `rule_engine.py` or as a pre-filter before `llm_verifier.py` is invoked) —
  decide based on how `CANDIDATES_PER_CLAUSE` candidates are currently gathered in
  `backend/conflict_detection/__init__.py`.

### 4. Retire the duplicate/incompatible builder scripts

- `backend/gr_assistant/build_faiss.py` reads from a different, no-longer-relevant source
  (`data/embeddings.npy` + `data/chunks.json`) and is superseded by the Kaggle notebook. **Already
  marked** with a `DEPRECATED` header comment pointing at `kaggle/build_gr_index.ipynb` — safe to
  delete outright once confirmed unused.
- `backend/gr_assistant/search.py` embeds queries with `paraphrase-multilingual-MiniLM-L12-v2` —
  a **different model** than `retrieval.py` uses (`intfloat/multilingual-e5-base`). It was never
  wired into the actual query path. **Already marked** with a `DEPRECATED` header comment — safe to
  delete outright once confirmed unused.
- `build_embeddings.py` (project root) and `setup.py`'s local-regeneration path are now superseded
  by the Kaggle notebook as the source of truth for `backend/data/*`. Decide whether to keep them
  for local regeneration or remove them in favor of "run the Kaggle notebook, copy the zip output."

### 5. No changes needed to

- `backend/store.py` (SQLite drafts/sessions) — untouched by this rebuild.
- The FAISS index type/format (`IndexFlatIP`, cosine via normalized inner product) — unchanged.
- `backend/config.py`'s `CHUNK_CHARS`/`CHUNK_OVERLAP` — the notebook's chunking uses the same
  500/100 values, so no drift between what these settings imply and what's actually in the index.

## Verification after swapping files in

1. `len(chunks) == index.ntotal` (the notebook already asserts this before export).
2. Unique `(gr_id, language)` pairs in `chunks.pkl` should be ~98,929 × 2, not ~4,929 — confirms
   full-corpus coverage instead of the old partial index.
3. Spot-check a few `/search` and `/conflict` responses to confirm `title`/`issued_on` are now real
   values, not `"GR {gr_id}"` / `null`.
