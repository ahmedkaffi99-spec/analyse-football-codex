import unittest

from football_analysis.coupon_profiles import (
    coupon_count_for_matches,
    build_dynamic_profiles,
    verify_cross_coupon_match_uniqueness,
)


class CouponProfileTests(unittest.TestCase):
    def test_reference_coupon_count_tiers(self):
        expected = {
            0: 0, 1: 0, 2: 1, 5: 1, 6: 2, 9: 2,
            10: 3, 15: 3, 16: 4, 19: 4, 20: 5, 25: 5,
        }
        for matches, count in expected.items():
            with self.subTest(matches=matches):
                self.assertEqual(coupon_count_for_matches(matches), count)

    def test_invalid_match_counts_rejected(self):
        for value in (-1, 1.5, True, "5"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    coupon_count_for_matches(value)

    def test_leg_budgets_are_bounded_by_pool(self):
        for matches in (2, 6, 9, 10, 16, 20, 25):
            profiles = build_dynamic_profiles(matches)
            self.assertTrue(profiles)
            self.assertTrue(all(2 <= profile["max_legs"] <= 5 for profile in profiles))
            self.assertLessEqual(sum(profile["max_legs"] for profile in profiles), matches)

    def test_zero_or_one_match_creates_no_profile(self):
        self.assertEqual(build_dynamic_profiles(0), [])
        self.assertEqual(build_dynamic_profiles(1), [])

    def test_duplicate_match_ids_across_coupons_blocked(self):
        coupons = [
            {"profile": "safe", "selections": [{"match_id": "m1"}]},
            {"profile": "balanced", "selections": [{"match_id": "m1"}]},
        ]
        with self.assertRaisesRegex(ValueError, "appears in both"):
            verify_cross_coupon_match_uniqueness(coupons)

    def test_missing_match_id_blocked(self):
        with self.assertRaisesRegex(ValueError, "without match_id"):
            verify_cross_coupon_match_uniqueness([{"profile": "safe", "selections": [{}]}])

    def test_unique_matches_allowed(self):
        verify_cross_coupon_match_uniqueness([
            {"profile": "safe", "selections": [{"match_id": "m1"}]},
            {"profile": "balanced", "selections": [{"match_id": "m2"}]},
        ])


if __name__ == "__main__":
    unittest.main()
