import unittest
from math import nan

from football_analysis.probability_blend import (
    DEFAULT_MARKET_WEIGHT,
    blend_probability,
    validate_market_weight,
)


class ProbabilityBlendTests(unittest.TestCase):
    def test_default_market_weight_preserves_reference_value(self):
        self.assertEqual(DEFAULT_MARKET_WEIGHT, 0.65)
        self.assertAlmostEqual(blend_probability(0.4, 0.6), 0.53)

    def test_explicit_weight(self):
        self.assertAlmostEqual(blend_probability(0.4, 0.6, weight=0.25), 0.45)

    def test_weight_endpoints(self):
        self.assertAlmostEqual(blend_probability(0.4, 0.6, weight=0.0), 0.4)
        self.assertAlmostEqual(blend_probability(0.4, 0.6, weight=1.0), 0.6)

    def test_overlapping_market_aggregate_is_not_clamped(self):
        self.assertAlmostEqual(blend_probability(0.8, 1.2), 1.06)

    def test_invalid_weights_rejected(self):
        for value in (-0.01, 1.01, nan, "invalid", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_market_weight(value)

    def test_invalid_probability_inputs_rejected(self):
        for model, market in ((None, 0.5), (0.5, None), (-0.1, 0.5), (0.5, nan)):
            with self.subTest(model=model, market=market):
                with self.assertRaises(ValueError):
                    blend_probability(model, market)


if __name__ == "__main__":
    unittest.main()
