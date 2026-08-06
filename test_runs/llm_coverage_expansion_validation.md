# LLM coverage expansion — validation
Draft ID: `aae7a564-6feb-48bc-b82d-39a0a7081655` (same nutrition/health draft
used in the retrieval-observability validation)

## Grounding (before changes)

- `MAX_CLAUSES_FOR_LLM` (`config.py`) and `CANDIDATES_PER_CLAUSE` (`config.py`)
  are both consumed in exactly one place: `detect_cross_department_conflicts()`
  in `conflict_detection/__init__.py` —
  - `llm_eligible_indices`: top `MAX_CLAUSES_FOR_LLM` clauses by
    `_priority_score()`, computed once per draft before the clause loop.
  - `llm_eligible_keys`: top `CANDIDATES_PER_CLAUSE` of each clause's
    retrieved pool (`candidates[:settings.CANDIDATES_PER_CLAUSE]`), computed
    once per clause inside the loop.
  - A candidate only reaches the LLM if both gates pass AND the deterministic
    rule engine didn't already resolve it.
- **No `asyncio.gather()` or any parallelization exists anywhere in this
  codebase** — grepped `conflict_detection/`, `llm.py`, and the whole
  `backend/` tree for `asyncio.gather`, `ThreadPoolExecutor`, `run_in_executor`:
  zero hits. `detect_cross_department_conflicts()` is a plain synchronous
  function; every LLM call in the clause loop runs strictly sequentially. The
  "Phase 1 parallelization work" referenced in the task brief does not exist
  in the current code — there is no concurrent-load interaction to worry
  about, because there is no concurrency. Total latency is purely additive:
  one call's wall time, back to back, per verified candidate.
- Real clause-count distribution (most recent 20 drafts, via
  `_extract_operative_clauses` against the live `generated_drafts` table):
  **max 5, average 3.35** — not the "up to 10" figure referenced in the task
  brief. Ceiling was set to 12, comfortably above the observed max with room
  to spare, rather than matching an unverified historical figure.

## Changes made
- `config.py`: `MAX_CLAUSES_FOR_LLM` 2 → 12 (re-scoped from a coverage budget
  to a safety ceiling — see updated comment in the file), `CANDIDATES_PER_CLAUSE`
  2 → 3. `RULE_ENGINE_CANDIDATES_PER_CLAUSE` (6) untouched, no score-threshold
  logic added or removed, no downgrade-rule/verdict-schema changes.
- `conflict_detection/__init__.py`: added a `logger.warning(...)` that fires
  only if a draft's clause count ever actually exceeds `MAX_CLAUSES_FOR_LLM`
  (did not fire for this 4-clause draft, as expected).

## Validation results

### Coverage (retrieval trace, `GET /api/drafts/{id}/retrieval-trace`)

| Clause | Content | Before: `llm_eligible_clause` | Before: `reached_llm` | After: `llm_eligible_clause` | After: `reached_llm` |
|---|---|---|---|---|---|
| 0 | Background paragraph | true | 2 | **true** | **3** |
| 1 | (b) Public Health — health checkups | **false** | **0** | **true** | **3** |
| 2 | (a) School Education — nutrition funding | true | 2 | **true** | **3** |
| 3 | (c) Rural Dev/Water Supply — drinking water | **false** | **0** | **true** | **3** |

All 4 clauses are now `llm_eligible_clause: true` with `reached_llm: 3`
(their full `CANDIDATES_PER_CLAUSE` budget) — confirmed via a genuinely cold
run (fresh backend process, empty response cache) hitting the live API and
reading the trace back from Postgres afterward, not inferred from code.

### Did real conflicts emerge in the previously-unchecked clauses?

**Yes.** Clause 3 (Rural Development/Water Supply, previously 0 candidates
reaching the LLM) now surfaces:
```
GR 202101131520371228 (Water_Supply_and_Sanitation_Department) — relation: conflict, severity: Critical
GR 202101131520371228 (Water_Supply_and_Sanitation_Department) — relation: conflict, severity: Critical
```
at 0.953-0.954 similarity — the highest-scoring candidates in the entire
draft. **These were completely invisible under the old cap** — clause 3 never
reached the LLM at all before this change, regardless of candidate score.

Clause 1 (Public Health) did not surface a Public-Health-Department conflict
in this particular run — its top-3-by-score candidates this run were
School Education / Medical Education, not Public Health (which the earlier
observability run found at 0.893, likely rank 4-6 of the 6 retrieved and
thus outside `CANDIDATES_PER_CLAUSE=3`). Clause 1 itself is fully
LLM-eligible now and did produce conflicts — just against a different
department than Public Health specifically. **Caveat, in scope for a future
task, not this one**: `CANDIDATES_PER_CLAUSE=3` still caps candidates *within*
a clause — a clause with more than 3 relevant departments in its retrieved
pool can still have one silently excluded. This is the same class of gap as
the one just fixed, one level down (candidate-level instead of clause-level),
and was explicitly out of scope here (`RULE_ENGINE_CANDIDATES_PER_CLAUSE`
unchanged per instructions).

Full "before" (old config, same draft, cold cache) for comparison: **0
conflicts** — this exact draft was a live reproduction of the "0 conflicts,
ambiguous why" problem the observability task set out to diagnose, and the
trace now shows it was clause-budget exclusion, not genuine clean clauses.

### Latency (cold — fresh backend process, empty LLM response cache, measured client-side via `httpx` around the full `POST /api/analysis/{id}/conflicts` call)

| Config | MAX_CLAUSES_FOR_LLM | CANDIDATES_PER_CLAUSE | Clauses LLM-checked | LLM calls (approx) | Wall time |
|---|---|---|---|---|---|
| Before | 2 | 2 | 2 of 4 | ~4 | **66.0s** |
| After | 12 (ceiling) | 3 | 4 of 4 | ~11-12 | **120.7s – 125.4s** (two cold runs) |

**Latency roughly doubled (66s → ~121-125s) and now exceeds the project's
10-20s conflict-detection target** (already substantially exceeded even
before this change, per the existing "23.8s-28.7s" figure documented in
`config.py`'s own comments for the *original* 2/2 config — the 66s "before"
figure measured here is for a 4-clause draft specifically, worse than that
baseline's assumed 2-clause case). This is being reported as-is per
instructions, not silently reverted: **going from 2 to 4 LLM-checked clauses,
and from 2 to 3 candidates per clause, found 5 real conflicts (including 2
Critical ones in a department that was previously never examined) that a
faster-but-blind pipeline would have missed entirely.**

Confirmed no parallelization exists to absorb this — every one of the
~11-12 LLM calls in the "after" case runs strictly sequentially, so latency
scales linearly with LLM-call count. Per-call latency itself
(~7-11s/call, consistent with the ~6-10s figure already documented in
`config.py`) did not change — only call volume did.

## Recommendation
This tradeoff should be a deliberate product decision, not an implementation
detail: either (a) accept the new ~2x latency as the cost of not silently
missing cross-departmental conflicts, (b) reintroduce parallelization
(genuinely absent today, contrary to what the task brief assumed) to claw
back latency without sacrificing coverage, or (c) find a middle ground
(e.g. a per-clause candidate cap lower than the rule-engine's wider pool,
combined with the now-uncapped clause coverage). Not decided as part of this
task — flagging per instructions rather than choosing unilaterally.
