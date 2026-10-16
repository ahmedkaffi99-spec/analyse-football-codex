import unittest
from datetime import datetime, timedelta, timezone

from football_analysis.strengths import HistoricalMatch
from football_analysis.walk_forward import walk_forward_backtest

UTC = timezone.utc
BASE = datetime(2025, 1, 1, tzinfo=UTC)


def make_match(i, home, away, hg, ag, day=None):
    return HistoricalMatch(str(i), BASE + timedelta(days=i if day is None else day), home, away, hg, ag)


class WalkForwardTests(unittest.TestCase):
    def test_predictions_use_only_earlier_completed_history(self):
        rows = [
            make_match(1, "A", "B", 2, 0),
            make_match(2, "B", "C", 0, 1),
            make_match(3, "C", "A", 1, 1),
            make_match(4, "A", "C", 3, 0),
            make_match(5, "B", "A", 0, 2),
            make_match(6, "C", "B", 0, 1),
            make_match(7, "A", "B", 2, 0),
        ]
        report = walk_forward_backtest(rows, min_train_matches=5)
        self.assertEqual([p.match_id for p in report.predictions], ["6", "7"])
        self.assertEqual(report.report.matches_evaluated, 2)
        self.assertEqual(report.skipped_matches, ("1", "2", "3", "4", "5"))

    def test_same_kickoff_matches_are_not_used_as_each_others_training_data(self):
        rows = [
            make_match(1, "A", "B", 2, 0, day=1),
            make_match(2, "B", "C", 0, 1, day=2),
            make_match(3, "C", "A", 1, 1, day=3),
            make_match(4, "A", "C", 3, 0, day=4),
            make_match(5, "B", "A", 0, 2, day=5),
            make_match(6, "A", "B", 1, 0, day=6),
            make_match(7, "B", "C", 0, 2, day=6),
        ]
        report = walk_forward_backtest(rows, min_train_matches=5)
        self.assertIn("6", [p.match_id for p in report.predictions])
        self.assertIn("7", [p.match_id for p in report.predictions])

    def test_rejects_duplicate_ids_and_invalid_minimum(self):
        row = make_match(1, "A", "B", 1, 0)
        with self.assertRaises(ValueError):
            walk_forward_backtest([row, row])
        with self.assertRaises(ValueError):
            walk_forward_backtest([row], min_train_matches=0)


if __name__ == "__main__":
    unittest.main()
