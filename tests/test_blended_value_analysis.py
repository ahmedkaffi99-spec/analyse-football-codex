import unittest

from football_analysis.value_analysis import score_market_predictions


def odds_row():
    return {
        "bookmakers": [{
            "name": "1xBet",
            "bets": [{
                "name": "Match Winner",
                "values": [
                    {"value": "Home", "odd": "2.0"},
                    {"value": "Draw", "odd": "3.5"},
                    {"value": "Away", "odd": "4.0"},
                ],
            }],
        }],
    }


class BlendedValueAnalysisTests(unittest.TestCase):
    def test_default_weight_blend_is_reported_without_overwriting_model_ev(self):
        rows = score_market_predictions(
            odds_row(), model_1x2={"1": 0.60, "x": 0.23, "2": 0.17},
            home_xg=1.8, away_xg=0.9,
        )
        home = next(row for row in rows if row["market"] == "1x2" and row["selection"] == "Home")
        self.assertEqual(home["market_weight"], 0.65)
        expected_blended = 0.35 * home["model_probability"] + 0.65 * home["market_probability"]
        self.assertAlmostEqual(home["blended_probability"], expected_blended, places=6)
        self.assertAlmostEqual(home["expected_value"], home["model_probability"] * home["odds"] - 1, places=6)
        self.assertAlmostEqual(home["blended_expected_value"], home["blended_probability"] * home["odds"] - 1, places=6)

    def test_weight_override_changes_only_blended_fields(self):
        default = score_market_predictions(
            odds_row(), model_1x2={"1": 0.60, "x": 0.23, "2": 0.17},
            home_xg=1.8, away_xg=0.9,
        )
        custom = score_market_predictions(
            odds_row(), model_1x2={"1": 0.60, "x": 0.23, "2": 0.17},
            home_xg=1.8, away_xg=0.9, market_weight=0.25,
        )
        home_default = next(row for row in default if row["market"] == "1x2" and row["selection"] == "Home")
        home_custom = next(row for row in custom if row["market"] == "1x2" and row["selection"] == "Home")
        self.assertEqual(home_custom["market_weight"], 0.25)
        self.assertEqual(home_custom["model_probability"], home_default["model_probability"])
        self.assertEqual(home_custom["expected_value"], home_default["expected_value"])
        self.assertNotEqual(home_custom["blended_probability"], home_default["blended_probability"])


if __name__ == "__main__":
    unittest.main()
