import unittest

from football_analysis.risk_selection import RiskConfig, select_coupon_preview


def candidate(fixture, probability, odds=2.0, *, market="1x2", selection="home", edge=0.05, binary=True):
    return {"fixture_id": fixture, "market": market, "selection": selection,
            "line": None, "probability": probability, "decimal_odds": odds,
            "edge": edge, "binary": binary}


class RiskSelectionTests(unittest.TestCase):
    def test_preview_ranks_and_caps_one_leg_per_fixture(self):
        candidates = [
            candidate("m1", .65, selection="home"),
            candidate("m1", .62, market="btts", selection="yes"),
            candidate("m2", .60, odds=1.5),
            candidate("m3", .55, odds=1.8),
        ]
        report = select_coupon_preview(candidates, RiskConfig(coupon_min=2, coupon_max=3))
        self.assertTrue(report["generated"])
        self.assertEqual([row["fixture_id"] for row in report["selections"]], ["m1", "m2"])
        self.assertAlmostEqual(report["combined_probability"], .65 * .60)
        self.assertAlmostEqual(report["total_odds"], 3.0)
        self.assertTrue(any("fixture already represented" in row["rejection_reasons"][0]
                          for row in report["rejected"]))

    def test_duplicate_pick_key_rejected_even_when_fixture_cap_allows_two(self):
        rows = [candidate("m1", .7), candidate("m1", .6), candidate("m2", .65)]
        report = select_coupon_preview(rows, RiskConfig(coupon_min=2, coupon_max=3, max_per_fixture=2))
        self.assertTrue(report["generated"])
        self.assertEqual(len(report["selections"]), 2)
        self.assertTrue(any("duplicate pick key" in row["rejection_reasons"][0] for row in report["rejected"]))

    def test_non_binary_invalid_probability_and_odds_are_rejected(self):
        rows = [candidate("m1", .7, binary=False), candidate("m2", 1.2),
                candidate("m3", .5, odds=1.0)]
        report = select_coupon_preview(rows, RiskConfig(coupon_min=1, coupon_max=3))
        self.assertFalse(report["generated"])
        self.assertEqual(report["selections"], [])
        self.assertEqual(len(report["rejected"]), 3)

    def test_allowlist_edge_and_probability_filters(self):
        config = RiskConfig(coupon_min=1, coupon_max=2, allowed_markets=frozenset({"1x2"}),
                           probability_min=.6, edge_min=0.0, edge_max=.2)
        rows = [candidate("m1", .7, market="corners", edge=.1),
                candidate("m2", .5, edge=.1), candidate("m3", .7, edge=-.1),
                candidate("m4", .7, edge=.3), candidate("m5", .7, edge=.1)]
        report = select_coupon_preview(rows, config)
        self.assertTrue(report["generated"])
        self.assertEqual([row["fixture_id"] for row in report["selections"]], ["m5"])
        self.assertEqual(len(report["rejected"]), 4)

    def test_calibration_requirement_and_insufficient_coupon(self):
        config = RiskConfig(coupon_min=2, coupon_max=3, require_calibration=True, calibration_min_n=30)
        rows = [candidate("m1", .7), candidate("m2", .7)]
        report = select_coupon_preview(rows, config)
        self.assertFalse(report["generated"])
        self.assertEqual(len(report["rejected"]), 2)
        self.assertIn("calibration required", report["rejected"][0]["rejection_reasons"])

    def test_invalid_config_rejected(self):
        with self.assertRaises(ValueError):
            RiskConfig(coupon_min=3, coupon_max=2)
        with self.assertRaises(ValueError):
            RiskConfig(odds_min=1.0)


if __name__ == "__main__":
    unittest.main()
