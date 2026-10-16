import unittest
from football_analysis.coverage_audit import audit_coverage

class CoverageAuditTests(unittest.TestCase):
    def test_groups_and_field_coverage(self):
        rows = [
            {"league":"L1","season":"2025","fixture_id":"1","status":"FT","home_goals":0,"away_goals":1,"corners":0,"xg":None},
            {"league":"L1","season":"2025","fixture_id":"2","status":"NS","home_goals":None,"away_goals":None,"corners":None,"xg":1.2},
            {"league":"L2","season":"2025","fixture_id":"3","status":"FT","home_goals":2,"away_goals":0},
        ]
        report = audit_coverage(rows)
        self.assertEqual(report["group_count"], 2)
        first = report["groups"][0]
        self.assertEqual(first["league"], "L1")
        self.assertEqual(first["fixtures_unique"], 2)
        self.assertEqual(first["finished_fixtures"], 1)
        self.assertEqual(first["fields"]["home_goals"]["available"], 1)
        self.assertEqual(first["fields"]["corners"]["coverage_pct"], 50.0)
        self.assertEqual(first["fields"]["xg"]["available"], 1)

    def test_zero_is_present_and_duplicates_are_excluded(self):
        rows = [
            {"league":"L","season":"S","fixture_id":"7","home_goals":0},
            {"league":"L","season":"S","fixture_id":"7","home_goals":3},
            {"league":"L","season":"S","fixture_id":"8","home_goals":""},
        ]
        group = audit_coverage(rows)["groups"][0]
        self.assertEqual(group["fixtures_unique"], 2)
        self.assertEqual(group["duplicate_rows"], 1)
        self.assertEqual(group["fields"]["home_goals"]["available"], 1)

    def test_required_identity_fields(self):
        with self.assertRaises(ValueError):
            audit_coverage([{"league":"L","season":"S"}])

    def test_empty_input(self):
        self.assertEqual(audit_coverage([]), {"groups": [], "group_count": 0})

if __name__ == "__main__":
    unittest.main()
