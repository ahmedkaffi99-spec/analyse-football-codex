import unittest

from football_analysis.market_families import family_for_category, classify_market, group_candidates_by_family


class MarketFamilyTaxonomyTests(unittest.TestCase):
    def test_result_categories_share_family(self):
        self.assertEqual(family_for_category("1x2").id, "result")
        self.assertEqual(family_for_category("double chance").id, "result")
        self.assertEqual(family_for_category("dnb").id, "result")

    def test_statistical_market_families(self):
        expected = {"total_goals": "goals_total", "win_to_nil": "team_goals",
                    "btts": "btts", "handicap": "handicap", "corners": "corners",
                    "yellow_cards": "cards", "shots_on_target": "shots",
                    "fouls": "fouls", "offsides": "offsides"}
        for category, family in expected.items():
            with self.subTest(category=category):
                self.assertEqual(family_for_category(category).id, family)

    def test_unknown_category_is_explicitly_derived(self):
        report = classify_market({"market": "novel_market"})
        self.assertEqual(report["family_id"], "derived")
        self.assertFalse(report["known_category"])

    def test_groups_preserve_order_and_candidate_payload(self):
        candidates = [{"id": "a", "market": "corners"}, {"id": "b", "market": "1x2"},
                     {"id": "c", "market": "corners"}, {"id": "d", "market": "unknown"}]
        groups = group_candidates_by_family(candidates)
        self.assertEqual([row["id"] for row in groups["corners"]], ["a", "c"])
        self.assertEqual([row["id"] for row in groups["result"]], ["b"])
        self.assertEqual([row["id"] for row in groups["derived"]], ["d"])


if __name__ == "__main__":
    unittest.main()
