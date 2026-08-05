"""
seed.py — idempotent demo data for local development.

SQL RULE: every query below is select()/insert() through the ORM or the
repository layer. Never an f-string, never string concatenation. See
backend/README.md, "SQL injection prevention".

Creates:
  - one admin officer (must_change_password=False)
  - two regular officers in different departments
  - 8 sample drafts spread across officers/departments/languages/statuses
  - a realistic spread of conflicts (none / one / several, mixed
    severity, at least one dismissed)
  - extracted references on several drafts

Every insert is guarded by an existence check, so re-running this
script is always safe — it will never throw a UNIQUE violation and
will never pile up duplicate demo rows.

Run manually, AFTER migrations are applied:
    cd backend && python3 seed.py

This is never run by the assistant — see backend/README.md /
docs/BACKEND_REINDEX_MIGRATION.md for the full setup sequence.
"""

import asyncio

from sqlalchemy import select

from db.base import async_session_factory
from db.models import GeneratedDraft, OfficerRole
from db.repositories import conflicts as conflicts_repo
from db.repositories import drafts as drafts_repo
from db.repositories import officers as officers_repo

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "NirnAdmin#2026"
OFFICER1_LOGIN = "priya.sharma"
OFFICER1_PASSWORD = "Officer#Pass01"
OFFICER2_LOGIN = "rahul.deshmukh"
OFFICER2_PASSWORD = "Officer#Pass02"

HTE_DEPT = "Higher_and_Technical_Education_Department"
PH_DEPT = "Public_Health_Department"
GAD_DEPT = "General_Administration_Department"


async def _ensure_officer(session, **kwargs):
    existing = await officers_repo.get_by_login_id(session, kwargs["login_id"])
    if existing is not None:
        return existing, False
    officer = await officers_repo.create_officer(session, **kwargs)
    return officer, True


async def _find_existing_draft(session, *, title: str, drafted_by) -> bool:
    stmt = select(GeneratedDraft.generated_draft_id).where(
        GeneratedDraft.title == title, GeneratedDraft.drafted_by == drafted_by
    )
    return (await session.execute(stmt)).first() is not None


