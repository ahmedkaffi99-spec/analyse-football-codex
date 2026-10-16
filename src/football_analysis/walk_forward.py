"""Chronological walk-forward evaluation of the historical team-strength baseline.

Only matches known to be finished before prediction time are used to fit the model.
This module is offline-only and consumes explicitly supplied finished matches.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from .backtest import BacktestReport, evaluate_predictions
from .models import MatchResult, Prediction
from .poisson import poisson_1x2
from .strengths import HistoricalMatch, expected_goals, fit_team_strengths


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    report: BacktestReport
    predictions: tuple[Prediction, ...]
    results: tuple[MatchResult, ...]
    skipped_matches: tuple[str, ...]


def walk_forward_backtest(
    matches: Iterable[HistoricalMatch],
    *,
    min_train_matches: int = 20,
    prediction_lead: timedelta = timedelta(hours=2),
    prior_matches: float = 5.0,
) -> WalkForwardReport:
    """Generate out-of-sample 1X2 predictions using strictly earlier matches.

    Matches without enough earlier training data, or involving teams absent from
    the training sample, are skipped. Matches sharing a kickoff timestamp are
    evaluated against the same strictly earlier history, never against each other.
    """
    rows = list(matches)
    if isinstance(min_train_matches, bool) or not isinstance(min_train_matches, int) or min_train_matches < 1:
        raise ValueError("min_train_matches must be a positive integer")
    if prediction_lead.total_seconds() < 0:
        raise ValueError("prediction_lead must not be negative")
    ids = [row.match_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate historical match_id")
    rows.sort(key=lambda row: (row.kickoff, row.match_id))

    predictions: list[Prediction] = []
    results: list[MatchResult] = []
    skipped: list[str] = []
    for target in rows:
        generated_at = target.kickoff - prediction_lead
        # Prefer verified final-whistle timestamps. If unavailable, use a
        # conservative three-hour duration proxy; this is not a substitute for
        # verified completion data in production research.
        history = [
            row for row in rows
            if (row.finished_at <= generated_at if row.finished_at is not None
                else row.kickoff + timedelta(hours=3) <= generated_at)
        ]
        if len(history) < min_train_matches:
            skipped.append(target.match_id)
            continue
        try:
            model = fit_team_strengths(history, prior_matches=prior_matches)
            home_xg, away_xg = expected_goals(model, target.home_team, target.away_team)
        except ValueError:
            # Insufficient or degenerate history/team coverage: no fabricated prediction.
            skipped.append(target.match_id)
            continue
        probabilities = poisson_1x2(home_xg, away_xg)
        predictions.append(Prediction(target.match_id, generated_at, probabilities))
        results.append(MatchResult(target.match_id, target.kickoff, target.home_goals, target.away_goals))

    report = evaluate_predictions(predictions, results)
    return WalkForwardReport(report, tuple(predictions), tuple(results), tuple(skipped))
