import unittest
from datetime import datetime, timedelta, timezone
from football_analysis.backtest import evaluate_predictions
from football_analysis.models import MatchResult, OddsSnapshot, Outcome, Prediction
UTC = timezone.utc
KICKOFF = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)

class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.prediction = Prediction("m1", KICKOFF - timedelta(hours=2), {Outcome.HOME: 0.7, Outcome.DRAW: 0.2, Outcome.AWAY: 0.1})
        self.result = MatchResult("m1", KICKOFF, 2, 0)
        self.odds = OddsSnapshot("m1", KICKOFF - timedelta(hours=3), {Outcome.HOME: 2.1, Outcome.DRAW: 3.2, Outcome.AWAY: 4.0})
    def test_metrics_and_roi(self):
        report = evaluate_predictions([self.prediction], [self.result], [self.odds])
        self.assertEqual(report.matches_evaluated, 1); self.assertEqual(report.bets_placed, 1); self.assertEqual(report.wins, 1)
        self.assertAlmostEqual(report.net_units, 1.1); self.assertAlmostEqual(report.roi, 1.1)
        self.assertIsNotNone(report.brier_score); self.assertIsNotNone(report.log_loss)
    def test_future_odds_are_excluded(self):
        future = OddsSnapshot("m1", KICKOFF - timedelta(minutes=10), {Outcome.HOME: 2.1, Outcome.DRAW: 3.2, Outcome.AWAY: 4.0})
        report = evaluate_predictions([self.prediction], [self.result], [future])
        self.assertEqual(report.bets_placed, 0); self.assertIsNone(report.roi)
    def test_prediction_at_kickoff_is_rejected(self):
        pred = Prediction("m1", KICKOFF, self.prediction.probabilities)
        with self.assertRaises(ValueError): evaluate_predictions([pred], [self.result])
    def test_duplicate_match_ids_are_rejected(self):
        with self.assertRaises(ValueError): evaluate_predictions([self.prediction, self.prediction], [self.result])
    def test_empty_intersection(self):
        report = evaluate_predictions([], [self.result])
        self.assertEqual(report.matches_evaluated, 0); self.assertIsNone(report.brier_score)

if __name__ == "__main__": unittest.main()
