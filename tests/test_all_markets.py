import unittest
from football_analysis.all_markets import extract_market_predictions

class AllMarketsTests(unittest.TestCase):
    def test_extracts_multiple_market_families_only_from_1xbet(self):
        row = {"fixture":{"id":1},"bookmakers":[
            {"name":"OtherBook","bets":[{"name":"Total Goals","values":[{"value":"Over 2.5","odd":"1.9"},{"value":"Under 2.5","odd":"1.9"}]}]},
            {"name":"1xBet","bets":[
                {"name":"Match Winner","values":[{"value":"Home","odd":"2.0"},{"value":"Draw","odd":"3.0"},{"value":"Away","odd":"4.0"}]},
                {"name":"Double Chance","values":[{"value":"Home/Draw","odd":"1.3"},{"value":"Draw/Away","odd":"1.7"},{"value":"Home/Away","odd":"1.4"}]},
                {"name":"Goals Over/Under","values":[{"value":"Over 2.5","odd":"1.9"},{"value":"Under 2.5","odd":"1.9"}]},
                {"name":"Both Teams To Score","values":[{"value":"Yes","odd":"1.8"},{"value":"No","odd":"2.0"}]},
                {"name":"Total Corners","values":[{"value":"Over 8.5","odd":"1.9"},{"value":"Under 8.5","odd":"1.9"}]},
                {"name":"Total Yellow Cards","values":[{"value":"Over 3.5","odd":"2.0"},{"value":"Under 3.5","odd":"1.8"}]},
                {"name":"Asian Handicap","values":[{"value":"Home -1.5","odd":"2.1"},{"value":"Away +1.5","odd":"1.7"}]}
            ]}
        ]}
        result = extract_market_predictions(row)
        categories = {item["market"] for item in result}
        self.assertTrue({"1x2", "double_chance", "total_goals", "btts", "corners", "yellow_cards"}.issubset(categories))
        self.assertNotIn("OtherBook", {item["bookmaker"] for item in result})
        self.assertTrue(all(0 < item["probability"] < 1 for item in result))

if __name__ == "__main__": unittest.main()
