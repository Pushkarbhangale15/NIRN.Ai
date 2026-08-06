# NIRN.Ai — Three-Tier Draft Approval Workflow + Nav Rename

This document describes the changes made to add a three-tier approval
workflow (Drafting Officer → Reviewing Officer → Approving Authority)
on top of the existing draft-writing app, plus a nav/page rename from
"Upload GR" to "Check Conflicts". It exists so anyone pulling this
branch/repo can understand exactly what changed, where, why, and how
to test it end-to-end without re-deriving any of it from the diff.

---

## 1. Role model — no new role was added

The app already had a single `officer_role` enum with three values:
`officer`, `reviewer`, `admin` (`backend/db/models.py`, `OfficerRole`).
That enum was **reused as-is** — nothing was renamed or added to it in
the database. Only *display labels* were introduced, mapping the same
three values to the workflow's tier names:

| DB enum value (unchanged) | Displayed as (EN) | Displayed as (MR) | Tier |
|---|---|---|---|
| `officer` | Drafting Officer | मसुदा अधिकारी | Low — writes/submits drafts |
| `reviewer` | Reviewing Officer | पुनरावलोकन अधिकारी | Middle — reviews, edits, forwards |
| `admin` | Approving Authority | मंजूरी प्राधिकरण | High — final approve/return, plus existing admin/user-management powers |

