import http.client
import json
import threading
import unittest
from http.server import HTTPServer

from football_analysis.preview_api import (
    health_payload, preview_1x2, preview_coupon, preview_coverage,
    make_handler, run_server,
)


class OfflinePreviewAPITests(unittest.TestCase):
    def test_health_discloses_disabled_external_actions(self):
        report = health_payload()
        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["external_writes"])
        self.assertFalse(report["supabase_writes"])
        self.assertFalse(report["telegram_publish"])
        self.assertFalse(report["bet_execution"])

    def test_1x2_preview_is_normalized_and_duplicate_fixtures_rejected(self):
        payload = {"fixtures": [{"fixture_id": "f1", "home": "Home", "away": "Away",
                                "home_expected_goals": 1.5, "away_expected_goals": 1.1}]}
        report = preview_1x2(payload)
        probabilities = report["fixtures"][0]["probabilities"]
        self.assertEqual(report["count"], 1)
        self.assertAlmostEqual(sum(probabilities.values()), 1.0, places=5)
        with self.assertRaises(ValueError):
            preview_1x2({"fixtures": payload["fixtures"] * 2})

    def test_coupon_and_coverage_preview(self):
        candidates = [
            {"fixture_id": "f1", "market": "1x2", "selection": "home", "probability": .7,
             "decimal_odds": 1.8, "edge": .05, "binary": True},
        ]
        report = preview_coupon({"candidates": candidates, "config": {"coupon_min": 1, "coupon_max": 2}})
        self.assertTrue(report["generated"])
        coverage = preview_coverage({"fixtures": [{"fixture_id": "f1", "home": "H", "away": "A"}],
                                    "odds_fixture_ids": ["f1"], "market_fixture_ids": ["f1"]})
        self.assertEqual(coverage["fixtures_total"], 1)
        self.assertEqual(coverage["fixtures"][0]["status"], "no_candidates")

    def test_config_unknown_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            preview_coupon({"candidates": [], "config": {"unreviewed_setting": True}})

    def test_http_api_local_and_bearer_guard(self):
        server = HTTPServer(("127.0.0.1", 0), make_handler("local-secret"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", "/health")
            response = conn.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
            conn.request("GET", "/health", headers={"Authorization": "Bearer local-secret"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertFalse(json.loads(response.read())["telegram_publish"])
            payload = {"fixtures": [{"fixture_id": "f2", "home": "H", "away": "A",
                                    "home_expected_goals": 1.3, "away_expected_goals": 1.0}]}
            conn.request("POST", "/api/preview/1x2", json.dumps(payload),
                        headers={"Authorization": "Bearer local-secret", "Content-Type": "application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["count"], 1)
            conn.request("POST", "/api/preview/1x2", "not-json",
                        headers={"Authorization": "Bearer local-secret", "Content-Type": "application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_remote_binding_requires_token(self):
        with self.assertRaises(ValueError):
            run_server("0.0.0.0", 8000)


if __name__ == "__main__":
    unittest.main()
