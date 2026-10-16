import unittest
from football_analysis.market_agents import count_market_probability, team_metric_rate
from football_analysis.all_markets import _category, extract_market_predictions

class SpecialistMarketAgentTests(unittest.TestCase):
    def test_market_names_do_not_confuse_shots_with_goals(self):
        self.assertEqual(_category("Total Shots Over/Under"), "shots")
        self.assertEqual(_category("Total Corners"), "corners")
        self.assertEqual(_category("Goals Over/Under"), "total_goals")
        self.assertEqual(_category("Total Fouls"), "fouls")

    def test_count_market_poisson_requires_fractional_line(self):
        p_over = count_market_probability(10.0, "Over 8.5", 8.5)
        p_under = count_market_probability(10.0, "Under 8.5", 8.5)
        self.assertIsNotNone(p_over)
        self.assertAlmostEqual(p_over + p_under, 1.0, places=6)
        self.assertIsNone(count_market_probability(10.0, "Over 9", 9.0))

    def test_corner_agent_requires_real_samples_from_both_teams(self):
        home = {"corners_mean": 5.2, "corners_n": 8}
        away = {"corners_mean": 4.1, "corners_n": 9}
        self.assertAlmostEqual(team_metric_rate("corners", home, away), 9.3)
        self.assertIsNone(team_metric_rate("corners", home, {"corners_mean": 3.0, "corners_n": 2}))

    def test_extracts_both_sides_of_a_market(self):
        row = {"bookmakers": [{"name": "1xBet", "bets": [{"name": "Total Corners", "values": [
            {"value": "Over 8.5", "odd": "1.9"}, {"value": "Under 8.5", "odd": "1.9"}]}]}]}
        rows = extract_market_predictions(row)
        self.assertEqual(len(rows), 2)
        self.assertEqual({x["selection"] for x in rows}, {"Over 8.5", "Under 8.5"})

if __name__ == "__main__":
    unittest.main()