Mapping lives in two places (backend has no server-rendered i18n, so
it's duplicated deliberately, once per side):

- `backend/role_labels.py` — `ROLE_DISPLAY_LABELS`, `role_display_label(role, language)` — used for readable server logs only, never sent as API response text.
- `frontend/src/constants/roles.js` — `ROLE_LABEL_KEYS`, `ROLES`, `roleLabel(role, t)` — used everywhere the UI shows a role name (queues, badges, dropdowns).

**Seed data does *not* include a reviewer account** (`backend/seed.py`
only creates one `admin` and two `officer` accounts — see §7). Create
a reviewer via the Admin panel (Admin → Officers → New Officer → role
`Reviewing Officer`) before testing the middle tier.

---

## 2. Database changes

Two new Alembic revisions, both applied on top of the existing chain
(`685491f43d1d` → … → `e40fcc005348`):

```
bd393fbabd3f  add content_sha256 and content_plain to draft_versions
afd8d23e266f  add three-tier draft approval workflow   (head)
```

> Run `cd backend && alembic upgrade head` after pulling. Both
> migrations have a working, tested `downgrade()`.

### `bd393fbabd3f` — integrity columns on `draft_versions`
- Adds `content_plain TEXT` and `content_sha256 VARCHAR(64)` to `draft_versions`.
- Backfills existing rows (`content_plain` via best-effort HTML-tag stripping, `content_sha256` via `hashlib.sha256`).
- Sets both columns `NOT NULL` only after the backfill.

### `afd8d23e266f` — workflow status + audit trail
- Widens `generated_drafts.status` from `(draft, under_review, finalised, archived)` to `(draft, submitted, reviewed, approved, returned, archived)` using Postgres's rename-recreate-swap pattern (there is no `ALTER TYPE … DROP VALUE`). Existing rows are migrated: `under_review → submitted`, `finalised → approved`.
- Adds `generated_drafts.returned_reason TEXT` (populated only when status = `returned`).
- Adds append-only table `draft_workflow_events`:

  | column | notes |
  |---|---|
  | `event_id` | PK |
  | `generated_draft_id` | FK |
  | `from_status`, `to_status` | the transition |
  | `actor_id`, `actor_role` | who did it, and in which tier |
  | `content_version_before`, `content_version_after` | which `draft_versions` rows bracket this event |
  | `decision` | enum: `submitted`, `edited_and_forwarded`, `forwarded_unchanged`, `accepted_reviewer_version`, `kept_original`, `returned` |
  | `note` | free text (e.g. the return reason) |
  | `created_at` | timestamp |

  This table has no UPDATE/DELETE code paths anywhere in the
  repository layer — append-only is enforced by code discipline, not
  a DB trigger.

---

## 3. Backend — new files

| File | Purpose |
|---|---|
| `backend/db/integrity.py` | `hash_content(content)` / `verify_content(content, expected_hash)` — SHA-256 over UTF-8 text, always server-computed, **never accepted from the client**. |
| `backend/diffing.py` | Word-level diff engine, separate from hashing. `_tokenize()` (regex `\s+|\S+`), `compute_diff(before, after)` via `difflib.SequenceMatcher`, `diff_summary()`. Operates on **plain text** (`content_plain`), never HTML. |
| `backend/role_labels.py` | See §1. |
| `backend/db/repositories/workflow.py` | `create_event(...)`, `get_workflow_history(session, draft_id)`, `get_latest_reviewer_names(session, draft_ids)` (batched to avoid N+1). |
| `backend/workflow_routes.py` | The whole approval-workflow router — see §5 for the endpoint list. |

## 3a. Backend — edited files

| File | What changed |
|---|---|
| `backend/db/models.py` | `DraftStatus` enum widened to 6 values; new `WorkflowDecision` enum; `GeneratedDraft.returned_reason` + `.workflow_events` relationship; `DraftVersion.content_plain` + `.content_sha256`; new `DraftWorkflowEvent` model. |
| `backend/db/repositories/drafts.py` | New exceptions `InvalidWorkflowStateError`, `DraftImmutableError`; `patch_draft_content` now blocks edits once `status = approved` (raises `DraftImmutableError`, mapped to HTTP 409); new functions `get_version_snapshot`, `submit_for_review`, `forward_to_approval`, `approve_draft`, `return_draft`, `list_review_queue`, `list_approval_queue`, `get_approval_view`. |
| `backend/schemas.py` | `Draft`/`DraftGenerateResponse`/`DraftHistoryItem`/`GeneratedDraftDetail` gained `status`/`returned_reason`; ~10 new schemas for the workflow endpoints (`ForwardToApprovalRequest`, `ApproveDraftRequest`, `ReturnDraftRequest`, `WorkflowEventOut`, `VerifyVersionResponse`, `DiffSegmentOut`, `DraftDiffResponse`, `WorkflowQueueItem`, `ApprovalViewResponse`, …). |
| `backend/routes.py` | Draft/detail serializers include new fields; `patch_draft` and `accept_conflict_resolution` catch `DraftImmutableError` → HTTP 409 with a clean JSON body (never a traceback). |
| `backend/admin_routes.py` | `DraftHistoryItem` construction includes `returned_reason`. |
| `backend/app.py` | Registers `workflow_router`. |

---

## 4. Integrity hashing (Task 1)

Every saved `draft_versions` row now carries a server-computed
`content_sha256`. It is:
- **Tamper-evidence, not diffing** — a fingerprint of exactly what was
  stored, not a comparison mechanism.
- Computed with `hashlib.sha256` in `backend/db/integrity.py`, never
  accepted as input from the client.
- Exposed via `GET /api/drafts/{id}/versions/{version_number}/verify`,
  which recomputes the hash from the stored content and reports
  match/mismatch.
- Shown in the UI via `frontend/src/components/HashBadge.jsx`
  (truncated hash + copy button + Verify button), used both in the
  Approval tab and in History's per-draft "Versions" panel.

---

## 5. Workflow endpoints (Task 4)

All in `backend/workflow_routes.py`. Ownership and role checks are
enforced **twice** — once in the route's `Depends()`, and again inside
the repository function — so a bug in one layer can't silently open a
hole.

| Method & path | Who | What |
|---|---|---|
| `POST /api/drafts/{id}/submit-for-review` | Drafting Officer, own draft, status=`draft` | `draft → submitted` |
| `GET /api/review-queue` | Reviewer/Admin | Drafts at `submitted` |
| `POST /api/drafts/{id}/forward-to-approval` | Reviewer, status=`submitted` | Optionally saves edited content, `submitted → reviewed` |
| `GET /api/approval-queue` | Admin | Drafts at `reviewed` |
| `GET /api/drafts/{id}/approval-view` | Admin | Diff (original vs reviewed) + hashes + history for one draft |
| `POST /api/drafts/{id}/approve` | Admin, status=`reviewed`. Body: `{decision: "accept_reviewer_version" \| "keep_original"}` | `reviewed → approved`; draft becomes immutable |
| `POST /api/drafts/{id}/return` | Reviewer or Admin. Body: `{reason}` (min 20 chars) | `→ returned`, reason stored, sent back to Drafting Officer |
| `GET /api/drafts/{id}/workflow-history` | Owner, Reviewer, Admin | Full `draft_workflow_events` timeline |
| `GET /api/drafts/{id}/versions/{n}/verify` | Owner, Reviewer, Admin | Recomputes & compares hash |
| `GET /api/drafts/{id}/diff?from_version=X&to_version=Y` | Owner, Reviewer, Admin | Word-level diff between two versions |

Every error path returns a clean JSON body (`{"detail": "..."}`) with
the correct status code — 403 for role/ownership violations, 404 for
missing drafts, 409 for invalid state transitions or edits on an
approved draft, never a raw 500 traceback.

**Decision enum mapping** — the request body uses present-tense values
(`accept_reviewer_version` / `keep_original`); the DB enum uses
past-tense (`accepted_reviewer_version` / `kept_original`). Mapped via
`_EVENT_DECISION` in `backend/db/repositories/drafts.py`.

---

## 6. Diff engine (Task 3)

`backend/diffing.py` — word-level diff via
`difflib.SequenceMatcher(autojunk=False)` on **plain text**
(`content_plain`), intentionally separate from the SHA-256 integrity
layer (hashing proves nothing changed; diffing shows what did).

Rendered by `frontend/src/components/drafting/DraftDiffView.jsx`:
- VS Code–style side-by-side: deletions highlighted on the left
  ("before"), insertions highlighted on the right ("after").
- Scroll is synchronized between the two panes.
- Stacks vertically on mobile.
- Summary line: "N additions, N deletions".
- Shows "No changes made at this stage" when the two versions are
  identical (e.g. reviewer forwarded without editing).

---

## 7. Frontend — Approval tab (Task 5)

New nav item **Approval**, visible only to Reviewing Officer / Approving
Authority (`frontend/src/App.jsx` — `RequireReviewerOrAdmin` guard,
redirects a Drafting Officer or anonymous visitor to `/` — never a
blank page). New page `frontend/src/pages/Approval.jsx`:

- **Reviewing Officer view** — queue of `submitted` drafts, opens an
  editable Tiptap view (reuses the existing editor), then either
  **"Forward without changes"** or **"Forward with my edits"**, each
  behind a confirmation dialog.
- **Approving Authority view** — queue of `reviewed` drafts, opens
  `DraftDiffView` + hash badges + `WorkflowHistoryList`, then
  **Accept reviewer's version**, **Keep original, discard edits**, or
  **Return for rework** (reason ≥ 20 chars). Approve is gated behind a
  "this is FINAL" confirmation modal — not an optimistic UI update.
- **Drafting Officer's own Draft page** (`frontend/src/pages/Draft.jsx`,
  `frontend/src/components/drafting/DraftViewer.jsx`) — shows an amber
  "returned for rework" banner with the reviewer/admin's reason when
  `status = returned`, and a **Submit for Review** button that appears
  once `status = draft` and the draft has been saved.
