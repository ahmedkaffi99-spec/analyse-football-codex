import unittest
from football_analysis.competitions import filter_priority_fixtures, is_priority_fixture

class CompetitionScopeTests(unittest.TestCase):
    def row(self, league_id, home, away):
        return {"league":{"id":league_id},"teams":{"home":{"name":home},"away":{"name":away}}}

    def test_keeps_top_five_leagues_and_champions_league(self):
        for league_id in (39, 140, 78, 135, 61, 2):
            self.assertTrue(is_priority_fixture(self.row(league_id, "Small Club", "Another Club")))

    def test_keeps_major_club_even_outside_priority_leagues(self):
        self.assertTrue(is_priority_fixture(self.row(999, "Real Madrid", "Local Club")))
        self.assertTrue(is_priority_fixture(self.row(999, "Paris Saint-Germain", "Local Club")))

    def test_excludes_unrelated_small_league_match(self):
        self.assertFalse(is_priority_fixture(self.row(999, "Local Club A", "Local Club B")))

    def test_filter_preserves_only_priority_rows(self):
        rows = [self.row(39, "A", "B"), self.row(999, "Real Madrid", "C"), self.row(999, "A", "B")]
        self.assertEqual(len(filter_priority_fixtures(rows)), 2)

if __name__ == "__main__": unittest.main()
