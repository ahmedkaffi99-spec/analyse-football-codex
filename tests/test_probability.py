import unittest
from football_analysis.models import Outcome
from football_analysis.probability import implied_probabilities, normalize_probabilities

class ProbabilityTests(unittest.TestCase):
    def test_normalize_weights(self):
        result = normalize_probabilities({Outcome.HOME: 2, Outcome.DRAW: 1, Outcome.AWAY: 1})
        self.assertAlmostEqual(result[Outcome.HOME], 0.5)
        self.assertAlmostEqual(sum(result.values()), 1.0)
    def test_rejects_zero_weights(self):
        with self.assertRaises(ValueError): normalize_probabilities({Outcome.HOME: 0, Outcome.DRAW: 0, Outcome.AWAY: 0})
    def test_market_margin_removal(self):
        odds = {Outcome.HOME: 2.0, Outcome.DRAW: 3.5, Outcome.AWAY: 4.0}
        self.assertGreater(sum(implied_probabilities(odds, remove_margin=False).values()), 1.0)
        self.assertAlmostEqual(sum(implied_probabilities(odds).values()), 1.0)
    def test_rejects_invalid_odds(self):
        with self.assertRaises(ValueError): implied_probabilities({Outcome.HOME: 1.0, Outcome.DRAW: 3.0, Outcome.AWAY: 4.0})

if __name__ == "__main__": unittest.main()
