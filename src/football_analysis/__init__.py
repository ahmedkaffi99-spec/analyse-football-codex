"""Offline-first football probability evaluation and backtesting."""

from .backtest import BacktestReport, evaluate_predictions
from .feature_engine import FeatureSnapshot, HistoricalObservation, build_team_features
from .baseline_comparison import BaselineComparison, compare_baselines
from .models import MatchResult, OddsSnapshot, Outcome, Prediction
from .poisson import poisson_1x2
from .walk_forward import WalkForwardReport, walk_forward_backtest

__all__ = [
    "BacktestReport",
    "FeatureSnapshot",
    "HistoricalObservation",
    "BaselineComparison",
    "MatchResult",
    "OddsSnapshot",
    "Outcome",
    "Prediction",
    "WalkForwardReport",
    "build_team_features",
    "compare_baselines",
    "evaluate_predictions",
    "poisson_1x2",
    "walk_forward_backtest",
]
