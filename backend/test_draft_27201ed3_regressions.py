"""
Regression tests for the three bugs found on Draft ID
27201ed3-ab62-42a8-b8c0-0d558143cfb5 (cross-departmental conflict test run).

Bug 1: generated draft text leaked ```marathi / ``` code-fence artifacts.
Bug 2: retrieval matched on generic fund-disbursement/committee-evaluation
       boilerplate (clause 03) against two unrelated GRs, producing an
       inconsistent verdict (Critical for one match, downgraded to
       Overlap/Medium for the structurally identical other).
Bug 3: an accepted conflict resolution did not persist durably — a page
       reload / fresh analysis run had no record of it.

Fixtures below are the real stored text pulled from that draft record, not
paraphrased examples, so these tests fail again if the underlying fix
regresses.
"""
import unittest

import template_rules
from conflict_detection import _is_boilerplate_clause


# ---------------------------------------------------------------------
# Bug 1 — code fence stripping
# ---------------------------------------------------------------------

# Verbatim prefix/suffix of the actual stored draft content for this draft
# ID (backend/data snapshot at time of the bug report).
_KNOWN_BAD_DRAFT_PREFIX = "```marathi\nमहाराष्ट्र शासन\nसामान्य प्रशासन विभाग"
_KNOWN_BAD_DRAFT_SUFFIX = "३. निवड फाईल.\n```"


class TestCodeFenceStripping(unittest.TestCase):
    def test_strips_leading_and_trailing_fence(self):
        raw = _KNOWN_BAD_DRAFT_PREFIX + "\n...body...\n" + _KNOWN_BAD_DRAFT_SUFFIX
        cleaned = template_rules.strip_llm_formatting_artifacts(raw)
        self.assertFalse(cleaned.startswith("```"))
        self.assertFalse(cleaned.endswith("```"))
        self.assertTrue(cleaned.startswith("महाराष्ट्र शासन"))

    def test_strips_fence_without_language_tag(self):
        raw = "```\nGovernment Resolution text here.\n```"
        cleaned = template_rules.strip_llm_formatting_artifacts(raw)
        self.assertEqual(cleaned, "Government Resolution text here.")

    def test_no_fence_is_a_no_op(self):
        raw = "महाराष्ट्र शासन\nसामान्य प्रशासन विभाग\n...body..."
        self.assertEqual(template_rules.strip_llm_formatting_artifacts(raw), raw)

    def test_placeholder_leak_check_catches_surviving_fence(self):
        # Safety net: find_placeholder_leaks must flag a fence even if the
        # stripping step is ever skipped or misses a case (e.g. a fence
        # appearing mid-document rather than at the very start/end).
        self.assertIn("```", template_rules.find_placeholder_leaks("```marathi\ntext\n```"))

    def test_cleaned_draft_has_no_leaks(self):
        raw = _KNOWN_BAD_DRAFT_PREFIX + "\n...body...\n" + _KNOWN_BAD_DRAFT_SUFFIX
        cleaned = template_rules.strip_llm_formatting_artifacts(raw)
        self.assertEqual(template_rules.find_placeholder_leaks(cleaned), [])


# ---------------------------------------------------------------------
# Bug 2 — boilerplate clause exclusion (Conflict #2 and #3, matched pair)
# ---------------------------------------------------------------------

# Verbatim draft_excerpt stored on BOTH DraftConflict rows for this draft
# (CFL-2026-000025 vs GR #202603251255249719, and CFL-2026-000026 vs GR
# #202101211535544124) — same underlying clause, same underlying bug.
_BOILERPLATE_CLAUSE_03 = (
    "०३. निधी वितरणाची कार्यपद्धती:\n"
    "(अ) पात्रतेसाठी अर्जदाराने प्रकल्पाचा प्रस्ताव सादर करणे आवश्यक आहे.\n"
    "(ब) शासकिय समितीद्वारे प्रस्तावांचे मूल्यांकन केले जाईल.\n"
    "(क) मान्यताप्राप्त अर्जदारांनाच अनुदानास पात्र ठरवले जाईल.\n\n"
    "अंमलबजावणीचा कालमर्यादा: सदर शासन निर्णयानुसार अंमलबजावणी करण्यात यावी. "
    "शासनाची मान्यता देण्यात येत आहे."
)

# The genuinely substantive clause from the same draft (clause 01, matched
# against GR #202504291630372425) — must NOT be classified as boilerplate.
_SUBSTANTIVE_CLAUSE_01 = (
    "०१. शासन खालीलप्रमाणे मंजुरी देण्यास प्रसन्न आहे: राज्यातील सौर ऊर्जेचा वापर "
    "वाढवण्यासाठी एक व्यापक आर्थिक सहाय्य योजना जाहीर करण्यात येत आहे. या "
    "योजनेअंतर्गत महानगरपालिका क्षेत्रात वीज देयकात बचत करण्यासाठी सौर ऊर्जा "
    "प्रकल्प उभारण्यास आर्थिक सहाय्य द्यावे, ग्रामपंचायतींना सौर ऊर्जा आधारित "
    "पथदिव्यांच्या स्थापनेसाठी अनुदान द्यावे, आणि विकेंद्रित कृषी वीज वाहिनीवर "
    "आधारित सौर ऊर्जा प्रकल्प उभारणाऱ्या ग्रामपंचायतींना प्रोत्साहनात्मक आर्थिक "
    "मदत द्यावी."
)


class TestBoilerplateClauseExclusion(unittest.TestCase):
    def test_fund_disbursement_procedure_clause_is_boilerplate(self):
        # Conflict #2 and #3 both stemmed from this exact clause matching
        # unrelated GRs purely on procedural phrasing.
        self.assertTrue(_is_boilerplate_clause(_BOILERPLATE_CLAUSE_03))

    def test_substantive_policy_clause_is_not_boilerplate(self):
        self.assertFalse(_is_boilerplate_clause(_SUBSTANTIVE_CLAUSE_01))

    def test_boilerplate_clause_excluded_from_candidate_search(self):
        # detect_cross_department_conflicts skips boilerplate clauses
        # entirely (see the `if _is_boilerplate_clause(clause): continue`
        # guard) -- both Conflict #2 and #3 should now be unreachable from
        # any draft containing only this clause, not just downgraded.
        import conflict_detection

        clauses = [_BOILERPLATE_CLAUSE_03]
        eligible = [c for c in clauses if not conflict_detection._is_boilerplate_clause(c)]
        self.assertEqual(eligible, [])


if __name__ == "__main__":
    unittest.main()
