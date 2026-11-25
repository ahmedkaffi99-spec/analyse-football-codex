import unittest

from football_analysis.oddspapi_normalizer import normalize_oddspapi_payload


CATALOG = {
    "100": {"name": "Full Time Result", "type": "1x2", "handicap": None,
            "period": "FT", "outcomes": {"1": "Home", "X": "Draw", "2": "Away"}},
    "101": {"name": "Total Corners", "type": "total", "handicap": 8.5,
            "period": "FT", "outcomes": {"O": "Over 8.5", "U": "Under 8.5"}},
}


def event(markets, bookmaker="1xbet"):
    return {"fixtureId": "fixture-1", "bookmakerOdds": {bookmaker: {"markets": markets}}}


class OddsPapiNormalizerTests(unittest.TestCase):
    def test_normalizes_all_markets_and_keeps_raw_names(self):
        payload = event({
            "100": {"outcomes": {
                "1": {"players": {"0": {"price": 2.1}}},
                "X": {"players": {"0": {"price": "3.4"}}},
                "2": {"players": {"0": {"price": 3.7}}},
            }},
            "101": {"outcomes": {
                "O": {"players": {"0": {"price": 1.9}}},
                "U": {"players": {"0": {"price": 1.9}}},
            }},
        })
        result = normalize_oddspapi_payload(payload, CATALOG)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["markets"]), 2)
        self.assertEqual(result["markets"][0]["market"], "Full Time Result")
        self.assertEqual(result["markets"][0]["selections"][1]["odds"], 3.4)
        self.assertEqual(result["markets"][1]["handicap"], 8.5)
        self.assertEqual(result["diagnostics"]["outcomes_valid"], 5)

    def test_invalid_prices_are_counted_and_suspended_outcomes_omitted(self):
        payload = event({"100": {"outcomes": {
            "1": {"players": {"0": {"price": 1.0}}},
            "X": {"players": {"0": {"price": None}}},
            "2": {"players": {"0": {"price": float("nan")}}},
        }}})
        result = normalize_oddspapi_payload(payload, CATALOG)
        self.assertEqual(result["status"], "no_valid_odds")
        self.assertEqual(result["markets"], [])
        self.assertEqual(result["diagnostics"]["invalid_prices"], 3)

    def test_bookmaker_name_matching_is_case_insensitive(self):
        result = normalize_oddspapi_payload(event({"100": {"outcomes": {
            "1": {"players": {"0": {"price": 2.0}}},
            "X": {"players": {"0": {"price": 3.0}}},
        }}, bookmaker="1XBET"), CATALOG)
        self.assertEqual(result["status"], "ok")

    def test_missing_catalog_uses_raw_fallback_labels(self):
        result = normalize_oddspapi_payload(event({"999": {"outcomes": {
            "a": {"players": {"0": {"price": 2.0}}},
            "b": {"players": {"0": {"price": 2.0}}},
        }}), {})
        self.assertEqual(result["markets"][0]["market"], "Market 999")
        self.assertEqual(result["markets"][0]["selections"][0]["selection"], "Option a")

    def test_empty_payload_and_missing_bookmaker_have_distinct_statuses(self):
        self.assertEqual(normalize_oddspapi_payload(None, {})["status"], "no_events")
        self.assertEqual(normalize_oddspapi_payload({"fixtureId": "x"}, {})["status"], "no_bookmaker")
        self.assertEqual(normalize_oddspapi_payload(event({}), {})["status"], "no_markets")

    def test_invalid_payloads_are_not_silently_coerced(self):
        result = normalize_oddspapi_payload("not a payload", {})
        self.assertEqual(result["status"], "no_events")
        self.assertEqual(result["markets"], [])


if __name__ == "__main__":
    unittest.main()