async def main() -> None:
    async with async_session_factory() as session:
        admin, admin_created = await _ensure_officer(
            session,
            name="System Administrator",
            login_id=ADMIN_LOGIN,
            password=ADMIN_PASSWORD,
            department=GAD_DEPT,
            designation="Deputy Secretary",
            role=OfficerRole.ADMIN,
            must_change_password=False,
        )
        officer1, o1_created = await _ensure_officer(
            session,
            name="Priya Sharma",
            login_id=OFFICER1_LOGIN,
            password=OFFICER1_PASSWORD,
            department=HTE_DEPT,
            designation="Section Officer",
            role=OfficerRole.OFFICER,
            must_change_password=True,
        )
        officer2, o2_created = await _ensure_officer(
            session,
            name="Rahul Deshmukh",
            login_id=OFFICER2_LOGIN,
            password=OFFICER2_PASSWORD,
            department=PH_DEPT,
            designation="Desk Officer",
            role=OfficerRole.OFFICER,
            must_change_password=True,
        )
        await session.commit()

        draft_specs = [
            dict(
                officer=officer1, department=HTE_DEPT, language="en", status_after="draft",
                title="Revision of Lateral Entry Intake for Diploma Holders",
                content="<h1>Revision of Lateral Entry Intake</h1><p>The intake of lateral entry students into degree engineering programmes is revised for the academic year 2026-27.</p>",
                conflicts=[], references=[
                    dict(reference_text="GR No TEM-2021/CR-45/TE-1", extracted_gr_number="TEM-2021/CR-45/TE-1", script="latin", resolved=True),
                ],
            ),
            dict(
                officer=officer1, department=HTE_DEPT, language="mr", status_after="under_review",
                title="राज्य विद्यापीठ संशोधन अनुदान सुधारणा",
                content="<h1>राज्य विद्यापीठ संशोधन अनुदान</h1><p>राज्यातील विद्यापीठांतील संशोधन प्रयोगशाळांसाठी अनुदान वाटप सुधारित करण्यात येत आहे.</p>",
                conflicts=[
                    dict(source_of_conflict="Finance Department", conflicting_text="Research grants above ₹10 lakh require Finance Department pre-approval.",
                         draft_excerpt="संशोधन अनुदान थेट वितरित करण्यात येईल.", severity="medium", justification="Draft bypasses the Finance Department pre-approval threshold set in the cited GR.",
                         conflicting_gr_id="MH-FIN-2020-0091", source_gr_title="Financial Delegation of Powers (Research Grants)"),
                ],
                references=[
                    dict(reference_text="शासन निर्णय क्रमांक: संकीर्ण-2019/प्र.क्र.252/तां.शि.-4", extracted_gr_number="संकीर्ण-2019/प्र.क्र.252/तां.शि.-4", script="devanagari", resolved=False),
                ],
            ),
            dict(
                officer=officer1, department=HTE_DEPT, language="en", status_after="finalised",
                title="Faculty Recruitment Rules — Government Engineering Colleges",
                content="<h1>Faculty Recruitment Rules</h1><p>Revised eligibility criteria for Assistant Professor recruitment in government engineering colleges.</p>",
                conflicts=[
                    dict(source_of_conflict="Higher and Technical Education Department", conflicting_text="Minimum qualification: Master's degree with 55% marks.",
                         draft_excerpt="Minimum qualification: Master's degree with 50% marks.", severity="low", justification="Minor deviation from the qualification threshold in the earlier GR on the same subject.",
                         conflicting_gr_id="MH-HTE-2018-0234", source_gr_title="Faculty Recruitment Rules 2018"),
                    dict(source_of_conflict="General Administration Department", conflicting_text="Reservation roster must follow the 2019 model roster point system.",
                         draft_excerpt="Reservation as per the existing roster.", severity="high", justification="Draft does not reference the mandatory 2019 model roster point system, risking a reservation-policy violation.",
                         conflicting_gr_id="MH-GAD-2019-0012", source_gr_title="Model Roster Point System for Reservation"),
                ],
                references=[],
            ),
            dict(
                officer=officer2, department=PH_DEPT, language="en", status_after="draft",
                title="District Hospital Staffing Norms Update",
                content="<h1>District Hospital Staffing Norms</h1><p>Revised nurse-to-bed ratio for district hospitals across the state.</p>",
                conflicts=[], references=[],
            ),
            dict(
                officer=officer2, department=PH_DEPT, language="mr", status_after="under_review",
                title="प्राथमिक आरोग्य केंद्र औषध पुरवठा धोरण",
                content="<h1>औषध पुरवठा धोरण</h1><p>प्राथमिक आरोग्य केंद्रांना आवश्यक औषधांचा नियमित पुरवठा सुनिश्चित करण्यासाठी सुधारित धोरण.</p>",
                conflicts=[
                    dict(source_of_conflict="Finance Department", conflicting_text="Procurement above ₹5 lakh requires e-tender.",
                         draft_excerpt="स्थानिक खरेदीस परवानगी.", severity="low", justification="Local-purchase allowance may fall under the e-tender threshold depending on the amount.",
                         conflicting_gr_id="MH-FIN-2017-0056", source_gr_title="e-Tendering Threshold Rules"),
                    dict(source_of_conflict="Public Health Department", conflicting_text="Cold-chain storage mandatory for vaccine consignments.",
                         draft_excerpt="साठवण अटींचा उल्लेख नाही.", severity="medium", justification="Draft omits the cold-chain storage condition mandated for vaccine-adjacent consignments."),
                    dict(source_of_conflict="Public Health Department", conflicting_text="District-level drug committee approval required before local purchase.",
                         draft_excerpt="स्थानिक स्तरावर थेट खरेदी करता येईल.", severity="high", justification="Draft permits direct local purchase, bypassing the mandatory district drug committee approval.",
                         conflicting_gr_id="MH-PHD-2015-0077", source_gr_title="District Drug Committee Procurement Rules"),
                ],
                references=[
                    dict(reference_text="GR No PHD-2015/CR-77/M-9", extracted_gr_number="PHD-2015/CR-77/M-9", script="latin", resolved=True),
                ],
                dismiss_one=True,
            ),
            dict(
                officer=officer2, department=PH_DEPT, language="en", status_after="archived",
                title="Ambulance Service Response Time Standards (Superseded Draft)",
                content="<h1>Ambulance Service Response Time</h1><p>Target response time of 20 minutes for urban areas, 35 minutes for rural areas.</p>",
                conflicts=[
                    dict(source_of_conflict="Public Health Department", conflicting_text="Target response time of 15 minutes for urban areas.",
                         draft_excerpt="Target response time of 20 minutes for urban areas.", severity="medium", justification="Relaxes the urban response-time target set by the earlier GR.",
                         conflicting_gr_id="MH-PHD-2022-0143", source_gr_title="Ambulance Service Response Time Standards 2022"),
                ],
                references=[],
                dismiss_one=True,
                dismiss_reason="Superseded by a later policy revision; conflict no longer applicable.",
            ),
            dict(
                officer=admin, department=GAD_DEPT, language="en", status_after="finalised",
                title="Standard Operating Procedure for File Movement (e-Office)",
                content="<h1>SOP for File Movement</h1><p>All departments shall route physical files through the e-Office platform with effect from the next quarter.</p>",
                conflicts=[
                    dict(source_of_conflict="Information Technology Department", conflicting_text="e-Office rollout mandatory only for Group A offices in phase 1.",
                         draft_excerpt="All departments shall route physical files through e-Office immediately.", severity="high", justification="Draft applies the mandate to all offices immediately, ahead of the phased rollout schedule already notified.",
                         conflicting_gr_id="MH-IT-2024-0019", source_gr_title="e-Office Phased Rollout Schedule"),
                ],
                references=[
                    dict(reference_text="GR No GAD-2023/CR-08/Desk-1", extracted_gr_number="GAD-2023/CR-08/Desk-1", script="latin", resolved=True),
                    dict(reference_text="GR No IT-2024/CR-19/e-Off", extracted_gr_number="IT-2024/CR-19/e-Off", script="latin", resolved=True),
                ],
            ),
            dict(
                officer=officer1, department=HTE_DEPT, language="mr", status_after="draft",
                title="तांत्रिक शिक्षण शिष्यवृत्ती योजना सुधारणा",
                content="<h1>शिष्यवृत्ती योजना</h1><p>आर्थिकदृष्ट्या दुर्बल घटकातील विद्यार्थ्यांसाठी तांत्रिक शिक्षण शिष्यवृत्ती रकमेत वाढ करण्यात येत आहे.</p>",
                conflicts=[], references=[
                    dict(reference_text="शासन निर्णय क्रमांक: शिष्यवृत्ती-2020/प्र.क्र.10/तां.शि.-2", extracted_gr_number="शिष्यवृत्ती-2020/प्र.क्र.10/तां.शि.-2", script="devanagari", resolved=True),
                ],
            ),
        ]

        created_count = 0
        for spec in draft_specs:
            officer = spec["officer"]
            if await _find_existing_draft(session, title=spec["title"], drafted_by=officer.officer_id):
                continue

            draft = await drafts_repo.create_draft_with_analysis(
                session,
                title=spec["title"],
                language=spec["language"],
                drafted_by=officer.officer_id,
                content=spec["content"],
                content_plain=spec["content"].replace("<h1>", "").replace("</h1>", " ").replace("<p>", "").replace("</p>", " "),
                department=spec["department"],
                brief=None,
                conflicts=spec["conflicts"],
                references=spec["references"],
            )
            await session.flush()

            if spec.get("dismiss_one"):
                rows = await conflicts_repo.get_conflicts_for_draft(session, draft.generated_draft_id)
                if rows:
                    await conflicts_repo.dismiss_conflict(
                        session, rows[-1].conflict_id,
                        reason=spec.get("dismiss_reason", "Reviewed and found not applicable to the final scope."),
                    )

            if spec["status_after"] != "draft":
                draft.status = spec["status_after"]

            created_count += 1

        await session.commit()

    print("\n=== NIRN.Ai seed data ===")
    print(f"Admin officer   {'(created)' if admin_created else '(already existed)'}: login_id={ADMIN_LOGIN}  password={ADMIN_PASSWORD}")
    print(f"Officer 1       {'(created)' if o1_created else '(already existed)'}: login_id={OFFICER1_LOGIN}  password={OFFICER1_PASSWORD}  dept={HTE_DEPT}")
    print(f"Officer 2       {'(created)' if o2_created else '(already existed)'}: login_id={OFFICER2_LOGIN}  password={OFFICER2_PASSWORD}  dept={PH_DEPT}")
    print(f"Drafts newly created this run: {created_count} / {len(draft_specs)}")
    print("These credentials are also documented in backend/README.md — change them before any non-local use.")


if __name__ == "__main__":
    asyncio.run(main())
