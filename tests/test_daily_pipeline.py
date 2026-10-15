import unittest
from datetime import datetime, timedelta, timezone

from football_analysis.daily_pipeline import build_daily_coupon, parse_fixture, render_telegram_message

UTC = timezone.utc


def fixture(match_id="m1", *, kickoff=None, home_xg=1.8, away_xg=0.7):
    kickoff = kickoff or datetime.now(UTC) + timedelta(days=1)
    return {
        "match_id": match_id, "home": "Home FC", "away": "Away FC",
        "kickoff": kickoff.isoformat(),
        "home_expected_goals": home_xg, "away_expected_goals": away_xg,
    }


class DailyPipelineTests(unittest.TestCase):
    def test_builds_single_coupon_with_market_weight_disabled(self):
        report = build_daily_coupon([fixture()])
        self.assertEqual(report["market_weight"], 0.0)
        self.assertEqual(len(report["coupon"]), 1)
        self.assertEqual(report["coupon"][0]["pick_label"], "1")
        self.assertEqual(report["status"], "preview_only")

    def test_skips_started_matches(self):
        report = build_daily_coupon([fixture(kickoff=datetime.now(UTC) - timedelta(hours=1))])
        self.assertEqual(report["coupon"], [])
        self.assertEqual(report["status"], "no_upcoming_fixtures")

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            build_daily_coupon([fixture(), fixture()])

    def test_timezone_required(self):
        row = fixture()
        row["kickoff"] = "2026-12-01T18:00:00"
        with self.assertRaises(ValueError):
            parse_fixture(row)

    def test_message_has_warning(self):
        message = render_telegram_message(build_daily_coupon([fixture()]))
        self.assertIn("Influence des cotes : désactivée", message)
        self.assertIn("pas une garantie", message)

    def test_empty_coupon_message(self):
        message = render_telegram_message(build_daily_coupon([]))
        self.assertIn("Aucun match futur", message)


if __name__ == "__main__":
    unittest.main()
