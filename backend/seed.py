"""
seed.py — demo data so the app has something to show right after a
fresh `alembic upgrade head`.

Run from inside backend/:

    python3 seed.py

Idempotent: re-running it skips officers/drafts that already exist
(matched by login_id / title) instead of duplicating them.
"""

import asyncio

from db.base import async_session_factory, engine
from db.models import DraftConflict, GeneratedDraft, Officer
from db.security import hash_password
from sqlalchemy import select

DEMO_OFFICERS = [
    dict(
        name="Priya Deshmukh",
        login_id="priya.deshmukh",
        password="ChangeMe123!",
        department="Higher and Technical Education Department",
        designation="Section Officer",
        role="officer",
    ),
    dict(
        name="Anil Kulkarni",
        login_id="anil.kulkarni",
        password="ChangeMe123!",
        department="General Administration Department",
        designation="Deputy Secretary",
        role="reviewer",
    ),
]

DEMO_DRAFTS = [
    dict(
        title="Revision of lateral entry intake for engineering diploma holders",
        language="en",
        department="Higher and Technical Education Department",
        brief="Increase lateral entry quota for diploma holders into degree engineering courses.",
        gr_number="HTE-2026/CR-118/TE-4",
        content=(
            "<p>Government of Maharashtra, Higher and Technical Education Department, "
            "hereby resolves to revise the lateral entry intake quota for diploma holders "
            "seeking admission to the second year of degree engineering courses from 10% "
            "to 15% of the sanctioned intake, effective from the academic year 2026-27.</p>"
        ),
        conflicts=[
            dict(
                source_of_conflict="AICTE Intake Norms GR",
                conflicting_text="Lateral entry intake shall not exceed 10% of sanctioned intake in any engineering discipline.",
                draft_excerpt="revise the lateral entry intake quota ... from 10% to 15%",
                conflicting_gr_id="HTE-2019/CR-45/TE-1",
                severity="high",
                justification="The draft's 15% cap directly exceeds the 10% ceiling fixed by the existing AICTE-aligned GR and would require that GR to be explicitly superseded.",
                detected_by="rule_engine",
            ),
        ],
    ),
    dict(
        title="Marathi Language Advisory Committee — Terms of Reference",
        language="mr",
        department="General Administration Department",
        brief="Constitute an advisory committee to review Marathi terminology usage across department GRs.",
        gr_number="GAD-2026/CR-27/भाषा-2",
        content=(
            "<p>महाराष्ट्र शासन, सामान्य प्रशासन विभाग, शासकीय शासन निर्णयांमधील मराठी "
            "भाषेच्या सुसंगत वापरासाठी सल्लागार समितीची स्थापना करण्यास मान्यता देत आहे.</p>"
        ),
        conflicts=[],
    ),
    dict(
        title="Enhancement of scholarship disbursal ceiling for post-matric students",
        language="en",
        department="Social Justice and Special Assistance Department",
        brief="Raise the annual scholarship disbursal ceiling for post-matric SC/ST students.",
        gr_number="SJSA-2026/CR-91/EDN-3",
        content=(
            "<p>The Social Justice and Special Assistance Department hereby enhances the "
            "annual post-matric scholarship disbursal ceiling to Rs. 55,000 per eligible "
            "student, chargeable to the department's plan allocation for FY 2026-27, "
            "superseding all prior ceilings fixed for this scheme.</p>"
        ),
        conflicts=[
            dict(
                source_of_conflict="Finance Department Plan Allocation GR",
                conflicting_text="Scholarship disbursal under this scheme is capped at Rs. 40,000 per student per annum, chargeable to the consolidated welfare fund.",
                draft_excerpt="enhances the annual post-matric scholarship disbursal ceiling to Rs. 55,000",
                conflicting_gr_id="FIN-2024/CR-12/WF-9",
                severity="medium",
                justification="The new ceiling changes the funding source and amount fixed in the Finance Department's allocation GR; a corresponding budget re-appropriation is needed before issue.",
                detected_by="llm_verifier",
            ),
            dict(
                source_of_conflict="Social Justice Dept eligibility circular",
                conflicting_text="Post-matric scholarship eligibility income limit is Rs. 2,50,000 per annum.",
                draft_excerpt=None,
                conflicting_gr_id="SJSA-2022/CR-6/EDN-1",
                severity="low",
                justification="The draft does not restate the income eligibility limit; recommend cross-referencing the 2022 circular to avoid ambiguity.",
                detected_by="rule_engine",
            ),
        ],
    ),
]


async def seed() -> None:
    async with async_session_factory() as session:
        officer_ids: dict[str, "Officer"] = {}

        for spec in DEMO_OFFICERS:
            existing = (
                await session.execute(select(Officer).where(Officer.login_id == spec["login_id"]))
            ).scalar_one_or_none()
            if existing:
                officer_ids[spec["login_id"]] = existing
                print(f"officer already present: {spec['login_id']}")
                continue

            officer = Officer(
                name=spec["name"],
                login_id=spec["login_id"],
                password_hash=hash_password(spec["password"]),
                department=spec["department"],
                designation=spec["designation"],
                role=spec["role"],
            )
            session.add(officer)
            await session.flush()
            officer_ids[spec["login_id"]] = officer
            print(f"created officer: {spec['login_id']} (password: {spec['password']})")

        drafted_by_cycle = [DEMO_OFFICERS[0]["login_id"], DEMO_OFFICERS[1]["login_id"], DEMO_OFFICERS[0]["login_id"]]

        for i, spec in enumerate(DEMO_DRAFTS):
            existing = (
                await session.execute(select(GeneratedDraft).where(GeneratedDraft.title == spec["title"]))
            ).scalar_one_or_none()
            if existing:
                print(f"draft already present: {spec['title'][:50]}...")
                continue

            drafted_by = officer_ids[drafted_by_cycle[i]]
            draft = GeneratedDraft(
                title=spec["title"],
                language=spec["language"],
                drafted_by=drafted_by.officer_id,
                content=spec["content"],
                content_plain=spec["content"].replace("<p>", "").replace("</p>", ""),
                department=spec["department"],
                brief=spec["brief"],
                gr_number=spec["gr_number"],
            )
            session.add(draft)
            await session.flush()

            for c in spec["conflicts"]:
                session.add(DraftConflict(generated_draft_id=draft.generated_draft_id, **c))

            print(f"created draft: {spec['title'][:50]}... ({len(spec['conflicts'])} conflicts)")

        await session.commit()

    counts = {}
    async with async_session_factory() as session:
        for label, model in (("officers", Officer), ("generated_drafts", GeneratedDraft), ("draft_conflicts", DraftConflict)):
            from sqlalchemy import func
            total = (await session.execute(select(func.count()).select_from(model))).scalar_one()
            counts[label] = total

    print("\nRow counts:")
    for label, total in counts.items():
        print(f"  {label}: {total}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
