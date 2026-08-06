# Consolidated findings — cross-departmental conflict test cycle
Run timestamps: `20260806T001153Z` (briefs 1–3), `20260806T001832Z` (brief 2 retry)

## Per-brief outcome

| Brief | Draft ID | Conflicts | Resolve attempts | Persisted | 409 on accept |
|---|---|---|---|---|---|
| 1 (Solar/GAD) | `f019df03…` | 2 | 2 | 1 | 1 |
| 2 (Water/Rural Dev) | — | draft generation **failed** (502) both attempts | — | — | — |
| 3 (Tribal Health) | `9cfb1492…` | 4 | 4 | 2 | 2 |

## Recurring vs. isolated patterns

### 🔴 RECURRING — accept-time 409 when two conflicts share the same/overlapping draft clause (2/2 successful briefs)
In both briefs that got far enough to run resolve, **every pair of conflicts anchored to the same draft clause** hit this: the first resolve+accept succeeds and patches the draft's content; the second conflict's `resolve` still generates a revision fine, but `resolve/accept` 409s with "the flagged clause no longer matches the current draft content" — because the first accept already replaced that shared text.

- Brief 1: clause 01 (municipal solar funding) was flagged against **two** different GRs (Urban Development, Industries/Energy/Labour). First accept succeeded; second 409'd.
- Brief 3: clause "नियंत्रण अधिकारी व विभाग प्रमुख..." was flagged against **two** different existing clauses of the *same* GR (`201803282056360624`). Same failure pattern.

This is a real gap in the single-clause resolve design: `accept_conflict_resolution` matches purely on literal substring presence of `conflict.draft_excerpt` in the draft's current content, with no awareness that another conflict row might reference the same span. **Priority: high** — it silently caps "how many of this draft's conflicts can actually be auto-resolved" at one per shared clause, and surfaces to the user as a bare 409 with no guidance to re-run analysis.

### 🔴 RECURRING — cross-department conflicts dominate (2/2 successful briefs, 6/6 conflicts)
All 6 detected conflicts across briefs 1 and 3 were cross-department (0 same-department). Expected given the test briefs were deliberately cross-departmental by design — not itself a bug, but confirms the harness's department-comparison classification is working and gives a baseline for future same-department regression checks.

### 🟡 ISOLATED (so far) — draft generation rejected for an unfilled officer-name placeholder (brief 2, reproduced 2/2 attempts on that brief specifically)
Brief 2 failed both times with the backend's own placeholder-leak guard correctly catching `[अधिकाऱ्याचे नाव]` (officer name) still unfilled after the automatic retry, returning `502` rather than shipping a broken draft — the guard is doing its job, but the underlying generation prompt has no fallback instruction for the officer-name field the way it does for department name and citation fields (`prompts.py`'s HALLUCINATION POLICY only covers department/reference placeholders, not the signature block's officer name). Only reproduced on brief 2's content so far (2/2 on that brief, 0/2 on briefs 1 and 3) — worth a wider test set before ranking this above the 409 issue, but it's a hard failure (blocks the whole brief) rather than a quality issue.

### ✓ Not observed in this run
- **Formatting/placeholder artifacts surviving into a returned draft**: 0/2 successful briefs — consistent with the earlier code-fence-stripping fix holding.
- **Self-contradicting high-severity verdicts** (justification asserts no beneficiary/scope overlap but relation stays `conflict`/severity `critical`-`high`): 0/6 conflicts. All of brief 3's auto-downgraded conflicts correctly show `relation: overlap` with lowered severity, not a contradiction.
- **Boilerplate-only overlap reaching a persisted conflict record**: 0/6 conflicts — consistent with the boilerplate-clause pre-filter fix holding across both successful briefs.
- **Resolve-persistence regression** (resolved-immediately ≠ resolved-after-5s): 0/6 conflicts — every resolution that succeeded stayed `resolved` on the delayed re-fetch, and every 409 stayed unresolved on the delayed re-fetch too. No sign of the earlier "reverts after reload" bug recurring.

## Known gaps in the classification itself (apply to every run)
- `DraftConflict` has no persisted `relation` (conflict/overlap) column — self-contradiction detection relies on the live `/api/analysis/{draft_id}/conflicts` response captured during the run, not a durable DB field. A conflict inspected from a past run without re-running analysis wouldn't have this available.
- No persisted structured `beneficiary_match`/`scope_match` fields — self-contradiction detection is a regex heuristic over free-text justification, not a structured check.
- No persisted `category`/`conflict_type` column on `DraftConflict`.

## Priority recommendation
1. **Fix the shared-clause 409 first** — it's 100% reproducible whenever two conflicts anchor to overlapping text, which is common (a clause naming multiple departments/GRs), and it currently fails silently from the caller's perspective.
2. **Investigate the officer-name placeholder gap** — extend the HALLUCINATION POLICY prompt section to cover the signature block the same way it covers department/reference fields, then re-run brief 2 (and a wider set) to confirm.
3. Continue monitoring the three "not observed" categories on a wider brief set before concluding they're fully fixed — 2 successful briefs / 6 conflicts is a small sample.

## Raw per-brief reports
- `20260806T001153Z_f019df03.md` / `.json` — Brief 1
- `20260806T001153Z_no-draft.md` / `.json` — Brief 2, first attempt (502)
- `20260806T001832Z_no-draft.md` / `.json` — Brief 2, retry (502, same root cause)
- `20260806T001153Z_9cfb1492.md` / `.json` — Brief 3
