"""Point-in-time rolling features for offline football research.

No network or database access. Inputs are explicit historical observations and
must carry availability timestamps. Unknown statistics remain missing, never zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from statistics import mean
from typing import Mapping


@dataclass(frozen=True, slots=True)
class HistoricalObservation:
    match_id: str
    kickoff_at: datetime
    finished_at: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    stats_available_at: datetime | None = None
    home_stats: Mapping[str, float | None] = field(default_factory=dict)
    away_stats: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("kickoff_at", self.kickoff_at), ("finished_at", self.finished_at)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.finished_at < self.kickoff_at:
            raise ValueError("finished_at must not precede kickoff_at")
        if self.stats_available_at is not None and (
            self.stats_available_at.tzinfo is None or self.stats_available_at.utcoffset() is None
        ):
            raise ValueError("stats_available_at must be timezone-aware")
        if not self.match_id.strip() or not self.home_team.strip() or not self.away_team.strip():
            raise ValueError("match and team identifiers must not be empty")
        if self.home_team.strip().casefold() == self.away_team.strip().casefold():
            raise ValueError("home and away teams must differ")
        for name, value in (("home_goals", self.home_goals), ("away_goals", self.away_goals)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for stats in (self.home_stats, self.away_stats):
            for key, value in stats.items():
                if value is not None and (not isfinite(float(value)) or float(value) < 0):
                    raise ValueError(f"stat {key!r} must be non-negative and finite, or None")


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    match_id: str
    generated_at: datetime
    data_cutoff_at: datetime
    feature_schema_version: str
    features: Mapping[str, float | int | None]
    quality_flags: tuple[str, ...]


def build_team_features(
    *,
    match_id: str,
    home_team: str,
    away_team: str,
    kickoff_at: datetime,
    generated_at: datetime,
    history: list[HistoricalObservation] | tuple[HistoricalObservation, ...],
    windows: tuple[int, ...] = (5, 10),
    schema_version: str = "v1",
) -> FeatureSnapshot:
    """Build team rolling features using only matches finished by generated_at.

    Match stats are usable only if their source availability timestamp is no later
    than generated_at. If absent, goal results can still be used, but match stats
    remain missing. The target match must be generated before its kickoff.
    """
    for name, value in (("kickoff_at", kickoff_at), ("generated_at", generated_at)):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
    if generated_at >= kickoff_at:
        raise ValueError("features must be generated strictly before kickoff")
    if not match_id.strip() or not home_team.strip() or not away_team.strip():
        raise ValueError("match and team identifiers must not be empty")
    if home_team.strip().casefold() == away_team.strip().casefold():
        raise ValueError("home and away teams must differ")
    if not windows or any(isinstance(w, bool) or not isinstance(w, int) or w < 1 for w in windows):
        raise ValueError("windows must contain positive integers")
    rows = list(history)
    ids = [row.match_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate historical match_id")

    # Finished historical results are eligible only once actually finished.
    eligible = [row for row in rows if row.finished_at <= generated_at and row.kickoff_at < kickoff_at]
    eligible.sort(key=lambda row: (row.finished_at, row.match_id))
    target_home, target_away = home_team.strip().casefold(), away_team.strip().casefold()
    features: dict[str, float | int | None] = {}
    flags: list[str] = []

    for side, team in (("home", target_home), ("away", target_away)):
        team_rows = []
        venue_rows = []
        for row in eligible:
            is_home = row.home_team.strip().casefold() == team
            is_away = row.away_team.strip().casefold() == team
            if not (is_home or is_away):
                continue
            goals_for = row.home_goals if is_home else row.away_goals
            goals_against = row.away_goals if is_home else row.home_goals
            stats_are_available = row.stats_available_at is not None and row.stats_available_at <= generated_at
            own_stats = row.home_stats if is_home else row.away_stats
            opp_stats = row.away_stats if is_home else row.home_stats
            stats = dict(own_stats) if stats_are_available else {}
            if stats_are_available:
                stats.update({f"against_{key}": value for key, value in opp_stats.items()})
            if stats_are_available and stats.get("xga") is None:
                stats["xga"] = opp_stats.get("xg")
            record = {"goals_for": float(goals_for), "goals_against": float(goals_against), **stats}
            team_rows.append((row, record, is_home))
            if (side == "home" and is_home) or (side == "away" and is_away):
                venue_rows.append((row, record, is_home))

        for window in windows:
            selected = team_rows[-window:]
            features[f"{side}_matches_available_{window}"] = len(selected)
            for metric in ("goals_for", "goals_against", "xg", "xga", "shots", "shots_on_target", "corners", "yellow_cards", "red_cards"):
                values = []
                for _, record, _ in selected:
                    value = record.get(metric)
                    if value is not None and isfinite(float(value)):
                        values.append(float(value))
                features[f"{side}_{metric}_avg_{window}"] = mean(values) if values else None
                features[f"{side}_{metric}_n_{window}"] = len(values)
            venue_selected = venue_rows[-window:]
            features[f"{side}_venue_matches_available_{window}"] = len(venue_selected)
            for metric in ("goals_for", "goals_against", "xg", "xga", "shots", "shots_on_target", "corners", "yellow_cards", "red_cards"):
                values = [float(record[metric]) for _, record, _ in venue_selected if record.get(metric) is not None]
                features[f"{side}_venue_{metric}_avg_{window}"] = mean(values) if values else None

    if not eligible:
        flags.append("no_finished_history_available")
    for side in ("home", "away"):
        if features.get(f"{side}_matches_available_{max(windows)}", 0) < max(windows):
            flags.append(f"limited_history_{side}")
        if features.get(f"{side}_corners_n_{max(windows)}", 0) == 0:
            flags.append(f"corners_missing_{side}")
        if features.get(f"{side}_xg_n_{max(windows)}", 0) == 0:
            flags.append(f"xg_missing_{side}")

    return FeatureSnapshot(
        match_id=match_id,
        generated_at=generated_at,
        data_cutoff_at=generated_at,
        feature_schema_version=schema_version,
        features=features,
        quality_flags=tuple(sorted(set(flags))),
    )
