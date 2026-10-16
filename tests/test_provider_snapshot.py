import unittest
from unittest.mock import patch

from football_analysis.provider_snapshot import collect_snapshot


def page_row(fid, bookmaker_name):
    return {
        "fixture": {"id": fid},
        "bookmakers": [{
            "id": 8,
            "name": bookmaker_name,
            "bets": [{
                "id": 1,
                "name": "Match Winner",
                "values": [
                    {"value": "Home", "odd": "1.80"},
                    {"value": "Draw", "odd": "3.50"},
                    {"value": "Away", "odd": "4.50"},
                ],
            }],
        }],
    }


class ProviderSnapshotTests(unittest.TestCase):
    @patch("football_analysis.provider_snapshot.api_get")
    def test_paginates_filters_bookmaker_and_preserves_capture_time(self, api_get):
        api_get.side_effect = [
            {"response": [page_row(10, "1xBet"), page_row(11, "Other")],
             "paging": {"current": 1, "total": 2}},
            {"response": [page_row(12, "1X BET")],
             "paging": {"current": 2, "total": 2}},
        ]
        result = collect_snapshot("2026-10-16")
        self.assertEqual(api_get.call_count, 2)
        self.assertEqual(result["fixtures_count"], 2)
        self.assertEqual(len(result["quotes"]), 6)
        self.assertEqual({q["fixture_id"] for q in result["quotes"]}, {"10", "12"})
        self.assertTrue(all(q["captured_at"] == result["captured_at"] for q in result["quotes"]))
        self.assertFalse(result["truncated"])

    def test_max_pages_must_be_positive(self):
        with self.assertRaises(ValueError):
            collect_snapshot("2026-10-16", max_pages=0)


if __name__ == "__main__":
    unittest.main()
