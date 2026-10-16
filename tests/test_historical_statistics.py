import unittest
from datetime import datetime, timezone, timedelta

from football_analysis.daily_api_pipeline import _parse_fixture_statistics, summarize_last_ten


class HistoricalStatisticsTests(unittest.TestCase):
    def test_parses_goals_corners_shots_cards_and_percentages(self):
        parsed = _parse_fixture_statistics([
            {"team": {"id": 1, "name": "Home FC"}, "statistics": [
                {"type": "Total Shots", "value": 12},
                {"type": "Shots on Goal", "value": 5},
                {"type": "Corner Kicks", "value": 7},
                {"type": "Yellow Cards", "value": 2},
                {"type": "Red Cards", "value": 0},
                {"type": "Ball Possession", "value": "61%"},
                {"type": "Expected Goals", "value": "1.75"},
            ]}
        ])
        self.assertEqual(parsed["Home FC"]["shots"], 12)
        self.assertEqual(parsed["Home FC"]["shots_on_target"], 5)
        self.assertEqual(parsed["Home FC"]["corners"], 7)
        self.assertEqual(parsed["Home FC"]["yellow_cards"], 2)
        self.assertEqual(parsed["Home FC"]["red_cards"], 0)
        self.assertEqual(parsed["Home FC"]["possession_pct"], 61)
        self.assertEqual(parsed["Home FC"]["xg"], 1.75)

    def test_averages_only_available_stats_across_latest_ten(self):
        rows = []
        stats = {}
        now = datetime.now(timezone.utc)
        for i in range(12):
            fid = 100 + i
            rows.append({
                "fixture": {"id": fid, "date": (now - timedelta(days=i+1)).isoformat(),
                            "status": {"short": "FT"}},
                "teams": {"home": {"id": 1, "name": "Alpha"},
                          "away": {"id": 2, "name": "Beta"}},
                "goals": {"home": i % 4, "away": 1},
            })
            stats[str(fid)] = {
                "Alpha": {"corners": float(i), "shots": 10.0 + i,
                          "shots_on_target": 4.0, "yellow_cards": 1.0}
            }
        summary = summarize_last_ten(1, rows, stats)
        self.assertEqual(summary["matches_used"], 10)
        self.assertEqual(summary["goals_for_n"], 10)
        self.assertEqual(summary["corners_n"], 10)
        # Most recent ten are i=0..9.
        self.assertAlmostEqual(summary["corners_mean"], 4.5)
        self.assertAlmostEqual(summary["shots_mean"], 14.5)
        self.assertAlmostEqual(summary["yellow_cards_mean"], 1.0)

    def test_missing_stats_are_null_not_zero(self):
        now = datetime.now(timezone.utc)
        rows = [{
            "fixture": {"id": 5, "date": now.isoformat(), "status": {"short": "FT"}},
            "teams": {"home": {"id": 1, "name": "Alpha"}, "away": {"id": 2, "name": "Beta"}},
            "goals": {"home": 2, "away": 0},
        }]
        summary = summarize_last_ten(1, rows, {})
        self.assertEqual(summary["goals_for_mean"], 2)
        self.assertIsNone(summary["corners_mean"])
        self.assertEqual(summary["corners_n"], 0)


if __name__ == "__main__":
    unittest.main()
