"""Specialist market agents using market-specific historical statistics.

Poisson is a transparent baseline for count markets, not a trained model.
Missing samples stay unsupported; no fallback statistics are fabricated.
"""
from __future__ import annotations
import math
from typing import Any

COUNT_MARKETS = {
    "corners": ("corners_mean",),
    "shots": ("shots_mean",),
    "shots_on_target": ("shots_on_target_mean",),
    "yellow_cards": ("yellow_cards_mean",),
    "red_cards": ("red_cards_mean",),
    "fouls": ("fouls_mean",),
    "offsides": ("offsides_mean",),
}

def poisson_pmf(rate: float, count: int) -> float:
    if rate < 0 or count < 0:
        return 0.0
    return math.exp(-rate) * rate**count / math.factorial(count) if rate else float(count == 0)

def count_market_probability(rate: float, selection: str, line: float) -> float | None:
    """Probability of an integer count being over/under a line."""
    if rate < 0 or rate > 100 or not math.isfinite(rate):
        return None
    label = selection.casefold()
    if "over" not in label and "under" not in label:
        return None
    # Asian integer lines can push; skip until push-aware EV is implemented.
    if abs(line - round(line)) < 1e-9:
        return None
    cdf = sum(poisson_pmf(rate, k) for k in range(max(0, math.floor(line)) + 1))
    return max(0.0, min(1.0, 1.0 - cdf if "over" in label else cdf))

def team_metric_rate(market: str, home_stats: dict[str, Any], away_stats: dict[str, Any]) -> float | None:
    """Combine each team's own recent metric mean; require both samples."""
    fields = COUNT_MARKETS.get(market)
    if not fields:
        return None
    key = fields[0]
    h, a = home_stats.get(key), away_stats.get(key)
    hn, an = home_stats.get(key.replace("_mean", "_n"), 0), away_stats.get(key.replace("_mean", "_n"), 0)
    if not isinstance(h, (int, float)) or not isinstance(a, (int, float)) or hn < 3 or an < 3:
        return None
    return max(0.0, float(h) + float(a))

def win_to_nil_probability(home_xg: float, away_xg: float, selection: str) -> float:
    """Independent Poisson score-grid probability that a side wins without conceding."""
    p_home, p_away = 0.0, 0.0
    for h in range(16):
        ph = poisson_pmf(home_xg, h)
        for a in range(16):
            joint = ph * poisson_pmf(away_xg, a)
            if h > a and a == 0:
                p_home += joint
            if a > h and h == 0:
                p_away += joint
    label = selection.casefold()
    if any(x in label for x in ("home", "team 1", "1")):
        return p_home
    if any(x in label for x in ("away", "team 2", "2")):
        return p_away
    return 0.0

def dnb_probabilities(model_1x2: dict[str, float]) -> dict[str, float]:
    """DNB conditional win probability; draw is refunded and excluded."""
    decisive = model_1x2.get("1", 0.0) + model_1x2.get("2", 0.0)
    if decisive <= 0:
        return {"1": 0.0, "2": 0.0}
    return {"1": model_1x2.get("1", 0.0) / decisive,
            "2": model_1x2.get("2", 0.0) / decisive}
