import unittest

from football_analysis.statistical_shrinkage import DEFAULT_PRIORS, shrink_mean, shrink_metric


class StatisticalShrinkageTests(unittest.TestCase):
    def test_additive_prior_reduces_extreme_small_sample_mean(self):
        adjusted = shrink_mean(0.2, 3, 1.335, k=5)
        self.assertAlmostEqual(adjusted, (0.2 * 3 + 1.335 * 5) / 8)
        self.assertGreater(adjusted, 0.2)

    def test_full_sample_is_still_shrunk_not_100_percent_raw(self):
        adjusted = shrink_mean(1.0, 10, 1.335, k=5)
        self.assertAlmostEqual(adjusted, (10 + 1.335 * 5) / 15)
        self.assertNotEqual(adjusted, 1.0)

    def test_missing_sample_metadata_preserves_measured_mean(self):
        self.assertEqual(shrink_mean(4.5, None, 4.8), 4.5)
        self.assertEqual(shrink_mean(4.5, 10, 4.8, k=0), 4.5)

    def test_invalid_inputs_are_not_fabricated(self):
        self.assertIsNone(shrink_mean(None, 5, 4.8))
        self.assertIsNone(shrink_mean(4.5, -1, 4.8))
        self.assertIsNone(shrink_mean(float("nan"), 5, 4.8))
        self.assertIsNone(shrink_mean(4.5, 5, float("nan")))

    def test_registered_and_unregistered_metric_behavior(self):
        self.assertAlmostEqual(shrink_metric("corners", 6, 5), (6 * 5 + DEFAULT_PRIORS["corners"] * 5) / 10)
        self.assertEqual(shrink_metric("red_cards", 0.1, 5), 0.1)


if __name__ == "__main__":
    unittest.main()
