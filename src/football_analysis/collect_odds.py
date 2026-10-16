"""API-Football odds collector, restricted to 1xBet only.

Fetches all pages of odds returned by the provider for a date and stores only
1xBet quotes in the dedicated football_odds table. No prediction endpoint is used.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .markets import flatten_api_football_odds
from .api_football_client import api_get as _resilient_api_get

API_BASE = "https://v3.football.api-sports.io"
TARGET_BOOKMAKER = "1xbet"


def is_target_bookmaker(name: Any) -> bool:
    """Match the exact 1xBet name, ignoring spaces and case."""
    normalized = "".join(char for char in str(name or "").casefold() if char.isalnum())
    return normalized == TARGET_BOOKMAKER


def only_target_bookmaker(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep fixtures that offer 1xBet and strip every other bookmaker."""
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        bookmakers = [
            bookmaker for bookmaker in (row.get("bookmakers") or [])
            if is_target_bookmaker(bookmaker.get("name"))
        ]
        if bookmakers:
            filtered_rows.append({**row, "bookmakers": bookmakers})
    return filtered_rows


def api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    """Use the shared API-Football client with bounded retries and quota capture."""
    return _resilient_api_get(path, params)


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
    """Collect 1xBet odds from all available pages and persist snapshots."""
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

    target_rows = only_target_bookmaker(all_rows)
    quotes = flatten_api_football_odds(target_rows, captured_at=captured_at)
    payload = [{
        "provider": "api-football",
        "fixture_id": quote.fixture_id,
        "bookmaker_id": quote.bookmaker_id or "unknown",
        "bookmaker_name": quote.bookmaker_name,
        "market_id": quote.market_id or "unknown",
        "market_name": quote.market_name,
        "selection": quote.selection,
        "odds": quote.odds,
        "point": quote.point if quote.point is not None else -999,
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
        "fixtures_with_odds": len({row.get("fixture", {}).get("id") for row in target_rows if row.get("fixture", {}).get("id") is not None}),
        "quotes_seen": len(quotes),
        "quotes_sent_to_supabase": inserted,
        "bookmaker": "1xBet",
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
