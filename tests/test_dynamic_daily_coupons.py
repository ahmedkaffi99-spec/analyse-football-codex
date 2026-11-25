import unittest
from datetime import datetime, timedelta, timezone

from football_analysis.daily_pipeline import build_daily_coupons, render_telegram_coupons

UTC = timezone.utc


def fixture(match_id, *, kickoff=None, home_xg=1.6, away_xg=0.8):
    kickoff = kickoff or datetime.now(UTC) + timedelta(days=1)
    return {
        "match_id": str(match_id),
        "home": f"Home {match_id}",
        "away": f"Away {match_id}",
        "kickoff": kickoff.isoformat(),
        "home_expected_goals": home_xg,
        "away_expected_goals": away_xg,
    }


class DynamicDailyCouponTests(unittest.TestCase):
    def test_six_eligible_matches_create_two_disjoint_three_leg_previews(self):
        report = build_daily_coupons([fixture(i) for i in range(6)])
        self.assertEqual(report["coupon_count"], 2)
        self.assertEqual([len(c["selections"]) for c in report["coupons"]], [3, 3])
        match_ids = [s["match_id"] for c in report["coupons"] for s in c["selections"]]
        self.assertEqual(len(match_ids), len(set(match_ids)))
        self.assertEqual(report["unused_matches"], 0)
        self.assertEqual(report["status"], "preview_only")

    def test_twenty_five_matches_create_five_five_leg_previews(self):
        report = build_daily_coupons([fixture(i) for i in range(25)])
        self.assertEqual(report["coupon_count"], 5)
        self.assertEqual([len(c["selections"]) for c in report["coupons"]], [5, 5, 5, 5, 5])
        match_ids = [s["match_id"] for c in report["coupons"] for s in c["selections"]]
        self.assertEqual(len(match_ids), 25)
        self.assertEqual(len(match_ids), len(set(match_ids)))
        self.assertEqual(report["unused_matches"], 0)

    def test_one_match_is_not_enough_to_create_coupon(self):
        report = build_daily_coupons([fixture("only-match")])
        self.assertEqual(report["coupons"], [])
        self.assertEqual(report["status"], "insufficient_matches")

    def test_started_matches_are_not_eligible(self):
        report = build_daily_coupons([
            fixture("past", kickoff=datetime.now(UTC) - timedelta(minutes=10)),
            fixture("future"),
        ])
        self.assertEqual(report["eligible_matches"], 1)
        self.assertEqual(report["coupons"], [])

    def test_duplicate_fixture_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate match_id"):
            build_daily_coupons([fixture("same"), fixture("same")])

    def test_preview_renderer_has_no_publish_claim(self):
        message = render_telegram_coupons(build_daily_coupons([fixture(i) for i in range(6)]))
        self.assertIn("PRÉVISUALISATION MULTI-COUPONS", message)
        self.assertIn("aucune publication", message.lower())


if __name__ == "__main__":
    unittest.main()
