"""Local-only HTTP facade for migrated preview services.

This module intentionally replaces the source database-backed API with a safe
preview surface while target persistence/schema parity is still under review.
It uses only the standard library and never performs external writes.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from math import isfinite
from typing import Any, Mapping

from .poisson import poisson_1x2
from .models import Outcome
from .risk_selection import RiskConfig, select_coupon_preview
from .coverage_audit import audit_pipeline_coverage

MAX_BODY_BYTES = 1_000_000
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def health_payload() -> dict[str, Any]:
    return {"status": "ok", "mode": "local-preview", "external_writes": False,
            "supabase_writes": False, "telegram_publish": False, "bet_execution": False}


def preview_1x2(payload: Mapping[str, Any]) -> dict[str, Any]:
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    output = []
    seen = set()
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, Mapping):
            raise ValueError(f"fixture {index} must be an object")
        match_id = str(fixture.get("fixture_id") or fixture.get("match_id") or "").strip()
        home, away = str(fixture.get("home") or "").strip(), str(fixture.get("away") or "").strip()
        if not match_id or not home or not away:
            raise ValueError(f"fixture {index} requires fixture_id, home and away")
        if match_id in seen:
            raise ValueError(f"duplicate fixture_id: {match_id}")
        seen.add(match_id)
        try:
            home_xg, away_xg = float(fixture["home_expected_goals"]), float(fixture["away_expected_goals"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"fixture {match_id} requires numeric expected goals") from None
        if not isfinite(home_xg) or not isfinite(away_xg):
            raise ValueError(f"fixture {match_id} expected goals must be finite")
        probabilities = poisson_1x2(home_xg, away_xg)
        output.append({"fixture_id": match_id, "home": home, "away": away,
                       "probabilities": {outcome.value: round(probabilities[outcome], 6) for outcome in Outcome}})
    return {"fixtures": output, "count": len(output), "mode": "preview"}


def preview_coupon(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    config_data = payload.get("config") or {}
    if not isinstance(config_data, Mapping):
        raise ValueError("config must be an object")
    allowed_fields = set(RiskConfig.__dataclass_fields__)
    unknown = set(config_data) - allowed_fields
    if unknown:
        raise ValueError(f"unknown risk config fields: {', '.join(sorted(unknown))}")
    for key in ("allowed_markets", "excluded_markets"):
        if key in config_data:
            if not isinstance(config_data[key], list):
                raise ValueError(f"{key} must be a list")
            config_data = dict(config_data)
            config_data[key] = frozenset(config_data[key])
    config = RiskConfig(**config_data)
    return select_coupon_preview(candidates, config)


def preview_coverage(payload: Mapping[str, Any]) -> dict[str, Any]:
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    return audit_pipeline_coverage(
        fixtures,
        odds_fixture_ids=payload.get("odds_fixture_ids", []),
        market_fixture_ids=payload.get("market_fixture_ids", []),
        candidate_fixture_ids=payload.get("candidate_fixture_ids", []),
        selected_fixture_ids=payload.get("selected_fixture_ids", []),
        exclusion_reasons=payload.get("exclusion_reasons", {}),
    )


def make_handler(api_token: str | None = None):
    class PreviewHandler(BaseHTTPRequestHandler):
        token = api_token

        def _authorized(self) -> bool:
            if not self.token:
                return True
            return self.headers.get("Authorization", "") == f"Bearer {self.token"

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"})
            if self.path != "/health":
                return self._send(404, {"error": "not found"})
            self._send(200, health_payload())

        def do_POST(self):
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"})
            if self.path not in {"/api/preview/1x2", "/api/preview/coupon", "/api/audit/coverage"}:
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "invalid content length"})
            if length < 0:
                return self._send(400, {"error": "invalid content length"})
            if length > MAX_BODY_BYTES:
                return self._send(413, {"error": "request body too large"})
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, Mapping):
                    raise ValueError("request body must be an object")
                if self.path == "/api/preview/1x2":
                    result = preview_1x2(payload)
                elif self.path == "/api/preview/coupon":
                    result = preview_coupon(payload)
                else:
                    result = preview_coverage(payload)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                return self._send(400, {"error": str(exc)})
            self._send(200, result)

        def log_message(self, format, *args):
            return  # Avoid logging request payloads or bearer credentials.

    return PreviewHandler


def run_server(host: str = "127.0.0.1", port: int = 8000, api_token: str | None = None) -> None:
    """Run local preview API; non-loopback hosts require an explicit token."""
    if host not in LOOPBACK_HOSTS and not api_token:
        raise ValueError("non-loopback binding requires api_token")
    server = HTTPServer((host, port), make_handler(api_token))
    try:
        print(f"Offline preview API listening on http://{host}:{port}")
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Run the offline football preview API (local only)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", default=os.getenv("PREVIEW_API_TOKEN"))
    args = parser.parse_args()
    run_server(args.host, args.port, args.token)
