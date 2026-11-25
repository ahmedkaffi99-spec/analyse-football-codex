"""Bayesian/additive mean shrinkage adapted from the reference count-market model.

The prior contributes k pseudo-observations. Missing sample metadata leaves a
measured mean unchanged (no invented confidence); invalid inputs return None.
This is an offline numerical helper.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

DEFAULT_K = 5.0
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
