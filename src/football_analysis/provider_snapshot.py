"""Manual API-Football snapshot collection to a local JSON artifact.

This module reads API-Football only. It has no Supabase or Telegram client.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .api_football_client import api_get
from .collect_odds import only_target_bookmaker
from .markets import flatten_api_football_odds


def collect_snapshot(date: str, max_pages: int = 50) -> dict:
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    captured_at = datetime.now(timezone.utc).isoformat()
    rows = []
    page = 1
    total = 1
    while page <= total and page <= max_pages:
        body = api_get("odds", {"date": date, "page": page})
        page_rows = body.get("response") or []
        rows.extend(page_rows)
        try:
            total = max(1, int((body.get("paging") or {}).get("total", page)))
        except (TypeError, ValueError):
            total = page
        if not page_rows:
            break
        page += 1
    filtered = only_target_bookmaker(rows)
    quotes = flatten_api_football_odds(filtered, captured_at=captured_at)
    return {
        "provider": "api-football",
        "bookmaker_filter": "1xBet",
        "date": date,
        "captured_at": captured_at,
        "pages_fetched": min(page - 1, max_pages),
        "provider_pages_reported": total,
        "truncated": total > max_pages,
        "fixtures_count": len({str((row.get("fixture") or {}).get("id")) for row in filtered}),
        "quotes": [
            {
                "fixture_id": q.fixture_id,
                "bookmaker_id": q.bookmaker_id,
                "bookmaker_name": q.bookmaker_name,
                "market_id": q.market_id,
                "market_name": q.market_name,
                "selection": q.selection,
                "decimal_odds": q.odds,
                "line": q.point,
                "captured_at": q.captured_at,
            }
            for q in quotes
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=os.environ.get("ODDS_DATE", datetime.now(timezone.utc).date().isoformat()))
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("artifacts/api_football_odds.json"))
    args = parser.parse_args()
    report = collect_snapshot(args.date, args.max_pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "quotes"}, ensure_ascii=False))
    print(f"Snapshot written locally: {args.output}")
    print("No database writes, Telegram messages, or coupon generation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
