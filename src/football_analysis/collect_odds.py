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


def collect(date: str, *, max_pages: int = 50) -> dict[str, Any]:
    """Fetch 1xBet quotes from API-Football; return data without external writes."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
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
    return {
        "date": date,
        "provider": "api-football",
        "bookmaker": "1xBet",
        "captured_at": captured_at,
        "pages_fetched": min(page - 1, max_pages),
        "provider_pages_reported": total_pages,
        "fixtures_with_odds": len({
            row.get("fixture", {}).get("id")
            for row in target_rows
            if row.get("fixture", {}).get("id") is not None
        }),
        "quotes_seen": len(quotes),
        "truncated_at_max_pages": total_pages > max_pages,
        "quotes": [
            {
                "fixture_id": q.fixture_id,
                "bookmaker_id": q.bookmaker_id,
                "bookmaker_name": q.bookmaker_name,
                "market_id": q.market_id,
                "market_name": q.market_name,
                "selection": q.selection,
                "odds": q.odds,
                "point": q.point,
                "captured_at": q.captured_at,
            }
            for q in quotes
        ],
    }


def main() -> int:
    date = os.environ.get("ODDS_DATE", datetime.now(timezone.utc).date().isoformat())
    output = os.environ.get("ODDS_OUTPUT_PATH", f"artifacts/odds_snapshots_{date}.json")
    try:
        report = collect(date)
        from pathlib import Path
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "quotes"}, ensure_ascii=False))
        print(f"Local artifact saved: {output_path}")
        print("No Supabase write or Telegram publication performed.")
        return 0
    except Exception as exc:
        print(f"ODDS_COLLECTION_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
