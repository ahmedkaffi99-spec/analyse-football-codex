"""Offline-first football probability evaluation and backtesting."""

from .backtest import BacktestReport, evaluate_predictions
from .models import MatchResult, OddsSnapshot, Outcome, Prediction
from .poisson import poisson_1x2

__all__ = [
    "BacktestReport",
    "MatchResult",
    "OddsSnapshot",
    "Outcome",
    "Prediction",
    "evaluate_predictions",
    "poisson_1x2",
]
