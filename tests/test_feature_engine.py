import unittest
from datetime import datetime, timedelta, timezone

from football_analysis.feature_engine import HistoricalObservation, build_team_features

UTC = timezone.utc
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def row(i, home, away, hg, ag, *, day, stats_at=None, hs=None, aws=None, finished_hour=2):
    kickoff = BASE + timedelta(days=day)
    return HistoricalObservation(
        str(i), kickoff, kickoff + timedelta(hours=finished_hour), home, away, hg, ag,
        stats_at, hs or {}, aws or {},
    )


class FeatureEngineTests(unittest.TestCase):
    def test_uses_only_finished_matches_and_available_stats(self):
        history = [
            row(1, "A", "B", 2, 0, day=1, stats_at=BASE + timedelta(days=7, hours=4),
                hs={"corners": 6, "xg": 1.8}, aws={"corners": 2, "xg": .3}),
            row(2, "C", "A", 1, 1, day=2, stats_at=BASE + timedelta(days=7, hours=4),
                hs={"corners": 4, "xg": 1.1}, aws={"corners": 5, "xg": 1.2}),
            row(3, "A", "C", 9, 0, day=5, stats_at=BASE + timedelta(days=5, hours=4),
                hs={"corners": 12, "xg": 4.0}, aws={"corners": 1, "xg": .1}),
        ]
        target_kickoff = BASE + timedelta(days=6)
        generated_at = target_kickoff - timedelta(hours=1)
        snap = build_team_features(
            match_id="target", home_team="A", away_team="B",
            kickoff_at=target_kickoff, generated_at=generated_at, history=history, windows=(2,),
        )
        # Row 3 finished after the target prediction time and cannot leak in.
        self.assertEqual(snap.features["home_goals_for_avg_2"], 1.5)
        # Stats from rows 1 and 2 were not yet available at prediction time.
        self.assertIsNone(snap.features["home_corners_avg_2"])
        self.assertIn("corners_missing_home", snap.quality_flags)

    def test_home_away_splits_and_missing_stats_are_preserved(self):
        history = [
            row(1, "A", "B", 2, 0, day=1, stats_at=BASE + timedelta(days=1, hours=3),
                hs={"corners": 6, "xg": 2.0}, aws={"corners": 3, "xg": .5}),
            row(2, "C", "A", 0, 1, day=2, stats_at=BASE + timedelta(days=2, hours=3),
                hs={"corners": 4, "xg": .4}, aws={"corners": 5, "xg": 1.0}),
        ]
        target_kickoff = BASE + timedelta(days=5)
        snap = build_team_features(
            match_id="target", home_team="A", away_team="B", kickoff_at=target_kickoff,
            generated_at=target_kickoff - timedelta(hours=1), history=history, windows=(5,),
        )
        self.assertEqual(snap.features["home_venue_goals_for_avg_5"], 2.0)
        self.assertEqual(snap.features["away_goals_for_avg_5"], 0.0)
        self.assertIsNone(snap.features["away_corners_avg_5"])

    def test_rejects_bad_time_duplicate_ids_and_invalid_windows(self):
        kickoff = BASE + timedelta(days=4)
        history = [row(1, "A", "B", 1, 0, day=1)]
        with self.assertRaises(ValueError):
            build_team_features(match_id="x", home_team="A", away_team="B",
                kickoff_at=kickoff, generated_at=kickoff, history=history)
        with self.assertRaises(ValueError):
            build_team_features(match_id="x", home_team="A", away_team="B",
                kickoff_at=kickoff, generated_at=kickoff-timedelta(hours=1), history=history+[history[0]])
        with self.assertRaises(ValueError):
            build_team_features(match_id="x", home_team="A", away_team="B",
                kickoff_at=kickoff, generated_at=kickoff-timedelta(hours=1), history=history, windows=(0,))


if __name__ == "__main__":
    unittest.main()
