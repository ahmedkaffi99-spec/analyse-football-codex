import unittest
from football_analysis.models import Outcome
from football_analysis.poisson import poisson_1x2


class PoissonBaselineTests(unittest.TestCase):
    def test_symmetric_rates_have_symmetric_home_and_away_probabilities(self):
        result = poisson_1x2(1.35, 1.35)
        self.assertAlmostEqual(result[Outcome.HOME], result[Outcome.AWAY], places=12)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=12)

    def test_higher_home_rate_increases_home_win_probability(self):
        balanced = poisson_1x2(1.2, 1.2)
        home_favored = poisson_1x2(2.0, 0.8)
        self.assertGreater(home_favored[Outcome.HOME], balanced[Outcome.HOME])

    def test_rejects_negative_or_non_finite_rates(self):
        for home_rate in (-0.1, float("nan"), float("inf")):
            with self.subTest(home_rate=home_rate):
                with self.assertRaises(ValueError): poisson_1x2(home_rate, 1.0)

    def test_rejects_invalid_grid_size(self):
        with self.assertRaises(ValueError): poisson_1x2(1.0, 1.0, max_goals=0)


if __name__ == "__main__":
    unittest.main()
