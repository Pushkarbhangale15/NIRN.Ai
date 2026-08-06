# Changes by Pushkar — Conflict Detection & Resolution Session

This document covers everything changed in this session: the OCR-upload
conflict bug, the three-part conflict-resolution improvement plan (count
bug → resolution quality → batch UI), and a transaction bug found during
final regression testing. Each section says what changed, why, and how to
test it yourself in the running app.

---

## 0. Setup note (not a code change)

The three-tier draft approval workflow migration (`bd393fbabd3f` →
`afd8d23e266f`) was already committed to the branch but not yet applied to
the local Postgres DB. Ran `alembic upgrade head` to bring the DB current —
see `approval.md` for what that migration itself contains. Also confirmed
the cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) is live in the
conflict-detection retrieval pipeline (`backend/conflict_detection/reranker.py`).

---

## 1. OCR Upload — conflicts silently disappearing

**Bug**: uploading a scanned GR ran conflict detection *twice* — once in
the background OCR pipeline (`backend/ocr_ingest/pipeline.py`), once again
when the frontend called `runFullAnalysis` right after. Since detection is
an LLM pass and not perfectly deterministic run-to-run, the second run
could find fewer (or zero) conflicts than the first, and the UI showed
whatever the second run found — silently dropping real, already-detected
conflicts.

**Fix**: `run_conflict_detection` (`backend/routes.py`) now carries forward
any previously-persisted, still-open conflict that the fresh pass didn't
happen to reproduce, instead of trusting the fresh pass as the sole source
of truth.

### How to test
1. Log in as `admin` / `NirnAdmin#2026`.
2. Go to **Check Conflicts** → upload a scanned GR PDF/image.
3. Wait for OCR to finish and conflicts to populate.
4. Note the conflict count. Reload the page / re-open the draft from
   **History** — the count should not drop.

---

## 2. Conflict Resolution Improvements (the main body of work)

Three problems, tackled in order: the resolved-count bug, then resolution
*quality*, then a batch-selection UI. All changes are on the `Draft GR`
page's **Policy Conflicts** tab.

### Problem 1 — Conflict count inflating after "Resolve All" (e.g. 8 → 16)

**Root cause**: after resolving conflicts, the frontend called
`POST /api/analysis/{id}` to refresh the list — a full, fresh, non-deterministic
re-detection pass. A second pass could find a different set of conflicts
than the first, and old still-open ones were also kept, so repeated
resolve batches made the count balloon.

**Fix**:
- `frontend/src/pages/Draft.jsx` — the post-resolve refresh now calls
  `GET /api/drafts/{id}/conflicts` (a plain read of what's already
  persisted) instead of re-running detection.
- `frontend/src/utils/conflictMapping.js` (new) — maps that endpoint's
  response shape to what the UI components expect.
- `backend/routes.py` — `run_conflict_detection` simplified: removed the
  duplicated `resolved_hits`/`stale_open_hits` construction in favor of one
  shared `_conflict_row_to_hit` helper.

**How to test**:
1. Open a draft with several conflicts on the **Policy Conflicts** tab.
2. Click **Resolve All Conflicts**, let it finish.
3. Click **Resolve All Conflicts** again (or reload the page).
4. Confirm the conflict count only reflects what's actually still open —
   it should never grow between refreshes.

### Problem 2 — Resolution quality (the AI-generated fixes were often generic)

- `backend/prompts.py` — `CONFLICT_RESOLUTION` prompt now includes the
  draft's own department + brief as context, and a chain-of-thought
  instruction (reasoned internally, not shown in output) so the model
  considers *why* the clause exists before rewriting it.
- New 4th resolution strategy: **`defer_to_existing`** — explicitly
  subordinates the draft clause to the existing GR instead of just
  rewording it. Added to `backend/schemas.py` (`ResolutionStrategy` enum)
  and to the frontend's auto-resolve fallback chain
  (`Draft.jsx`: `["reword", "add_carve_out", "defer_to_existing"]`).
- **Still-conflicting explanation**: when an auto-resolve attempt doesn't
  clear the conflict, the backend now makes one extra small LLM call
  (`STILL_CONFLICTING_REASON` prompt) to explain *why*, in one sentence,
  and persists it (`resolved_reason` column) so it survives a reload.

**How to test**:
1. Pick an unresolved conflict on the Policy Conflicts tab, click its
   individual **Resolve** action (or let **Resolve All** run — it now
   tries `defer_to_existing` as a third fallback if reword/carve-out fail).
2. Check that a resolved clause reads naturally and references the
   specific conflicting GR, not a generic rewording.
3. If a conflict shows "still conflicting" after an attempt, confirm there's
   now a one-sentence explanation of *why* (not just a generic warning).

### Problem 3 — Batch selection UI (checkboxes + 3 actions)

