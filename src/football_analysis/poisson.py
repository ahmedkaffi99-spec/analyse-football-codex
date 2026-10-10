"""Independent Poisson-score baseline for research and backtesting.

This is a transparent baseline, not a trained or production-ready model. Expected
goals (lambdas) must come from a separately validated source/model.
"""
from __future__ import annotations
from math import exp, isfinite
from .models import Outcome


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    """Return Poisson masses for scores 0..max_goals, renormalized after truncation."""
    values = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        values.append(values[-1] * rate / goals)
    total = sum(values)
    if total <= 0.0 or not isfinite(total):
        raise ValueError("could not compute a finite Poisson distribution")
    return [value / total for value in values]


def poisson_1x2(home_expected_goals: float, away_expected_goals: float, *, max_goals: int = 10) -> dict[Outcome, float]:
    """Estimate H/D/A probabilities from independent Poisson goal counts.

    The score grid is truncated at `max_goals` per team and each marginal is
    renormalized on that grid. Defaults are suitable for a simple baseline; the
    truncation parameter is explicit to make the approximation inspectable.
    """
    for name, rate in (("home_expected_goals", home_expected_goals), ("away_expected_goals", away_expected_goals)):
        if not isfinite(rate) or rate < 0.0 or rate > 20.0:
            raise ValueError(f"{name} must be finite and between 0 and 20")
    if isinstance(max_goals, bool) or not isinstance(max_goals, int) or not 1 <= max_goals <= 20:
        raise ValueError("max_goals must be an integer between 1 and 20")

    home = _poisson_pmf(float(home_expected_goals), max_goals)
    away = _poisson_pmf(float(away_expected_goals), max_goals)
    result = {Outcome.HOME: 0.0, Outcome.DRAW: 0.0, Outcome.AWAY: 0.0}
    for home_goals, p_home in enumerate(home):
        for away_goals, p_away in enumerate(away):
            if home_goals > away_goals:
                result[Outcome.HOME] += p_home * p_away
            elif home_goals == away_goals:
                result[Outcome.DRAW] += p_home * p_away
            else:
                result[Outcome.AWAY] += p_home * p_away
    # Correct minor floating-point drift while preserving relative probabilities.
    total = sum(result.values())
    return {outcome: probability / total for outcome, probability in result.items()}
