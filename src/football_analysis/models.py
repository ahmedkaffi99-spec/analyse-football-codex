"""Validated domain types. No I/O, APIs, database, or bookmaker integration."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Mapping

class Outcome(str, Enum):
    HOME = "H"
    DRAW = "D"
    AWAY = "A"

def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")

@dataclass(frozen=True, slots=True)
class MatchResult:
    match_id: str
    kickoff: datetime
    home_goals: int
    away_goals: int

    def __post_init__(self) -> None:
        if not self.match_id.strip(): raise ValueError("match_id must not be empty")
        _require_aware(self.kickoff, "kickoff")
        for name, score in (("home_goals", self.home_goals), ("away_goals", self.away_goals)):
            if isinstance(score, bool) or not isinstance(score, int) or score < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def outcome(self) -> Outcome:
        if self.home_goals > self.away_goals: return Outcome.HOME
        if self.home_goals < self.away_goals: return Outcome.AWAY
        return Outcome.DRAW

@dataclass(frozen=True, slots=True)
class Prediction:
    match_id: str
    generated_at: datetime
    probabilities: Mapping[Outcome, float]

    def __post_init__(self) -> None:
        if not self.match_id.strip(): raise ValueError("match_id must not be empty")
        _require_aware(self.generated_at, "generated_at")
        normalized = {Outcome(key): float(value) for key, value in self.probabilities.items()}
        if set(normalized) != set(Outcome): raise ValueError("probabilities must contain exactly H, D, and A")
        if any(not isfinite(p) or p < 0.0 or p > 1.0 for p in normalized.values()):
            raise ValueError("each probability must be finite and between 0 and 1")
        if abs(sum(normalized.values()) - 1.0) > 1e-6: raise ValueError("probabilities must sum to 1 within 1e-6")
        object.__setattr__(self, "probabilities", normalized)

@dataclass(frozen=True, slots=True)
class OddsSnapshot:
    match_id: str
    observed_at: datetime
    decimal_odds: Mapping[Outcome, float]

    def __post_init__(self) -> None:
        if not self.match_id.strip(): raise ValueError("match_id must not be empty")
        _require_aware(self.observed_at, "observed_at")
        normalized = {Outcome(key): float(value) for key, value in self.decimal_odds.items()}
        if set(normalized) != set(Outcome): raise ValueError("decimal_odds must contain exactly H, D, and A")
        if any(not isfinite(odd) or odd <= 1.0 for odd in normalized.values()):
            raise ValueError("decimal odds must be finite and greater than 1.0")
        object.__setattr__(self, "decimal_odds", normalized)