- Status badges everywhere share one source of truth:
  `frontend/src/constants/workflowStatus.js`
  (`DRAFT_STATUSES`, `statusLabel()`, `statusBadgeClass()`).

`frontend/src/pages/History.jsx` also gained a "Versions" panel per
draft (expandable), showing each version's truncated hash + Verify
button, reusing the workflow-history and version-verify endpoints
rather than a new listing endpoint.

---

## 8. Nav rename: "Upload GR" → "Check Conflicts" (Task 6)

- `frontend/src/pages/UploadGR.jsx` → renamed to
  `frontend/src/pages/CheckConflicts.jsx` (component renamed too, all
  `t()` keys renamed to `conflictcheck_*`).
- Nav label and page heading changed to "Check Conflicts" / "Check a
  GR for Conflicts" ("GR मधील संघर्ष तपासा").
- Old routes `/upload-gr` and `/upload` still work — they redirect to
  `/check-conflicts` (`frontend/src/App.jsx`), so no bookmark breaks.
- `frontend/src/LanguageContext.jsx` — ~18 confirmed-dead `upload_*`
  translation keys were removed; keys that were actually load-bearing
  were renamed, not deleted.

**Important finding, reported rather than silently "fixed":** the
original brief assumed this page only accepted pasted text and that
any upload UI/endpoint was leftover dead code. That's not true — the
page has three real, working input paths: paste text, PDF text
extraction (`POST /api/upload-gr/parse-file`), and async OCR upload
(`POST /api/gr/upload`). Both backend endpoints are live features, not
dead code, and were **not** removed or renamed — only the frontend
nav/heading/copy changed. The unrelated "Upload & Analyze" card on the
Home page (`frontend/src/pages/Home.jsx`) links to `/draft`, not this
page, and was left untouched.

---

## 9. What was intentionally left alone

