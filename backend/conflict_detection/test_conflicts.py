import unittest
from conflict_detection.rule_engine import check_deterministic_conflicts

class TestConflictDetection(unittest.TestCase):
    
    def test_funding_conflict_deterministic(self):
        draft = "This scheme shall prohibit CSR funding entirely from private entities."
        matched = "The project cost can be partially met since CSR funding is permitted."
        conflict = check_deterministic_conflicts(
            draft_clause=draft,
            matched_gr_id="GR-2024-001",
            matched_gr_title="CSR funding rules",
            matched_clause=matched
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.category, "Funding Conflict")
        self.assertEqual(conflict.severity, "Critical")
        self.assertTrue(conflict.conflict)

    def test_authority_conflict_deterministic(self):
        draft = "The District Collector shall approve all procurement tenders."
        matched = "Ministry approval is mandatory for all procurement tenders; no Collector approval is allowed."
        conflict = check_deterministic_conflicts(
            draft_clause=draft,
            matched_gr_id="GR-2024-002",
            matched_gr_title="Procurement approvals",
            matched_clause=matched
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.category, "Authority Conflict")
        self.assertEqual(conflict.severity, "High")

    def test_timeline_conflict_deterministic(self):
        draft = "The implementation must complete within 30 days."
        matched = "Tendering agency shall complete the implementation within 90 days."
        conflict = check_deterministic_conflicts(
            draft_clause=draft,
            matched_gr_id="GR-2024-003",
            matched_gr_title="Tendering timelines",
            matched_clause=matched
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.category, "Timeline Conflict")
        self.assertEqual(conflict.severity, "Medium")

    def test_no_conflict_when_unrelated(self):
        draft = "The officer shall wear standard formal dress code."
        matched = "The grant amount of 10 lakhs is sanctioned for library expansion."
        conflict = check_deterministic_conflicts(
            draft_clause=draft,
            matched_gr_id="GR-2024-004",
            matched_gr_title="Library grants",
            matched_clause=matched
        )
        self.assertIsNone(conflict)

if __name__ == "__main__":
    unittest.main()
