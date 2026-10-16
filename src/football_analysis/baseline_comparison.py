"""Compare model probabilities with uniform and de-vigged market baselines."""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Iterable

from .models import MatchResult, OddsSnapshot, Outcome, Prediction


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    sample_size: int
    market_sample_size: int
    model_brier: float | None
    uniform_brier: float | None
    market_brier: float | None
    model_log_loss: float | None
    uniform_log_loss: float | None
    market_log_loss: float | None


def _scores(probabilities: dict[Outcome, float], outcome: Outcome) -> tuple[float, float]:
    brier = sum((probabilities[o] - float(o == outcome)) ** 2 for o in Outcome)
    log_loss = -log(max(probabilities[outcome], 1e-15))
    return brier, log_loss


def compare_baselines(
    predictions: Iterable[Prediction],
    results: Iterable[MatchResult],
    odds_snapshots: Iterable[OddsSnapshot] = (),
) -> BaselineComparison:
    """Score model, uniform 1/3, and normalized implied market probabilities.

    Only the latest odds snapshot observed no later than prediction generation
    and strictly before kickoff is eligible. Market probabilities are normalized
    by their implied-probability sum to remove the overround approximately.
    """
    prediction_rows = list(predictions)
    result_rows = list(results)
    prediction_map = {p.match_id: p for p in prediction_rows}
    result_map = {r.match_id: r for r in result_rows}
    if len(prediction_map) != len(prediction_rows) or len(result_map) != len(result_rows):
        raise ValueError("duplicate prediction or result match_id")
    odds = list(odds_snapshots)
    keys = [(o.match_id, o.observed_at) for o in odds]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate odds snapshots for the same match and timestamp")

    model_brier = uniform_brier = market_brier = 0.0
    model_log = uniform_log = market_log = 0.0
    n = market_n = 0
    uniform = {o: 1.0 / 3.0 for o in Outcome}
    for match_id in sorted(prediction_map.keys() & result_map.keys()):
        pred, result = prediction_map[match_id], result_map[match_id]
        if pred.generated_at >= result.kickoff:
            raise ValueError(f"prediction for {match_id} was generated at or after kickoff")
        mb, ml = _scores(dict(pred.probabilities), result.outcome)
        ub, ul = _scores(uniform, result.outcome)
        model_brier += mb; model_log += ml
        uniform_brier += ub; uniform_log += ul
        n += 1
        eligible = [o for o in odds if o.match_id == match_id and o.observed_at <= pred.generated_at and o.observed_at < result.kickoff]
        if eligible:
            snapshot = max(eligible, key=lambda o: o.observed_at)
            raw = {outcome: 1.0 / snapshot.decimal_odds[outcome] for outcome in Outcome}
            total = sum(raw.values())
            market = {outcome: value / total for outcome, value in raw.items()}
            b, ll = _scores(market, result.outcome)
            market_brier += b; market_log += ll
            market_n += 1
    return BaselineComparison(
        n, market_n,
        model_brier / n if n else None,
        uniform_brier / n if n else None,
        market_brier / market_n if market_n else None,
        model_log / n if n else None,
        uniform_log / n if n else None,
        market_log / market_n if market_n else None,
    )
