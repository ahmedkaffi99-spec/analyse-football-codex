"""No-vig multi-book consensus calculation migrated from the read-only reference.

This module is pure/offline: it consumes already collected odds and never fetches
or publishes data. Ambiguous/invalid markets are discarded instead of producing
a misleading consensus.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

BOOK_WEIGHTS = {"Pinnacle": 3.0}
EXCLUDED_BOOKMAKERS = {"Dafabet"}
MIN_BOOKMAKERS = 3


def no_vig_probabilities(market: Mapping[str, Any] | None) -> dict[str, float] | None:
    """Normalize a complete market's decimal odds to probabilities.

    Invalid odds, duplicate outcome labels, and markets with fewer than two
    outcomes are rejected. Supports the target's `odds` field and the source's
    `cote` field for compatibility.
    """
    if not isinstance(market, Mapping):
        return None
    selections = market.get("selections", [])
    if not isinstance(selections, Sequence) or isinstance(selections, (str, bytes)):
        return None
    odds: dict[str, float] = {}
    for item in selections:
        if not isinstance(item, Mapping):
            return None
        selection = item.get("selection")
        raw_odds = item.get("odds", item.get("cote"))
        if not isinstance(selection, str) or not selection.strip():
            return None
        if isinstance(raw_odds, bool) or not isinstance(raw_odds, (int, float)):
            return None
        value = float(raw_odds)
        if not math.isfinite(value) or value <= 1.0:
            return None
        label = selection.strip()
        if label in odds:
            return None
        odds[label] = value
    if len(odds) < 2:
        return None
    total = sum(1.0 / value for value in odds.values())
    if not math.isfinite(total) or total <= 0:
        return None
    return {label: (1.0 / value) / total for label, value in odds.items()}


def consensus(
    book_markets: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    reference_book: str = "1xBet",
    min_books: int = MIN_BOOKMAKERS,
) -> dict[tuple[Any, Any, str], dict[str, Any]]:
    """Return weighted no-vig consensus only for outcomes shared by enough books.

    Consensus requires unique bookmaker observations per market key. A repeated
    market from one provider is skipped rather than silently replacing data.
    Pinnacle receives its configured weight; other included books have weight 1.
    """
    if isinstance(min_books, bool) or not isinstance(min_books, int) or min_books < 2:
        raise ValueError("min_books must be an integer >= 2")
    if not isinstance(reference_book, str) or not reference_book.strip():
        raise ValueError("reference_book must be a non-empty string")
    if not isinstance(book_markets, Mapping):
        return {}

    grouped: dict[tuple[Any, Any], dict[str, dict[str, float]]] = {}
    for bookmaker, markets in book_markets.items():
        if not isinstance(bookmaker, str) or not bookmaker.strip() or bookmaker in EXCLUDED_BOOKMAKERS:
            continue
        if not isinstance(markets, Sequence) or isinstance(markets, (str, bytes)):
            continue
        seen_market_keys: set[tuple[Any, Any]] = set()
        for market in markets:
            if not isinstance(market, Mapping):
                continue
            market_name = market.get("market") or market.get("marche")
            if not isinstance(market_name, str) or not market_name.strip():
                continue
            key = (market_name.strip(), market.get("handicap"))
            if key in seen_market_keys:
                continue
            probabilities = no_vig_probabilities(market)
            if probabilities is None:
                continue
            seen_market_keys.add(key)
            grouped.setdefault(key, {})[bookmaker] = probabilities

    output: dict[tuple[Any, Any, str], dict[str, Any]] = {}
    for key, by_book in grouped.items():
        if len(by_book) < min_books:
            continue
        common = set.intersection(*(set(probabilities) for probabilities in by_book.values()))
        for selection in sorted(common):
            weights = {book: BOOK_WEIGHTS.get(book, 1.0) for book in by_book}
            total_weight = sum(weights.values())
            average = sum(by_book[book][selection] * weights[book] for book in by_book) / total_weight
            reference_probability = by_book.get(reference_book, {}).get(selection)
            output[(key[0], key[1], selection)] = {
                "probability": average,
                "bookmakers": len(by_book),
                "reference_probability": reference_probability,
                "difference_points": None if reference_probability is None else round((average - reference_probability) * 100, 2),
            }
    return output
