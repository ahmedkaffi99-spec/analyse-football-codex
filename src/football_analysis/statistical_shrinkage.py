"""Bayesian/additive mean shrinkage adapted from the reference count-market model.

The prior contributes k pseudo-observations. Missing sample metadata leaves a
measured mean unchanged (no invented confidence); invalid inputs return None.
This is an offline numerical helper.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

DEFAULT_K = 5.0
HOME_ADVANTAGE_FACTORS = {
    "corners": 1.107, "shots": 1.101, "shots_on_target": 1.103,
    "fouls": 0.985, "yellow_cards": 0.934,
}
DEFAULT_PRIORS = {
    "goals": 1.335,
    "corners": 4.8,
    "yellow_cards": 2.1,
    "cards": 2.1,
    "fouls": 11.9,
    "shots": 12.7,
    "shots_on_target": 4.4,
    "offsides": 1.7,
}


def shrink_mean(value: Any, sample_n: Any, prior: Any, k: float = DEFAULT_K) -> float | None:
    """Return a shrinkage-adjusted mean using k pseudo-observations.

    With absent sample count, preserve the supplied mean without claiming a
    shrinkage estimate. k=0 explicitly disables shrinkage. Invalid/non-finite
    measurements, negative counts, or invalid priors are rejected.
    """
    if value is None:
        return None
    try:
        measured = float(value)
        strength = float(k)
    except (TypeError, ValueError):
        return None
    if not isfinite(measured) or not isfinite(strength) or strength < 0:
        return None
    if sample_n is None:
        return measured
    try:
        n = float(sample_n)
        baseline = float(prior)
    except (TypeError, ValueError):
        return None
    if not isfinite(n) or n < 0 or not isfinite(baseline):
        return None
    if strength == 0 or n == 0 and strength == 0:
        return measured
    return (measured * n + baseline * strength) / (n + strength)


def shrink_metric(metric: str, value: Any, sample_n: Any, k: float = DEFAULT_K) -> float | None:
    """Apply the registered prior for a count metric; unsupported metrics stay raw."""
    prior = DEFAULT_PRIORS.get(metric)
    if prior is None:
        if value is None:
            return None
        try:
            raw = float(value)
            return raw if isfinite(raw) else None
        except (TypeError, ValueError):
            return None
    return shrink_mean(value, sample_n, prior, k)


def apply_home_advantage(metric: str, home_mean: float, away_mean: float) -> tuple[float, float]:
    """Apply source-measured home/away multipliers to supported count metrics.

    The home factor and its complement (2-factor) are used so an equal pair of
    rates keeps its total mean unchanged. Unsupported metrics are returned raw.
    """
    factor = HOME_ADVANTAGE_FACTORS.get(metric)
    try:
        home, away = float(home_mean), float(away_mean)
    except (TypeError, ValueError):
        raise ValueError("home and away means must be numeric")
    if not isfinite(home) or not isfinite(away) or home < 0 or away < 0:
        raise ValueError("home and away means must be finite and non-negative")
    if factor is None:
        return home, away
    return max(0.15, home * factor), max(0.15, away * (2.0 - factor))
