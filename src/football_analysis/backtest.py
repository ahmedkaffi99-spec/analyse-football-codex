"""Offline backtesting with proper scoring rules and time-safe odds matching."""
from __future__ import annotations
from dataclasses import dataclass
from math import log
from typing import Iterable
from .models import MatchResult, OddsSnapshot, Outcome, Prediction

@dataclass(frozen=True, slots=True)
class BacktestReport:
    matches_evaluated: int
    brier_score: float | None
    log_loss: float | None
    bets_placed: int
    wins: int
    net_units: float
    roi: float | None

def _unique_by_id(items, label: str):
    indexed = {}
    for item in items:
        if item.match_id in indexed: raise ValueError(f"duplicate {label} for match_id={item.match_id!r}")
        indexed[item.match_id] = item
    return indexed

def evaluate_predictions(predictions: Iterable[Prediction], results: Iterable[MatchResult], odds_snapshots: Iterable[OddsSnapshot] = ()) -> BacktestReport:
    """Evaluate predictions; odds must be known by prediction time and before kickoff.

    One unit is staked on the most-probable outcome if a temporally eligible odds
    snapshot exists. Brier is the multiclass mean sum of squared errors; log loss
    uses a small floor for numerical safety. ROI is net units divided by bets.
    """
    prediction_map = _unique_by_id(predictions, "prediction")
    result_map = _unique_by_id(results, "result")
    odds = tuple(odds_snapshots)
    seen = set()
    for snapshot in odds:
        key = (snapshot.match_id, snapshot.observed_at)
        if key in seen: raise ValueError("duplicate odds snapshots for the same match and timestamp")
        seen.add(key)
    brier_total = log_loss_total = net_units = 0.0
    evaluated = bets = wins = 0
    for match_id in sorted(prediction_map.keys() & result_map.keys()):
        prediction, result = prediction_map[match_id], result_map[match_id]
        if prediction.generated_at >= result.kickoff: raise ValueError(f"prediction for {match_id} was generated at or after kickoff")
        probs = prediction.probabilities
        brier_total += sum((probs[o] - float(o == result.outcome)) ** 2 for o in Outcome)
        log_loss_total -= log(max(probs[result.outcome], 1e-15))
        evaluated += 1
        eligible = [s for s in odds if s.match_id == match_id and s.observed_at <= prediction.generated_at and s.observed_at < result.kickoff]
        if not eligible: continue
        snapshot = max(eligible, key=lambda s: s.observed_at)
        pick = max(Outcome, key=lambda o: probs[o])
        bets += 1
        if pick == result.outcome:
            wins += 1
            net_units += snapshot.decimal_odds[pick] - 1.0
        else: net_units -= 1.0
    return BacktestReport(evaluated, brier_total / evaluated if evaluated else None, log_loss_total / evaluated if evaluated else None, bets, wins, net_units, net_units / bets if bets else None)