- `frontend/src/pages/Analyze.jsx` — unrouted, unreachable dead code (no `/analyze` route exists). Out of scope for this change; not touched.
- `feat_upload_*` / `analyze_eyebrow` translation keys on the Home page — belong to the unrelated "Upload & Analyze" card, not this rename.

---

## 10. Two real bugs found and fixed during testing

1. **`frontend/src/pages/History.jsx` — `ReferenceError: statusBadgeClass is not defined`.**
   The function was called in JSX but never imported from
   `constants/workflowStatus.js`, which crashed the entire History
   page (blank page for every user) on load. `npm run build` didn't
   catch it because Vite/esbuild doesn't do exhaustive
   undefined-reference checking without ESLint (none is configured in
   this project). Fixed by adding the missing import. **Caught only
   by actually loading the page in a browser — a reminder to do that
   after any change, not just run the build.**

2. **Pre-existing infinite "Maximum update depth exceeded" loop on
   logout from any protected page** — reproducible before this
   feature work too, on a stock `/draft` page. Root cause:
   `<Navigate>`'s redirect effect has no dependency array, so it
   re-fires on every render; `AnimatePresence mode="wait"`
   (`frontend/src/App.jsx`, `PageWrapper`) keeps the exiting page's
   subtree — including the route guard — mounted and re-rendering
   throughout its ~250ms exit animation, which fired `navigate()`
   dozens of times per logout. Fixed by rewriting `RequireAuth`,
   `RequireAdmin`, and `RequireReviewerOrAdmin` in `App.jsx` to run the
   redirect inside a `useEffect` keyed on the real auth booleans,
   instead of returning `<Navigate>` JSX directly.

---

## 11. How to test this after pulling

### Setup
```bash
cd backend
alembic upgrade head
python3 seed.py          # creates admin + 2 officers + 8 sample drafts
uvicorn app:app --reload --port 8000

# in a second terminal
cd frontend
npm install
npm run dev               # http://localhost:3000
```

### Accounts (from `backend/seed.py` — change before any non-local use)

| Role | login_id | password | Notes |
|---|---|---|---|
| Approving Authority (admin) | `admin` | `NirnAdmin#2026` | `must_change_password=False` |
| Drafting Officer | `priya.sharma` | `Officer#Pass01` | `must_change_password=True` — will be prompted to set a new password on first login |
| Drafting Officer | `rahul.deshmukh` | `Officer#Pass02` | same as above |
| Reviewing Officer | *(none seeded)* | — | Create one via Admin → Officers → New Officer → role "Reviewing Officer" before testing the middle tier |

### 8-step manual checklist

1. Log in as a Drafting Officer, open a `draft`-status draft → click **Submit for Review** → status badge changes to **Submitted**.
2. Log in as the Reviewing Officer → **Approval** tab → Review Queue → open the draft, edit the text, **Forward with my edits** → confirm dialog → draft leaves the queue.
3. Repeat with a different draft using **Forward without changes** → same result, no edits.
4. Log in as `admin` → **Approval** tab → Approval Queue → open a forwarded draft → confirm `DraftDiffView` shows highlighted insertions/deletions (or "No changes made at this stage" for the unedited one), and hash badges' **Verify** button reports a match.
5. Click **Accept reviewer's version** → confirm the "this is FINAL" modal → status becomes **Approved**; draft leaves the queue.
6. On another `reviewed` draft, click **Keep original, discard edits** → confirm → content reverts to what the Drafting Officer originally submitted (reviewer's edit is discarded but still recorded in the audit trail).
7. On a `submitted` or `reviewed` draft, click **Return for rework** with a reason ≥20 characters → log back in as the original Drafting Officer and confirm the amber returned-reason banner appears on their Draft/History page.
8. Confirm: the navbar reads **Check Conflicts** (not "Upload GR"); a Drafting Officer does **not** see the Approval nav item and is redirected home (not a blank page) if they visit `/approval` directly; a `PATCH` on an approved draft returns `409`, not a 500 or a silent success.

### API-level spot checks (curl / Postman, if you don't want to click through the UI)

```bash
# should return 200 with an "explanation" field, not a raw diff
curl -s http://localhost:8000/api/drafts/1/diff?from_version=1&to_version=2 -H "Authorization: Bearer <token>"

# should return 409 once the draft is approved
curl -s -X PATCH http://localhost:8000/api/drafts/<id> -H "Authorization: Bearer <token>" -d '{"content":"x"}'
```
