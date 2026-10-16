"""API-Football odds collector.

Fetches all odds markets returned by the provider for a date and stores every
quote in the dedicated football_odds table. No prediction endpoint is used.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .markets import flatten_api_football_odds

API_BASE = "https://v3.football.api-sports.io"


def api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing API_FOOTBALL_KEY")
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"x-apisports-key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API-Football request failed for {path}: {exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Unexpected API-Football response")
    if body.get("errors"):
        raise RuntimeError(f"API-Football returned errors for {path}: {body['errors']}")
    return body


def supabase_request(table: str, payload: Any, params: str = "", prefer: str = "return=minimal") -> Any:
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not base or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    url = f"{base}/rest/v1/{table}" + (f"?{params}" if params else "")
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Supabase write to {table} failed: {exc}") from exc


def collect(date: str, *, max_pages: int = 50) -> dict[str, Any]:
    """Collect all pages of odds returned for the date and persist snapshots."""
    captured_at = datetime.now(timezone.utc).isoformat()
    all_rows: list[dict[str, Any]] = []
    page = 1
    total_pages = 1
    while page <= total_pages and page <= max_pages:
        body = api_get("odds", {"date": date, "page": str(page)})
        rows = body.get("response") or []
        all_rows.extend(rows)
        paging = body.get("paging") or {}
        try:
            total_pages = max(1, int(paging.get("total", page)))
        except (TypeError, ValueError):
            total_pages = page
        if not rows:
            break
        page += 1

    quotes = flatten_api_football_odds(all_rows, captured_at=captured_at)
    payload = [{
        "provider": "api-football",
        "fixture_id": quote.fixture_id,
        "bookmaker_id": quote.bookmaker_id,
        "bookmaker_name": quote.bookmaker_name,
        "market_id": quote.market_id,
        "market_name": quote.market_name,
        "selection": quote.selection,
        "odds": quote.odds,
        "point": quote.point,
        "captured_at": quote.captured_at,
        "raw_payload": {
            "fixture_id": quote.fixture_id,
            "bookmaker_id": quote.bookmaker_id,
            "market_id": quote.market_id,
            "market_name": quote.market_name,
            "selection": quote.selection,
            "odds": quote.odds,
            "point": quote.point,
        },
    } for quote in quotes]

    inserted = 0
    # Small batches keep requests manageable. The unique key includes capture time,
    # preserving price history rather than overwriting earlier snapshots.
    for start in range(0, len(payload), 100):
        batch = payload[start:start + 100]
        supabase_request(
            "football_odds",
            batch,
            params="on_conflict=provider,fixture_id,bookmaker_id,market_id,selection,point,captured_at",
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        inserted += len(batch)
    return {
        "date": date,
        "pages_fetched": min(page - 1, max_pages),
        "fixtures_with_odds": len({row.get("fixture", {}).get("id") for row in all_rows if row.get("fixture", {}).get("id") is not None}),
        "quotes_seen": len(quotes),
        "quotes_sent_to_supabase": inserted,
        "captured_at": captured_at,
        "truncated_at_max_pages": total_pages > max_pages,
    }


def main() -> int:
    date = os.environ.get("ODDS_DATE", datetime.now(timezone.utc).date().isoformat())
    try:
        print(json.dumps(collect(date), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ODDS_COLLECTION_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
