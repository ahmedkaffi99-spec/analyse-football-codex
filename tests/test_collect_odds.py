import unittest

from football_analysis.collect_odds import is_target_bookmaker, only_target_bookmaker


class OneXBetFilterTests(unittest.TestCase):
    def test_matches_only_one_xbet_name(self):
        self.assertTrue(is_target_bookmaker("1xBet"))
        self.assertTrue(is_target_bookmaker("1XBET"))
        self.assertTrue(is_target_bookmaker("1x Bet"))
        self.assertFalse(is_target_bookmaker("Bet365"))
        self.assertFalse(is_target_bookmaker("Marathonbet"))
        self.assertFalse(is_target_bookmaker(None))

    def test_strips_other_bookmakers_and_empty_fixtures(self):
        rows = [
            {
                "fixture": {"id": 100},
                "bookmakers": [
                    {"id": 11, "name": "1xBet", "bets": [{"id": 1, "name": "Match Winner", "values": []}]},
                    {"id": 8, "name": "Bet365", "bets": [{"id": 1, "name": "Match Winner", "values": []}]},
                ],
            },
            {"fixture": {"id": 200}, "bookmakers": [{"id": 8, "name": "Bet365", "bets": []}]},
        ]
        filtered = only_target_bookmaker(rows)
        self.assertEqual(len(filtered), 1)
        self.assertEqual([book["name"] for book in filtered[0]["bookmakers"]], ["1xBet"])
        self.assertEqual(filtered[0]["fixture"]["id"], 100)


if __name__ == "__main__":
    unittest.main()
