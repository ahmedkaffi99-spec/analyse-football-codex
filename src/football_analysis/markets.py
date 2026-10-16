"""Market utilities for the independent football prediction engine.

This module is deliberately provider-agnostic and makes no network calls.
It normalizes bookmaker odds and preserves arbitrary API-Football market names.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial, isfinite
from typing import Any, Iterable


@dataclass(frozen=True)
class OddsQuote:
    fixture_id: str
    bookmaker_id: str | None
    bookmaker_name: str
    market_id: str | None
    market_name: str
    selection: str
    odds: float
    captured_at: str | None = None
    point: float | None = None


def implied_probability(odds: float) -> float:
    """Raw implied probability from finite decimal odds greater than 1."""
    try:
        value = float(odds)
    except (TypeError, ValueError) as exc:
        raise ValueError("Decimal odds must be a finite number greater than 1") from exc
    if not isfinite(value) or value <= 1:
        raise ValueError("Decimal odds must be a finite number greater than 1")
    return 1.0 / value


def normalize_implied_probabilities(odds_by_selection: dict[str, float]) -> dict[str, float]:
    """Remove the bookmaker overround by normalizing implied probabilities."""
    if not odds_by_selection:
        return {}
    raw = {key: implied_probability(value) for key, value in odds_by_selection.items()}
    total = sum(raw.values())
    if not isfinite(total) or total <= 0:
        raise ValueError("Odds do not produce a finite positive implied probability sum")
    return {key: value / total for key, value in raw.items()}


def poisson_distribution(expected_goals: float, max_goals: int = 10) -> list[float]:
    """Return a truncated Poisson score distribution normalized to sum to one."""
    try:
        rate = float(expected_goals)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected goals must be a finite non-negative number") from exc
    if not isfinite(rate) or rate < 0:
        raise ValueError("Expected goals must be a finite non-negative number")
    if isinstance(max_goals, bool) or not isinstance(max_goals, int) or max_goals < 1:
        raise ValueError("max_goals must be a positive integer")
    values = [exp(-rate) * rate**n / factorial(n) for n in range(max_goals + 1)]
    total = sum(values)
    return [p / total for p in values]


def poisson_market_probabilities(home_xg: float, away_xg: float, max_goals: int = 10) -> dict[str, Any]:
    """Derive common football markets from independent home/away Poisson goals.

    This is a baseline model only: expected-goal inputs must be estimated from
    historical data by a separate component and validated with chronological tests.
    """
    home = poisson_distribution(home_xg, max_goals)
    away = poisson_distribution(away_xg, max_goals)
    score = [[h * a for a in away] for h in home]
    p_home = p_draw = p_away = 0.0
    btts_yes = 0.0
    totals = [0.0] * (2 * max_goals + 1)
    correct_scores: dict[str, float] = {}
    for h, row in enumerate(score):
        for a, p in enumerate(row):
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
            if h > 0 and a > 0:
                btts_yes += p
            totals[h + a] += p
            correct_scores[f"{h}-{a}"] = p

    def over(line: float) -> float:
        return sum(p for goals, p in enumerate(totals) if goals > line)

    def under(line: float) -> float:
        return sum(p for goals, p in enumerate(totals) if goals < line)

    result: dict[str, Any] = {
        "1x2": {"home": p_home, "draw": p_draw, "away": p_away},
        "double_chance": {
            "1X": p_home + p_draw,
            "X2": p_draw + p_away,
            "12": p_home + p_away,
        },
        "btts": {"yes": btts_yes, "no": 1.0 - btts_yes},
        "totals": {
            str(line): {"over": over(line), "under": under(line)}
            for line in (0.5, 1.5, 2.5, 3.5, 4.5)
        },
        "expected_goals": {"home": float(home_xg), "away": float(away_xg)},
        "correct_scores": correct_scores,
    }
    return result


def flatten_api_football_odds(
    response_rows: Iterable[dict[str, Any]],
    captured_at: str | None = None,
) -> list[OddsQuote]:
    """Flatten API-Football /odds response rows without assuming a fixed market list."""
    quotes: list[OddsQuote] = []
    for row in response_rows:
        fixture = row.get("fixture") or {}
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue
        for bookmaker in row.get("bookmakers") or []:
            bookmaker_id = bookmaker.get("id")
            bookmaker_name = str(bookmaker.get("name") or "unknown")
            for bet in bookmaker.get("bets") or []:
                market_id = bet.get("id")
                market_name = str(bet.get("name") or "unknown")
                for value in bet.get("values") or []:
                    raw_odds = value.get("odd")
                    try:
                        odd = float(str(raw_odds).strip())
                    except (TypeError, ValueError):
                        continue
                    if not isfinite(odd) or odd <= 1:
                        continue
                    point = value.get("handicap")
                    try:
                        point_value = float(point) if point is not None else None
                    except (TypeError, ValueError):
                        point_value = None
                    if point_value is not None and not isfinite(point_value):
                        point_value = None
                    quotes.append(OddsQuote(
                        fixture_id=str(fixture_id),
                        bookmaker_id=str(bookmaker_id) if bookmaker_id is not None else None,
                        bookmaker_name=bookmaker_name,
                        market_id=str(market_id) if market_id is not None else None,
                        market_name=market_name,
                        selection=str(value.get("value") or "unknown"),
                        odds=odd,
                        captured_at=captured_at,
                        point=point_value,
                    ))
    return quotes
