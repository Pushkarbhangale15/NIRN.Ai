# One-off scripts

Historical migration/experiment scripts, already run once against this
project's own data. **Nothing in the running app imports anything from
this folder** (verified: no `import` of these modules anywhere under
`backend/` or `frontend/`) — they exist purely as a record of how the
current `backend/data/index.faiss` came to be, in case the same tuning
work needs to be redone from scratch.

They are not wired into `app.py`, not run by any startup/build step, and
not referenced by `requirements.txt` beyond dependencies (`faiss`,
`numpy`) already needed elsewhere.

| Script | What it did |
|---|---|
| `build_ivfpq.py` | One-time conversion of the original flat `IndexFlatIP` (9 GB, exact) to a compressed `IndexIVFPQ`. Fixed RAM/swap thrashing on this machine, but recall dropped to ~30% — superseded by `build_ivfsq.py`. |
| `build_ivfsq.py` | Second attempt: `IndexIVFScalarQuantizer` (int8, ~4x compression) instead of PQ (~32x compression) — better recall fidelity. |
| `build_faiss.py` | Deprecated even before the move here — reads from paths (`data/embeddings.npy`, `data/chunks.json`) that predate the current pipeline. The FAISS index is now built by `kaggle/build_gr_index.ipynb` instead. Kept only as a historical reference; safe to delete outright. |

If you ever do need to re-run `build_ivfpq.py` / `build_ivfsq.py`, they
resolve `backend/data/` relative to their own file location (not your
current directory), so they can be invoked from anywhere, e.g.:
```bash
python backend/one_off_scripts/build_ivfpq.py
```
