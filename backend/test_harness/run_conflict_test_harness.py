"""
run_conflict_test_harness.py — automates the cross-departmental conflict
test cycle end-to-end: submit a brief via the real HTTP API, wait for
generation + conflict detection to finish, then pull the ground-truth
records directly from Postgres (never from a rendered PDF, and never
assumed) to classify each conflict against known issue patterns and
verify resolve-attempt persistence.

Usage:
    # backend must be running (uvicorn app:app) and reachable at API_BASE_URL
    cd backend
    python -m test_harness.run_conflict_test_harness

    # or with a custom brief set (JSON list of {"brief": ..., "department": ...}):
    python -m test_harness.run_conflict_test_harness --briefs my_briefs.json

Every run writes one Markdown + one JSON findings file per brief under
test_runs/, plus a single cross-run summary Markdown, so consecutive runs
are diffable without re-parsing anything.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make backend/ importable regardless of the caller's cwd, so this can be
# invoked as `python test_harness/run_conflict_test_harness.py` from
# backend/ or as `python backend/test_harness/run_conflict_test_harness.py`
# from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from db.base import async_session_factory  # noqa: E402
from db.models import DraftConflict, GeneratedDraft  # noqa: E402
from conflict_detection import _is_boilerplate_clause  # noqa: E402
import template_rules  # noqa: E402

API_BASE_URL = os.environ.get("NIRN_API_BASE_URL", "http://localhost:8000")
ADMIN_LOGIN = os.environ.get("NIRN_TEST_LOGIN", "admin")
ADMIN_PASSWORD = os.environ.get("NIRN_TEST_PASSWORD", "NirnAdmin#2026")
DEFAULT_DEPARTMENT = "General_Administration_Department"
DEFAULT_LANGUAGE = "Marathi"

REPO_ROOT = _BACKEND_DIR.parent
OUTPUT_DIR = REPO_ROOT / "test_runs"

# Persistence-regression check: how long to wait before re-querying the DB
# a second time after a resolve/accept — long enough to catch the "reverts
# after reload" class of bug, short enough to keep the run fast.
PERSISTENCE_RECHECK_DELAY_SECONDS = 5

RESOLVE_STRATEGIES = ["reword", "add_carve_out"]

# Heuristic markers of a justification asserting a distinction (different
# beneficiary/scope/purpose, no overlap) — used to flag a verdict that
# contradicts its own reasoning. This is a heuristic over free text, not a
# structured field (see the "known gaps" note emitted in each report).
_SELF_CONTRADICTION_MARKERS = [
    r"different beneficiar", r"different scope", r"different purpose",
    r"no beneficiary overlap", r"no scope overlap", r"does not (?:mention|address|cover|target)",
    r"focuses solely on", r"unrelated to", r"no overlap",
    r"targets? a different", r"narrower (?:case|scope)",
]
_SELF_CONTRADICTION_RE = re.compile("|".join(_SELF_CONTRADICTION_MARKERS), re.IGNORECASE)

_HIGH_SEVERITIES = {"critical", "high"}


def _norm_dept(value: Optional[str]) -> str:
    return (value or "").replace("_", " ").strip().lower()


@dataclass
class ConflictFinding:
    conflict_id: Optional[str]
    matched_gr_id: Optional[str]
    matched_department: Optional[str]
    relation: Optional[str]  # from the live API response; NOT a persisted DB column — see gaps
    severity: Optional[str]
    justification: str
    draft_excerpt: str
    conflicting_text: str
    flags: dict = field(default_factory=dict)
    resolve_attempted: bool = False
    resolve_result: dict = field(default_factory=dict)
    persistence_check: dict = field(default_factory=dict)


@dataclass
class BriefFinding:
    brief: str
    department: str
    draft_id: Optional[str] = None
    draft_department_stored: Optional[str] = None
    draft_content_gaps: list = field(default_factory=list)
    placeholder_artifacts: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)  # list[ConflictFinding]
    errors: list = field(default_factory=list)
    known_gaps: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class Harness:
    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(base_url=api_base_url, timeout=180.0)
        self.token: Optional[str] = None

    async def login(self):
        resp = await self.client.post(
            "/api/auth/login",
            json={"login_id": ADMIN_LOGIN, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    async def generate_draft(self, brief: str, department: str) -> dict:
        resp = await self.client.post(
            "/api/copilot/draft",
            json={"prompt": brief, "language": DEFAULT_LANGUAGE, "department": department},
        )
        resp.raise_for_status()
        return resp.json()

    async def run_conflict_analysis(self, draft_id: str) -> list:
        resp = await self.client.post(f"/api/analysis/{draft_id}/conflicts")
        resp.raise_for_status()
        return resp.json()

    async def resolve_conflict(self, conflict_id: str, strategy: str) -> dict:
        resp = await self.client.post(
            f"/api/conflicts/{conflict_id}/resolve", json={"strategy": strategy}
        )
        resp.raise_for_status()
        return resp.json()

    async def accept_resolution(self, conflict_id: str, revised_clause: str) -> dict:
        resp = await self.client.post(
            f"/api/conflicts/{conflict_id}/resolve/accept",
            json={"revised_clause": revised_clause},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


async def fetch_draft_row(draft_id: str) -> Optional[GeneratedDraft]:
    async with async_session_factory() as session:
        return (
            await session.execute(
                select(GeneratedDraft).where(GeneratedDraft.generated_draft_id == draft_id)
            )
        ).scalar_one_or_none()


async def fetch_conflict_rows(draft_id: str) -> list:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(DraftConflict)
                .where(DraftConflict.generated_draft_id == draft_id)
                .order_by(DraftConflict.created_at)
            )
        ).scalars().all()
        # Detach the attributes we need while the session is still open.
        return [
            {
                "conflict_id": str(r.conflict_id),
                "conflict_ref": r.conflict_ref,
                "source_of_conflict": r.source_of_conflict,
                "conflicting_text": r.conflicting_text,
                "draft_excerpt": r.draft_excerpt,
                "conflicting_gr_id": r.conflicting_gr_id,
                "source_gr_title": r.source_gr_title,
                "severity": r.severity.value if hasattr(r.severity, "value") else r.severity,
                "justification": r.justification,
                "is_resolved": r.is_resolved,
                "resolution_status": r.resolution_status,
                "resolved_clause_text": r.resolved_clause_text,
                "is_dismissed": r.is_dismissed,
            }
            for r in rows
        ]


async def fetch_single_conflict_status(conflict_id: str) -> Optional[dict]:
    async with async_session_factory() as session:
        row = (
            await session.execute(
                select(DraftConflict).where(DraftConflict.conflict_id == conflict_id)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "resolution_status": row.resolution_status,
            "is_resolved": row.is_resolved,
            "resolved_clause_text": row.resolved_clause_text,
        }


def classify_conflict(draft_department: str, db_row: dict, live_relation: Optional[str]) -> dict:
    flags = {}

    # 1. cross-department vs same-department
    flags["cross_department"] = _norm_dept(draft_department) != _norm_dept(db_row["source_of_conflict"])

    # 2. self-contradicting verdict: justification asserts a distinction but
    #    the verdict is still a high-severity conflict. `live_relation` comes
    #    from the API response at analysis time — the DB has no persisted
    #    "relation" column (see known_gaps in the brief-level report).
    justification = db_row["justification"] or ""
    asserts_distinction = bool(_SELF_CONTRADICTION_RE.search(justification))
    severity_high = (db_row["severity"] or "").lower() in _HIGH_SEVERITIES
    relation_is_conflict = (live_relation or "conflict").lower() == "conflict"
    flags["self_contradicting"] = asserts_distinction and severity_high and relation_is_conflict

    # 3. boilerplate-only overlap: both the draft clause and the matched
    #    clause are dominated by generic procedural language. Uses the same
    #    classifier the live pipeline now uses to filter these out
    #    pre-retrieval — a conflict reaching this point that still trips
    #    the classifier on both sides indicates the filter has a gap.
    draft_is_boilerplate = _is_boilerplate_clause(db_row["draft_excerpt"] or "")
    matched_is_boilerplate = _is_boilerplate_clause(db_row["conflicting_text"] or "")
    flags["boilerplate_only"] = draft_is_boilerplate and matched_is_boilerplate

    return flags


async def process_conflict(harness: Harness, db_row: dict, live_relation: Optional[str],
                            draft_department: str) -> ConflictFinding:
    finding = ConflictFinding(
        conflict_id=db_row["conflict_id"],
        matched_gr_id=db_row["conflicting_gr_id"],
        matched_department=db_row["source_of_conflict"],
        relation=live_relation,
        severity=db_row["severity"],
        justification=db_row["justification"] or "",
        draft_excerpt=db_row["draft_excerpt"] or "",
        conflicting_text=db_row["conflicting_text"] or "",
        flags=classify_conflict(draft_department, db_row, live_relation),
    )

    if db_row["resolution_status"] == "resolved":
        finding.resolve_result = {"skipped": "already resolved at analysis time"}
        return finding

    finding.resolve_attempted = True
    cleared = False
    last_error = None
    revised_clause = None
    try:
        for strategy in RESOLVE_STRATEGIES:
            result = await harness.resolve_conflict(db_row["conflict_id"], strategy)
            if result.get("cleared"):
                revised_clause = result["revised_clause"]
                await harness.accept_resolution(db_row["conflict_id"], revised_clause)
                cleared = True
                break
        finding.resolve_result = {"cleared": cleared, "strategy_used": strategy if cleared else None}
    except Exception as exc:  # noqa: BLE001 — record and continue, don't abort the run
        last_error = str(exc)
        finding.resolve_result = {"cleared": False, "error": last_error}

    # Persistence-regression check: fetch immediately, then again after a
    # delay, directly from the DB (never the in-memory API response) —
    # this is exactly the check that would have caught the earlier
    # "resolved state reverts after reload" bug.
    immediate = await fetch_single_conflict_status(db_row["conflict_id"])
    await asyncio.sleep(PERSISTENCE_RECHECK_DELAY_SECONDS)
    after_wait = await fetch_single_conflict_status(db_row["conflict_id"])

    persisted_immediately = bool(immediate and immediate["resolution_status"] == "resolved")
    persisted_after_wait = bool(after_wait and after_wait["resolution_status"] == "resolved")
    finding.persistence_check = {
        "immediate": immediate,
        "after_wait": after_wait,
        "persisted_immediately": persisted_immediately,
        "persisted_after_wait": persisted_after_wait,
        "regression_detected": persisted_immediately != persisted_after_wait,
    }
    return finding


async def run_one_brief(harness: Harness, brief: str, department: str) -> BriefFinding:
    bf = BriefFinding(brief=brief, department=department)

    try:
        draft_resp = await harness.generate_draft(brief, department)
    except Exception as exc:  # noqa: BLE001
        bf.errors.append(f"draft generation failed: {exc}")
        return bf

    draft_id = draft_resp["draft_id"]
    bf.draft_id = draft_id

    try:
        live_conflicts = await harness.run_conflict_analysis(draft_id)
    except Exception as exc:  # noqa: BLE001
        bf.errors.append(f"conflict analysis failed: {exc}")
        live_conflicts = []

    live_by_id = {c["conflict_id"]: c for c in live_conflicts if c.get("conflict_id")}

    # Ground truth: pull draft + conflicts from Postgres directly, not from
    # the in-memory API response above.
    draft_row = await fetch_draft_row(draft_id)
    if draft_row is None:
        bf.errors.append(f"draft {draft_id} not found in database after generation")
        return bf
    bf.draft_department_stored = draft_row.department
    bf.placeholder_artifacts = template_rules.find_placeholder_leaks(draft_row.content)

    db_conflicts = await fetch_conflict_rows(draft_id)
    for db_row in db_conflicts:
        live_relation = live_by_id.get(db_row["conflict_id"], {}).get("relation")
        finding = await process_conflict(harness, db_row, live_relation, draft_row.department)
        bf.conflicts.append(finding)

    bf.known_gaps = [
        "DraftConflict has no persisted 'relation' (conflict/overlap) column — "
        "the relation used for self_contradicting classification comes from the "
        "live /api/analysis/{draft_id}/conflicts response captured during this "
        "run, not from a durable DB field. A conflict inspected on a later run "
        "without re-running analysis would not have this field available.",
        "DraftConflict has no persisted structured beneficiary_match/scope_match "
        "fields (those exist only transiently in ConflictReportItem during "
        "LLM verification) — self_contradicting detection here is a regex "
        "heuristic over the free-text justification, not a structured check.",
        "DraftConflict has no persisted 'category'/conflict_type column — "
        "conflict_type shown in the UI is only available from the live "
        "analysis response, not reconstructable from the DB alone for a "
        "conflict from a past run.",
    ]

    total = len(bf.conflicts)
    cross = sum(1 for c in bf.conflicts if c.flags.get("cross_department"))
    same = total - cross
    self_contra = sum(1 for c in bf.conflicts if c.flags.get("self_contradicting"))
    boilerplate = sum(1 for c in bf.conflicts if c.flags.get("boilerplate_only"))
    resolved_attempted = sum(1 for c in bf.conflicts if c.resolve_attempted)
    resolved_success_persisted = sum(
        1 for c in bf.conflicts
        if c.resolve_attempted and c.persistence_check.get("persisted_after_wait")
    )
    persistence_regressions = sum(
        1 for c in bf.conflicts
        if c.resolve_attempted and c.persistence_check.get("regression_detected")
    )
    bf.summary = {
        "total_conflicts": total,
        "cross_department": cross,
        "same_department": same,
        "likely_false_positive_self_contradicting": self_contra,
        "likely_false_positive_boilerplate": boilerplate,
        "resolve_attempts": resolved_attempted,
        "resolve_succeeded_and_persisted": resolved_success_persisted,
        "persistence_regressions_detected": persistence_regressions,
        "placeholder_artifacts_found": len(bf.placeholder_artifacts) > 0,
    }
    return bf


def _conflict_to_md(c: ConflictFinding) -> str:
    flag_str = ", ".join(k for k, v in c.flags.items() if v) or "none"
    lines = [
        f"#### Conflict `{c.conflict_id}` vs GR `{c.matched_gr_id}` ({c.matched_department})",
        f"- relation: `{c.relation}` (live API only, not persisted) | severity: `{c.severity}`",
        f"- flags triggered: **{flag_str}**",
        f"- justification: {c.justification[:400]}{'…' if len(c.justification) > 400 else ''}",
    ]
    if c.resolve_attempted:
        lines.append(f"- resolve result: {json.dumps(c.resolve_result, ensure_ascii=False)}")
        pc = c.persistence_check
        regressed = pc.get("regression_detected")
        lines.append(
            f"- persistence check: immediate={pc.get('persisted_immediately')} "
            f"after {PERSISTENCE_RECHECK_DELAY_SECONDS}s={pc.get('persisted_after_wait')} "
            f"{'⚠️ REGRESSION DETECTED' if regressed else '✓ stable'}"
        )
    else:
        skip_reason = c.resolve_result.get("skipped", "not attempted")
        lines.append(f"- resolve: {skip_reason}")
    return "\n".join(lines)


def brief_finding_to_md(bf: BriefFinding, index: int) -> str:
    lines = [
        f"## Brief {index}",
        f"**Department (requested):** `{bf.department}`  ",
        f"**Department (as stored on draft):** `{bf.draft_department_stored}`  ",
        f"**Draft ID:** `{bf.draft_id}`",
        "",
        "**Brief text:**",
        f"> {bf.brief}",
        "",
    ]
    if bf.errors:
        lines.append("### Errors")
        lines.extend(f"- {e}" for e in bf.errors)
        lines.append("")

    if bf.placeholder_artifacts:
        lines.append(f"### ⚠️ Placeholder/formatting artifacts found: {bf.placeholder_artifacts}")
    else:
        lines.append("### Placeholder/formatting artifacts: none found")
    lines.append("")

    lines.append("### Summary")
    for k, v in bf.summary.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("### Conflicts")
    if not bf.conflicts:
        lines.append("_No conflicts detected._")
    else:
        for c in bf.conflicts:
            lines.append(_conflict_to_md(c))
            lines.append("")

    lines.append("### Known gaps in this classification")
    for g in bf.known_gaps:
        lines.append(f"- {g}")
    lines.append("")
    return "\n".join(lines)


def cross_run_summary_md(briefs: list, timestamp: str) -> str:
    lines = [f"# Cross-brief summary — {timestamp}", ""]
    totals = {
        "total_conflicts": 0, "cross_department": 0, "same_department": 0,
        "likely_false_positive_self_contradicting": 0, "likely_false_positive_boilerplate": 0,
        "resolve_attempts": 0, "resolve_succeeded_and_persisted": 0,
        "persistence_regressions_detected": 0,
    }
    briefs_with_placeholder_bug = []
    briefs_with_self_contradiction = []
    briefs_with_boilerplate = []
    briefs_with_persistence_regression = []

    for i, bf in enumerate(briefs, 1):
        for k in totals:
            totals[k] += bf.summary.get(k, 0)
        if bf.summary.get("placeholder_artifacts_found"):
            briefs_with_placeholder_bug.append(i)
        if bf.summary.get("likely_false_positive_self_contradicting"):
            briefs_with_self_contradiction.append(i)
        if bf.summary.get("likely_false_positive_boilerplate"):
            briefs_with_boilerplate.append(i)
        if bf.summary.get("persistence_regressions_detected"):
            briefs_with_persistence_regression.append(i)

    lines.append("## Totals across all briefs")
    for k, v in totals.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Recurring vs. isolated bug patterns")
    n = len(briefs)
    def _pattern_line(name, hit_briefs):
        recurring = len(hit_briefs) > 1
        tag = "🔴 RECURRING — higher priority" if recurring else ("🟡 isolated" if hit_briefs else "✓ not observed")
        return f"- **{name}**: briefs {hit_briefs or 'none'} ({len(hit_briefs)}/{n}) — {tag}"

    lines.append(_pattern_line("Formatting/placeholder artifacts in draft text", briefs_with_placeholder_bug))
    lines.append(_pattern_line("Self-contradicting high-severity verdicts", briefs_with_self_contradiction))
    lines.append(_pattern_line("Boilerplate-only overlap reaching a conflict record", briefs_with_boilerplate))
    lines.append(_pattern_line("Resolve-persistence regression", briefs_with_persistence_regression))
    lines.append("")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--briefs", type=str, default=None,
                         help="Path to a JSON file: list of {brief, department?}")
    args = parser.parse_args()

    if args.briefs:
        briefs_input = json.loads(Path(args.briefs).read_text(encoding="utf-8"))
    else:
        briefs_input = [{"brief": b} for b in DEFAULT_BRIEFS]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    harness = Harness()
    await harness.login()

    results: list = []
    try:
        for item in briefs_input:
            brief = item["brief"]
            department = item.get("department") or DEFAULT_DEPARTMENT
            print(f"--- Running brief (department={department}): {brief[:60]}...")
            bf = await run_one_brief(harness, brief, department)
            results.append(bf)

            slug = (bf.draft_id or "no-draft")[:8]
            json_path = OUTPUT_DIR / f"{timestamp}_{slug}.json"
            md_path = OUTPUT_DIR / f"{timestamp}_{slug}.md"
            json_path.write_text(
                json.dumps(asdict(bf), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            md_path.write_text(
                brief_finding_to_md(bf, len(results)), encoding="utf-8"
            )
            print(f"    -> {md_path}")
    finally:
        await harness.close()

    summary_path = OUTPUT_DIR / f"{timestamp}_SUMMARY.md"
    summary_path.write_text(cross_run_summary_md(results, timestamp), encoding="utf-8")
    print(f"\nCross-run summary -> {summary_path}")


DEFAULT_BRIEFS = [
    "राज्यातील सौर ऊर्जेचा वापर वाढवण्यासाठी एक व्यापक आर्थिक सहाय्य योजना जाहीर करावी. या "
    "योजनेअंतर्गत (अ) महानगरपालिका क्षेत्रात वीज देयकात बचत करण्यासाठी सौर ऊर्जा प्रकल्प "
    "उभारण्यास आर्थिक सहाय्य द्यावे, (ब) ग्रामपंचायतींना सौर ऊर्जा आधारित पथदिव्यांच्या "
    "स्थापनेसाठी अनुदान द्यावे, आणि (क) विकेंद्रित कृषी वीज वाहिनीवर आधारित सौर ऊर्जा प्रकल्प "
    "उभारणाऱ्या ग्रामपंचायतींना प्रोत्साहनात्मक आर्थिक मदत द्यावी. या तिन्ही घटकांसाठी पात्रता "
    "निकष, निधी वितरणाची कार्यपद्धती आणि अंमलबजावणीचा कालमर्यादा नमूद करावा.",

    "ग्रामीण भागातील पाणीपुरवठा योजनांसाठी जलस्रोत बळकटीकरण आणि पाणलोट क्षेत्र विकासासाठी "
    "आर्थिक सहाय्य योजना जाहीर करावी. या योजनेअंतर्गत (अ) ग्रामपंचायतींना पाणीपुरवठा "
    "योजनांच्या देखभालीसाठी अनुदान द्यावे, (ब) वनक्षेत्रालगतच्या गावांमध्ये जलसंधारण "
    "कामांसाठी वनविभागाच्या सहकार्याने निधी उपलब्ध करावा, आणि (क) पाणलोट क्षेत्र विकास "
    "कार्यक्रमांतर्गत जमीन सुधारण्यासाठी शेतकऱ्यांना सहाय्य द्यावे. पात्रता निकष व निधी "
    "वितरण कार्यपद्धती नमूद करावी.",

    "आदिवासी बहुल भागातील आरोग्य सुविधा बळकट करण्यासाठी सर्वसमावेशक योजना जाहीर करावी. या "
    "योजनेअंतर्गत (अ) आदिवासी उपयोजनांतर्गत प्राथमिक आरोग्य केंद्रांचे बांधकाम व श्रेणीवाढ "
    "करावी, (ब) सार्वजनिक आरोग्य विभागामार्फत या केंद्रांना वैद्यकीय कर्मचारी व साधनसामग्री "
    "पुरवावी, आणि (क) आदिवासी संशोधन व प्रशिक्षण संस्थेमार्फत स्थानिक आरोग्य कर्मचाऱ्यांना "
    "प्रशिक्षण द्यावे. पात्रता निकष, निधी वितरण आणि अंमलबजावणी कालमर्यादा नमूद करावा.",
]


if __name__ == "__main__":
    asyncio.run(main())
