"""Odds, model edge and expected-value calculations for 1xBet market families."""
from __future__ import annotations

import math
import re
from typing import Any

from .all_markets import extract_market_predictions


def _poisson_pmf(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _total_goals_probability(home_xg: float, away_xg: float, selection: str, line: float) -> float | None:
    """Approximate O/U probability from independent Poisson goal counts."""
    if not (0 <= home_xg <= 8 and 0 <= away_xg <= 8):
        return None
    total = 0.0
    max_goals = 12
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            goals = h + a
            if "over" in selection.casefold() and goals > line:
                total += _poisson_pmf(home_xg, h) * _poisson_pmf(away_xg, a)
            elif "under" in selection.casefold() and goals < line:
                total += _poisson_pmf(home_xg, h) * _poisson_pmf(away_xg, a)
    # Integer Asian lines require push probability handling; don't score them as a simple win.
    if abs(line - round(line)) < 1e-9:
        return None
    return min(1.0, max(0.0, total))


def _model_probability(market: str, selection: str, line: Any,
                       model_1x2: dict[str, float], home_xg: float,
                       away_xg: float) -> float | None:
    label = selection.strip().casefold().replace(" ", "")
    if market == "1x2":
        aliases = {"home": "1", "1": "1", "draw": "x", "x": "x",
                   "away": "2", "2": "2", "team1": "1", "team2": "2"}
        key = aliases.get(label)
        return model_1x2.get(key) if key else None
    if market == "double_chance":
        if any(x in label for x in ("home/draw", "1x", "1/x", "homeordraw")):
            return model_1x2.get("1", 0) + model_1x2.get("x", 0)
        if any(x in label for x in ("draw/away", "x2", "x/2", "draworaway")):
            return model_1x2.get("x", 0) + model_1x2.get("2", 0)
        if any(x in label for x in ("home/away", "12", "1/2", "homeoraway")):
            return model_1x2.get("1", 0) + model_1x2.get("2", 0)
    if market == "btts":
        p_home_scores = 1 - math.exp(-home_xg)
        p_away_scores = 1 - math.exp(-away_xg)
        yes = p_home_scores * p_away_scores
        if label in {"yes", "y", "bothteams to scoreyes"}:
            return yes
        if label in {"no", "n"}:
            return 1 - yes
    if market == "total_goals" and line is not None:
        try:
            return _total_goals_probability(home_xg, away_xg, selection, float(line))
        except (TypeError, ValueError):
            return None
    # No independent prediction model yet for corners, cards, shots or handicap.
    return None


def score_market_predictions(odds_row: dict[str, Any], *,
                             model_1x2: dict[str, float],
                             home_xg: float, away_xg: float) -> list[dict[str, Any]]:
    """Score 1xBet market outcomes with model probability, edge and EV where supported.

    Edge is model probability minus de-vigged market probability. EV uses the
    offered decimal odds: P(model) * odds - 1. Unsupported families retain their
    normalized market probability but deliberately have no fabricated edge.
    """
    scored = []
    for market in extract_market_predictions(odds_row):
        family = market["market"]
        probabilities = market.get("probabilities") or {}
        selection = market["selection"]
        p_market = probabilities.get(selection, market.get("probability"))
        p_model = _model_probability(family, selection, market.get("line"),
                                    model_1x2, home_xg, away_xg)
        item = {**market, "market_probability": round(float(p_market), 6),
                "model_probability": None, "edge": None, "edge_pct_points": None,
                "expected_value": None, "value_status": "odds_only_no_model"}
        if p_model is not None and 0 <= p_model <= 1:
            edge = p_model - float(p_market)
            ev = p_model * float(market["odds"]) - 1
            item.update(model_probability=round(p_model, 6), edge=round(edge, 6),
                        edge_pct_points=round(edge * 100, 2),
                        expected_value=round(ev, 6),
                        value_status="positive_ev" if ev > 0 else "negative_ev")
        scored.append(item)
    return sorted(scored, key=lambda item: (
        item["expected_value"] is None,
        -(item["expected_value"] if item["expected_value"] is not None else -99),
        item["market"], str(item.get("line") or "")))
