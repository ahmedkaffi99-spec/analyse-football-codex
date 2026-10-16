import unittest

from football_analysis.value_analysis import score_market_predictions


class ValueAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "bookmakers": [{
                "name": "1xBet",
                "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "2.0"},
                        {"value": "Draw", "odd": "3.5"},
                        {"value": "Away", "odd": "4.0"}]},
                    {"name": "Double Chance", "values": [
                        {"value": "Home/Draw", "odd": "1.25"},
                        {"value": "Draw/Away", "odd": "1.8"},
                        {"value": "Home/Away", "odd": "1.35"}]},
                    {"name": "Goals Over/Under", "values": [
                        {"value": "Over 2.5", "odd": "1.9"},
                        {"value": "Under 2.5", "odd": "1.9"}]},
                    {"name": "Both Teams To Score", "values": [
                        {"value": "Yes", "odd": "1.8"},
                        {"value": "No", "odd": "2.0"}]},
                    {"name": "Total Corners", "values": [
                        {"value": "Over 8.5", "odd": "1.9"},
                        {"value": "Under 8.5", "odd": "1.9"}]},
                ]},
                {"name": "OtherBook", "bets": [
                    {"name": "Match Winner", "values": [
                        {"value": "Home", "odd": "1.1"},
                        {"value": "Draw", "odd": "9.0"},
                        {"value": "Away", "odd": "20.0"}]}]},
            ]
        }

    def test_scores_supported_families_and_leaves_unsupported_without_edge(self):
        rows = score_market_predictions(
            self.row, model_1x2={"1": 0.60, "x": 0.23, "2": 0.17},
            home_xg=1.8, away_xg=0.9)
        self.assertTrue(rows)
        self.assertTrue(all(row["bookmaker"] == "1xBet" for row in rows))
        by_family = {row["market"]: row for row in rows}
        self.assertIsNotNone(by_family["1x2"]["model_probability"])
        self.assertIsNotNone(by_family["double_chance"]["edge"])
        self.assertIsNotNone(by_family["btts"]["expected_value"])
        self.assertIsNotNone(by_family["total_goals"]["edge"])
        self.assertIsNone(by_family["corners"]["edge"])
        self.assertEqual(by_family["corners"]["value_status"], "odds_only_no_model")

    def test_edge_and_ev_calculation(self):
        rows = score_market_predictions(
            self.row, model_1x2={"1": 0.60, "x": 0.23, "2": 0.17},
            home_xg=1.8, away_xg=0.9)
        home = next(row for row in rows if row["market"] == "1x2")
        self.assertAlmostEqual(home["edge"], home["model_probability"] - home["market_probability"], places=5)
        self.assertAlmostEqual(home["expected_value"], home["model_probability"] * home["odds"] - 1, places=5)


if __name__ == "__main__":
    unittest.main()
