# Retrieval observability — validation run
Draft ID: `aae7a564-6feb-48bc-b82d-39a0a7081655`
Brief: nutrition/health scheme citing Tribal Development + School Education
in वाचा, with operative clauses touching Public Health and Rural
Development/Water Supply without citing them.

## Grounding findings (before any code changes)

- **Retrieval is per-clause**, not pooled/global: `detect_cross_department_conflicts()`
  calls `retrieval.search(clause, ...)` once inside the `for clause_index, clause in
  enumerate(clauses)` loop — a fresh FAISS search per clause, not one shared
  candidate set for the whole draft.
- **Actual top_k in use: 6**, not the "4 retrieved candidates" figure from prior
  audit docs. It's `settings.RULE_ENGINE_CANDIDATES_PER_CLAUSE = 6`
  (`backend/config.py:103`) — the pool the deterministic rule engine sees per
  clause. Of that pool, only the top `settings.CANDIDATES_PER_CLAUSE = 2`
  (already score-sorted) are ever eligible for the LLM stage.
- **A separate, more consequential budget exists at the *clause* level**:
  `settings.MAX_CLAUSES_FOR_LLM = 2` (`backend/config.py:91`). Regardless of
  how many operative clauses a draft has, only the top-2 (by
  `_priority_score()` — funding/authority/timeline/committee/legal-reference
  keyword presence, ties broken by document order) ever get LLM verification.
  The other clauses only get the free, local, deterministic rule-engine pass —
  **their retrieved candidates, however relevant, never reach the LLM at all.**
  This was not previously logged or exposed anywhere.
- No pre-LLM min-score threshold exists in the candidate-filtering logic itself
  — filtering to the LLM stage is by **rank within the fixed budgets above**,
  not by a similarity-score cutoff. (`CONFLICT_CONFIDENCE_FLOOR = 0.45` is a
  *post*-LLM filter on the final conflict list, unrelated to which candidates
  get examined.)

## What was built (this task)
- `conflict_detection/models.py`: `RetrievalCandidateTrace` (gr_id, department,
  score, source `top_k`/`jurisdiction`, `reached_llm`, `rule_engine_result`)
  and `ClauseRetrievalTrace` (clause_index, preview, boilerplate_skipped,
  llm_eligible_clause, top_k, candidates_per_clause_budget, candidates_returned,
  candidates).
- `detect_cross_department_conflicts()` gained an opt-in `trace: Optional[list]`
  param — appends one `ClauseRetrievalTrace` per extracted clause (including
  boilerplate-skipped and budget-excluded ones). Return type/value and behavior
  are unchanged for both existing callers that don't pass it.
- `generated_drafts.retrieval_trace` (JSONB, migration `e40fcc005348`) — the
  most recent run's trace, persisted by `run_conflict_detection`.
- `GET /api/drafts/{draft_id}/retrieval-trace` — reads it back without
  re-running detection.
- **No retrieval, filtering, or scoring behavior was changed.**

## Validation results

4 operative clauses were extracted from this draft. Per-clause retrieval detail:

| Clause | Content | `llm_eligible_clause` | Candidates retrieved | Departments seen | Reached LLM |
|---|---|---|---|---|---|
| 0 | Background paragraph (restates all 3 sub-schemes) | **true** | 6/6 (top_k=6) | Tribal Development, School Education, Water Supply & Sanitation | 2 (both Tribal Development) |
| 1 | **(b) — health checkups via Public Health Dept medical teams** | **false** | 6/6 | Public Health (score 0.893), School Education, Medical Education & Drugs | **0** |
| 2 | **(a) — nutrition funding via School Education** | **true** | 6/6 | Tribal Development (all 6) | 2 (both Tribal Development) |
| 3 | **(c) — drinking water via Rural Dev/Water Supply coordination** | **false** | 6/6 | Tribal Development, **Water Supply & Sanitation (score 0.930)** | **0** |

Final result: **2 conflicts**, both against Tribal Development Department
(one `conflict`/Critical, one `overlap`/Medium — both from clauses 0/2).

### Direct answer to the validation questions

- **Clause (b), Public Health**: a Public Health Department candidate **was
  retrieved** at 0.893 similarity — high enough to be a plausible real match —
  but this clause fell outside the `MAX_CLAUSES_FOR_LLM=2` budget (lower
  `_priority_score()` than clauses 0/2, which contain more
  funding/authority-keyword hits). Only the deterministic rule engine
  evaluated it, and found no conflict. **This "no conflict" is NOT
  "candidates checked and cleared by the LLM" — it's "checked by keyword
  rules only, LLM never saw it."** Whether the LLM would agree is genuinely
  unknown from this run.
- **Clause (c), Rural Development/Water Supply**: same pattern. A Water
  Supply & Sanitation Department candidate was retrieved at 0.930 similarity
  — the highest score of any candidate in the entire draft — and never
  reached the LLM for the same budget reason.
- **Clauses (a)/background** (Tribal Development, School Education): these
  did get full LLM verification, which is exactly why both actual conflicts
  found trace back to Tribal Development.

**Bottom line: this draft's "0 conflicts on Public Health / Rural
Development" (in the version of this draft that previously showed 0 total)
was never a resolved "checked and cleared" result — retrieval worked
correctly and found relevant, high-scoring candidates in both departments,
but the clause-level `MAX_CLAUSES_FOR_LLM` budget silently prevented the LLM
from ever evaluating them.** This is precisely the ambiguity the task set
out to eliminate, and it's now visible per-clause via
`GET /api/drafts/{draft_id}/retrieval-trace` instead of being indistinguishable
from a genuine clean bill of health.

## Follow-up recommendation (not implemented — flagging only, per instructions)
`MAX_CLAUSES_FOR_LLM=2` is a *draft-wide* cap, not a *per-clause* one — on a
4-clause draft (typical for a multi-department scheme like this one), half
the clauses never get LLM scrutiny regardless of retrieval quality. Given
this project's explicit design intent is catching **cross-departmental**
conflicts, and departments are exactly what's split across clauses in briefs
like this one, this budget is the more likely source of missed conflicts
than retrieval's `top_k=6`. Worth reassessing budget allocation (e.g.
guaranteeing at least one LLM slot per distinct department mentioned,
similar to the existing jurisdiction-keyword guarantee for retrieval) as a
separate, deliberate task — not a top_k tuning question.
