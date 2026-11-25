import unittest

from football_analysis.historical_model_selector import compare_market, select_by_market


def history(model, results, odds=2.0, start="2026-01-01"):
    return [
        {"market": "1x2", "date": f"2026-01-{day:02d}", "result": outcome,
         "probability": 0.6 if model == "a" else 0.4, "decimal_odds": odds}
        for day, outcome in enumerate(results, 1)
    ]


class HistoricalModelSelectorTests(unittest.TestCase):
    def test_roi_winner_and_chronological_stability(self):
        a = history("a", ["win", "win", "win", "loss"])
        b = history("b", ["loss", "loss", "loss", "loss"])
        result = compare_market(a, b, model_a="poisson", model_b="market", n_min=4)
        self.assertEqual(result["decision"], "poisson")
        self.assertTrue(result["stable"])
        self.assertAlmostEqual(result["model_a"]["roi"], 0.5)
        self.assertAlmostEqual(result["model_b"]["roi"], -1.0)

    def test_insufficient_samples_do_not_produce_a_decision(self):
        result = compare_market(history("a", ["win", "loss"]), history("b", ["loss", "win"]), n_min=5)
        self.assertEqual(result["decision"], "unavailable")
        self.assertIsNone(result["stable"])

    def test_pushes_are_not_roi_bets_and_missing_odds_do_not_hide_graded_sample(self):
        a = history("a", ["win", "push", "loss", "win"])
        a[0].pop("decimal_odds")
        b = history("b", ["loss", "push", "loss", "loss"])
        result = compare_market(a, b, n_min=4)
        self.assertTrue(result["model_a"]["available"])
        self.assertEqual(result["model_a"]["n"], 4)
        self.assertEqual(result["model_a"]["n_bets"], 3)

    def test_tie_when_roi_difference_is_under_one_point(self):
        a = history("a", ["win", "loss", "win", "loss"], odds=2.0)
        b = history("b", ["win", "loss", "win", "loss"], odds=2.0)
        result = compare_market(a, b, n_min=4)
        self.assertEqual(result["decision"], "tie")

    def test_selects_per_market_and_reports_missing_market(self):
        a = {"1x2": history("a", ["win", "win", "win", "loss"])}
        b = {"1x2": history("b", ["loss", "loss", "loss", "loss"]), "corners": []}
        results = select_by_market(a, b, model_a="poisson", model_b="market", n_min=4)
        self.assertEqual(results["1x2"]["decision"], "poisson")
        self.assertEqual(results["corners"]["decision"], "unavailable")

    def test_bad_minimum_rejected(self):
        with self.assertRaises(ValueError):
            compare_market([], [], n_min=1)


if __name__ == "__main__":
    unittest.main()
