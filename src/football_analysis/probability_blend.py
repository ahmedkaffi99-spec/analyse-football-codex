"""Explicit model/market probability blend with the reference default weight.

The blend is a research utility. It does not select bets, send messages, or place
orders. Inputs must be available from a pre-match snapshot and model.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

DEFAULT_MARKET_WEIGHT = 0.65


def validate_market_weight(weight: Any) -> float:
    try:
        value = float(weight)
    except (TypeError, ValueError) as exc:
        raise ValueError("market_weight must be a finite number between 0 and 1") from exc
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("market_weight must be a finite number between 0 and 1")
    return value


def blend_probability(model_probability: Any, market_probability: Any, *, weight: float = DEFAULT_MARKET_WEIGHT) -> float:
    """Return (1 - weight) * model + weight * market.

    Finite non-negative values are accepted. Values above one are deliberately
    not clamped because some overlapping market definitions in the reference
    pipeline can produce non-unit market aggregates; callers must retain the
    market semantics and avoid treating such aggregates as normalized outcomes.
    """
    weight = validate_market_weight(weight)
    try:
        model = float(model_probability)
        market = float(market_probability)
    except (TypeError, ValueError) as exc:
        raise ValueError("model and market probabilities must be finite non-negative numbers") from exc
    if not isfinite(model) or not isfinite(market) or model < 0.0 or market < 0.0:
        raise ValueError("model and market probabilities must be finite non-negative numbers")
    return (1.0 - weight) * model + weight * market