`frontend/src/components/drafting/ConflictCard.jsx` gained:
- A checkbox per conflict, and a selection toolbar (appears once 1+ are
  selected) with three actions:
  - **Resolve Selected** — same sequential LLM-resolve loop as "Resolve
    All", scoped to just the checked items.
  - **Manually Edit Selected** — enabled only when exactly one conflict is
    checked. Highlights that clause directly in the Tiptap editor
    (`frontend/src/utils/findClauseInDoc.js`, new — locates the clause text
    in the document; `@tiptap/extension-highlight`, new dependency) and
    scrolls to it. Officer edits it by hand, clicks the normal **Save**,
    then clicks **Mark as Resolved** in the banner that appears above the
    editor. This calls a new backend endpoint,
    `POST /api/conflicts/{id}/resolve/mark-resolved`
    (`backend/routes.py`), which marks the conflict resolved *without*
    re-patching the draft content — the officer's own save already did that.
  - **Ignore Selected** — dismisses the selected conflicts (reuses the
    existing dismiss endpoint), prompting once for a shared reason rather
    than once per conflict. Ignored conflicts move into a collapsed
    **"Ignored Conflicts"** section at the bottom of the panel — greyed
    out, read-only, showing the reason — and are excluded from every count
    and every batch action above.

**How to test**:
1. On the Policy Conflicts tab, check 2+ conflicts — a toolbar appears
   with **Resolve Selected / Manually Edit Selected / Ignore Selected**.
   "Manually Edit Selected" is disabled unless exactly one is checked.
2. **Resolve Selected**: check 2 conflicts, click it — only those two
   resolve; everything else is untouched. Progress shows `(done/total)`
   while running.
3. **Ignore Selected**: check 1–2 conflicts, click it, enter a reason once
   — they disappear from the active list and appear in the collapsed
   **"Ignored Conflicts"** section at the bottom with that reason. The
   header badge splits into e.g. "6 Conflicts Detected" + "2 Ignored".
4. **Manually Edit Selected**: check exactly one conflict, click it — the
   editor scrolls to and highlights (yellow) the flagged clause, and an
   amber banner appears above the editor. Rewrite the highlighted text,
   click **Save**, then click **Mark as Resolved** in the banner. The
   conflict should show as resolved and the banner disappears. Reload to
   confirm it stuck.

---

## 3. Bug found during final regression testing (fixed)

While testing "Resolve All" against several conflicts at once, some
correctly failed with a 409 ("flagged clause no longer matches current
draft content" — a known, pre-existing issue when two conflicts share
overlapping draft text). But the failure was never actually recorded: the
conflict stayed at `not_attempted` forever instead of `attempted_error`,
because the database session's rollback-on-exception behavior
(`backend/db/base.py`'s `get_session()`) was silently discarding the status
write the moment before the request's own error response went out.

**Fix**: `backend/routes.py` — new `_record_resolve_attempt_durable()`
helper writes that status on its own independent, immediately-committed
session, so it survives even though the overall request still returns an
error to the caller. Applied everywhere a resolve attempt is recorded right
before the endpoint raises.

**How to test**: hard to trigger deliberately from the UI (needs two
conflicts anchored to overlapping draft text), but if you hit a "could not
be cleared" result during **Resolve All**/**Resolve Selected**, that
conflict should now show `attempted_error` on reload — not silently reset
to looking untouched.

---

## Files touched this session

**Backend**
- `backend/routes.py` — count-bug fix, `mark-resolved` endpoint, durable
  failure recording, prompt context wiring
- `backend/prompts.py` — `defer_to_existing` strategy, CoT instruction,
  department/brief context, `STILL_CONFLICTING_REASON` prompt
- `backend/schemas.py` — `DEFER_TO_EXISTING` enum value, `still_conflicting_reason`,
  `is_dismissed`/`dismissed_reason` on `ConflictHit`, `MarkResolvedRequest`/`Response`
- `backend/db/repositories/conflicts.py` — `record_resolve_attempt` gained
  an optional `reason` param

**Frontend**
- `frontend/src/pages/Draft.jsx` — post-resolve refresh fix, batch
  generalization (`resolveConflictBatch`), ignore/manual-edit wiring
- `frontend/src/components/drafting/ConflictCard.jsx` — checkboxes, action
  toolbar, Ignored Conflicts section
- `frontend/src/components/drafting/DraftViewer.jsx` — highlight extension,
  locate-and-scroll effect, Mark as Resolved banner
- `frontend/src/utils/conflictMapping.js` (new)
- `frontend/src/utils/findClauseInDoc.js` (new)
- `frontend/src/api.js` — `markConflictResolved` wrapper
- `frontend/package.json` — added `@tiptap/extension-highlight`
