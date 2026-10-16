import unittest
from datetime import datetime, timezone, timedelta

from football_analysis.strengths import HistoricalMatch, expected_goals, fit_team_strengths


def match(i, home, away, hg, ag):
    return HistoricalMatch(
        str(i), datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
        home, away, hg, ag,
    )


class TeamStrengthTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            match(1, "A", "B", 3, 0),
            match(2, "B", "C", 0, 2),
            match(3, "C", "A", 1, 1),
            match(4, "A", "C", 2, 0),
            match(5, "B", "A", 1, 2),
            match(6, "C", "B", 0, 1),
        ]

    def test_strengths_are_positive_and_expected_goals_are_bounded(self):
        model = fit_team_strengths(self.rows)
        home_xg, away_xg = expected_goals(model, "A", "B")
        self.assertGreater(home_xg, 0)
        self.assertGreater(away_xg, 0)
        self.assertLessEqual(home_xg, 8)
        self.assertLessEqual(away_xg, 8)
        self.assertTrue(all(team.attack > 0 and team.defence > 0 for team in model.teams.values()))

    def test_attack_responds_to_results_with_shrinkage(self):
        model = fit_team_strengths(self.rows, prior_matches=5)
        self.assertGreater(model.teams["a"].attack, model.teams["b"].attack)

    def test_rejects_duplicate_ids_and_empty_sample(self):
        with self.assertRaises(ValueError):
            fit_team_strengths([])
        with self.assertRaises(ValueError):
            fit_team_strengths([self.rows[0], self.rows[0]])

    def test_rejects_unknown_or_same_team(self):
        model = fit_team_strengths(self.rows)
        with self.assertRaises(ValueError):
            expected_goals(model, "A", "Unknown")
        with self.assertRaises(ValueError):
            expected_goals(model, "A", "a")

    def test_requires_timezone_aware_kickoff(self):
        with self.assertRaises(ValueError):
            HistoricalMatch("x", datetime(2026, 1, 1), "A", "B", 1, 0)

    def test_verified_finish_must_be_aware_and_not_precede_kickoff(self):
        kickoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            HistoricalMatch("naive-finish", kickoff, "A", "B", 1, 0, finished_at=datetime(2026, 1, 1, 2))
        with self.assertRaises(ValueError):
            HistoricalMatch("early-finish", kickoff, "A", "B", 1, 0, finished_at=kickoff - timedelta(minutes=1))


if __name__ == "__main__":
    unittest.main()
