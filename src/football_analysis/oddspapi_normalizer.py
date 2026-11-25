"""Offline OddsPapi-to-target market normalizer migrated from the reference.

No API calls are made here. The caller supplies raw payloads and a market
catalogue; diagnostics make bookmaker/market/outcome loss visible.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any


def _market_catalog_entry(catalog: Mapping[str, Any], market_id: Any) -> Mapping[str, Any]:
    entry = catalog.get(str(market_id), {})
    return entry if isinstance(entry, Mapping) else {}


def _valid_decimal_price(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(price) or price <= 1.0:
        return None
    return price


def normalize_oddspapi_payload(
    payload: Any,
    market_catalog: Mapping[str, Any] | None,
    bookmaker: str = "1xbet",
) -> dict[str, Any]:
    """Normalize raw event bookmakerOdds into target market/selection/odds records.

    Input supports one event object or a list of event objects. Market IDs and
    outcome IDs are resolved from the supplied catalogue. Suspended/missing/
    invalid prices are counted and discarded. Market names and outcome labels
    remain raw provider text, preserving the source's all-market behaviour.
    """
    events = payload if isinstance(payload, list) else [payload] if isinstance(payload, Mapping) else []
    catalog = market_catalog if isinstance(market_catalog, Mapping) else {}
    requested = str(bookmaker or "").strip().casefold()
    diagnostics = {"events_count": len(events), "bookmaker_found": False,
                  "markets_total": 0, "markets_valid": 0,
                  "outcomes_total": 0, "outcomes_valid": 0, "invalid_prices": 0}
    output: list[dict[str, Any]] = []
    if not events:
        return {"status": "no_events", "markets": output, "diagnostics": diagnostics}

    for event in events:
        if not isinstance(event, Mapping):
            continue
        book_map = event.get("bookmakerOdds")
        if not isinstance(book_map, Mapping):
            continue
        book_key = next((key for key in book_map if str(key).strip().casefold() == requested), None)
        if book_key is None:
            continue
        diagnostics["bookmaker_found"] = True
        bookmaker_data = book_map.get(book_key)
        if not isinstance(bookmaker_data, Mapping):
            continue
        raw_markets = bookmaker_data.get("markets", {})
        if not isinstance(raw_markets, Mapping):
            continue
        for market_id, market_data in raw_markets.items():
            diagnostics["markets_total"] += 1
            if not isinstance(market_data, Mapping):
                continue
            entry = _market_catalog_entry(catalog, market_id)
            outcomes_names = entry.get("outcomes", {})
            if not isinstance(outcomes_names, Mapping):
                outcomes_names = {}
            raw_outcomes = market_data.get("outcomes", {})
            if not isinstance(raw_outcomes, Mapping):
                continue
            selections = []
            for outcome_id, outcome_data in raw_outcomes.items():
                diagnostics["outcomes_total"] += 1
                if not isinstance(outcome_data, Mapping):
                    diagnostics["invalid_prices"] += 1
                    continue
                players = outcome_data.get("players", {})
                player_zero = players.get("0", {}) if isinstance(players, Mapping) else {}
                price = _valid_decimal_price(player_zero.get("price") if isinstance(player_zero, Mapping) else None)
                if price is None:
                    diagnostics["invalid_prices"] += 1
                    continue
                label = outcomes_names.get(str(outcome_id)) if isinstance(outcomes_names, Mapping) else None
                if not label:
                    label = f"Option {outcome_id}"
                selections.append({"selection": str(label), "odds": price})
                diagnostics["outcomes_valid"] += 1
            if selections:
                output.append({"fixture_id": str(event.get("fixtureId") or event.get("fixture_id") or "") or None,
                              "bookmaker": str(book_key), "market_id": str(market_id),
                              "market": entry.get("name") or f"Market {market_id}",
                              "market_type": entry.get("type"),
                              "handicap": entry.get("handicap"),
                              "period": entry.get("period"),
                              "selections": selections})
                diagnostics["markets_valid"] += 1

    if output:
        status = "ok"
    elif diagnostics["bookmaker_found"] and diagnostics["markets_total"]:
        status = "no_valid_odds"
    elif diagnostics["bookmaker_found"]:
        status = "no_markets"
    else:
        status = "no_bookmaker"
    return {"status": status, "markets": output, "diagnostics": diagnostics}
