import unittest
from datetime import datetime, timedelta, timezone

from football_analysis.baseline_comparison import compare_baselines
from football_analysis.models import MatchResult, OddsSnapshot, Outcome, Prediction

UTC = timezone.utc
KICKOFF = datetime(2026, 9, 1, 18, tzinfo=UTC)


class BaselineComparisonTests(unittest.TestCase):
    def setUp(self):
        self.predictions = [
            Prediction("m1", KICKOFF - timedelta(hours=2), {Outcome.HOME: .7, Outcome.DRAW: .2, Outcome.AWAY: .1}),
            Prediction("m2", KICKOFF - timedelta(hours=2), {Outcome.HOME: .2, Outcome.DRAW: .6, Outcome.AWAY: .2}),
        ]
        self.results = [MatchResult("m1", KICKOFF, 2, 0), MatchResult("m2", KICKOFF, 1, 1)]
        self.odds = [
            OddsSnapshot("m1", KICKOFF - timedelta(hours=3), {Outcome.HOME: 2.0, Outcome.DRAW: 3.2, Outcome.AWAY: 4.0}),
            OddsSnapshot("m2", KICKOFF - timedelta(hours=3), {Outcome.HOME: 2.8, Outcome.DRAW: 3.0, Outcome.AWAY: 2.8}),
        ]

    def test_compares_all_three_baselines(self):
        report = compare_baselines(self.predictions, self.results, self.odds)
        self.assertEqual(report.sample_size, 2)
        self.assertEqual(report.market_sample_size, 2)
        self.assertIsNotNone(report.model_brier)
        self.assertIsNotNone(report.uniform_log_loss)
        self.assertIsNotNone(report.market_brier)

    def test_future_odds_are_excluded(self):
        future = OddsSnapshot("m1", KICKOFF - timedelta(minutes=1), self.odds[0].decimal_odds)
        report = compare_baselines(self.predictions[:1], self.results[:1], [future])
        self.assertEqual(report.market_sample_size, 0)
        self.assertIsNone(report.market_brier)

    def test_empty_sample_returns_none_metrics(self):
        report = compare_baselines([], [])
        self.assertEqual(report.sample_size, 0)
        self.assertIsNone(report.model_brier)
        self.assertIsNone(report.market_log_loss)


if __name__ == "__main__":
    unittest.main()
