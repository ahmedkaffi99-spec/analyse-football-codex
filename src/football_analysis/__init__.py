"""Offline-first football probability evaluation and backtesting."""

from .backtest import BacktestReport, evaluate_predictions
from .models import MatchResult, OddsSnapshot, Outcome, Prediction

__all__ = ["BacktestReport", "MatchResult", "OddsSnapshot", "Outcome", "Prediction", "evaluate_predictions"]
