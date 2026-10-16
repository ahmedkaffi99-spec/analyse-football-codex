import unittest

from football_analysis.markets import (
    flatten_api_football_odds,
    implied_probability,
    normalize_implied_probabilities,
    poisson_distribution,
    poisson_market_probabilities,
)


class MarketUtilitiesTests(unittest.TestCase):
    def test_implied_probability(self):
        self.assertAlmostEqual(implied_probability(2.0), 0.5)
        with self.assertRaises(ValueError):
            implied_probability(1.0)

    def test_remove_overround(self):
        probs = normalize_implied_probabilities({"home": 2.0, "draw": 3.5, "away": 4.0})
        self.assertAlmostEqual(sum(probs.values()), 1.0)
        self.assertGreater(probs["home"], probs["away"])

    def test_poisson_distribution_normalized(self):
        distribution = poisson_distribution(1.4, max_goals=10)
        self.assertAlmostEqual(sum(distribution), 1.0)
        self.assertTrue(all(value >= 0 for value in distribution))

    def test_poisson_markets_are_valid(self):
        markets = poisson_market_probabilities(1.5, 1.0)
        self.assertAlmostEqual(sum(markets["1x2"].values()), 1.0, places=7)
        self.assertAlmostEqual(sum(markets["btts"].values()), 1.0, places=7)
        self.assertGreater(markets["1x2"]["home"], markets["1x2"]["away"])
        self.assertIn("2.5", markets["totals"])
        self.assertIn("1-0", markets["correct_scores"])

    def test_flatten_odds_keeps_unknown_markets(self):
        rows = [{
            "fixture": {"id": 123},
            "bookmakers": [{
                "id": 8,
                "name": "Example Bookmaker",
                "bets": [{
                    "id": 999,
                    "name": "Special market name",
                    "values": [
                        {"value": "Yes", "odd": "1.91"},
                        {"value": "No", "odd": "1.99"},
                        {"value": "invalid", "odd": "N/A"},
                    ],
                }],
            }],
        }]
        quotes = flatten_api_football_odds(rows, captured_at="2026-10-16T00:00:00Z")
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0].fixture_id, "123")
        self.assertEqual(quotes[0].market_id, "999")
        self.assertEqual(quotes[0].market_name, "Special market name")
        self.assertEqual(quotes[0].selection, "Yes")
        self.assertEqual(quotes[0].odds, 1.91)
        self.assertEqual(quotes[0].captured_at, "2026-10-16T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
