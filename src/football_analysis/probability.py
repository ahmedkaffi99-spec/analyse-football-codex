"""Small, dependency-free probability helpers."""
from __future__ import annotations
from math import isfinite
from typing import Mapping
from .models import Outcome

def normalize_probabilities(values: Mapping[Outcome, float]) -> dict[Outcome, float]:
    weights = {Outcome(key): float(value) for key, value in values.items()}
    if set(weights) != set(Outcome): raise ValueError("weights must contain exactly H, D, and A")
    if any(not isfinite(v) or v < 0.0 for v in weights.values()): raise ValueError("weights must be finite and non-negative")
    total = sum(weights.values())
    if total <= 0.0: raise ValueError("at least one weight must be positive")
    return {outcome: weight / total for outcome, weight in weights.items()}

def implied_probabilities(decimal_odds: Mapping[Outcome, float], *, remove_margin: bool = True) -> dict[Outcome, float]:
    odds = {Outcome(key): float(value) for key, value in decimal_odds.items()}
    if set(odds) != set(Outcome): raise ValueError("decimal_odds must contain exactly H, D, and A")
    if any(not isfinite(odd) or odd <= 1.0 for odd in odds.values()): raise ValueError("decimal odds must be finite and greater than 1.0")
    raw = {outcome: 1.0 / odd for outcome, odd in odds.items()}
    return normalize_probabilities(raw) if remove_margin else raw
