"""Offline-first football probability evaluation and backtesting."""

from .backtest import BacktestReport, evaluate_predictions
from .models import MatchResult, OddsSnapshot, Outcome, Prediction
from .poisson import poisson_1x2
from .walk_forward import WalkForwardReport, walk_forward_backtest

__all__ = [
    "BacktestReport",
    "MatchResult",
    "OddsSnapshot",
    "Outcome",
    "Prediction",
    "WalkForwardReport",
    "evaluate_predictions",
    "poisson_1x2",
    "walk_forward_backtest",
]
