"""Leakage-safe team attack/defence strengths from completed historical scores.

This is a transparent baseline. It requires explicitly supplied finished matches;
it does not fetch data or connect to Supabase. Strengths are shrunk toward league
averages to reduce overreaction to small samples.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


@dataclass(frozen=True, slots=True)
class HistoricalMatch:
    match_id: str
    kickoff: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.match_id.strip():
            raise ValueError("match_id must not be empty")
        if self.kickoff.tzinfo is None or self.kickoff.utcoffset() is None:
            raise ValueError("kickoff must be timezone-aware")
        if self.finished_at is not None:
            if self.finished_at.tzinfo is None or self.finished_at.utcoffset() is None:
                raise ValueError("finished_at must be timezone-aware")
            if self.finished_at < self.kickoff:
                raise ValueError("finished_at must not precede kickoff")
        if not self.home_team.strip() or not self.away_team.strip():
            raise ValueError("team names must not be empty")
        if self.home_team.strip().casefold() == self.away_team.strip().casefold():
            raise ValueError("home_team and away_team must differ")
        for field, value in (("home_goals", self.home_goals), ("away_goals", self.away_goals)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class TeamStrength:
    matches: int
    attack: float
    defence: float
    goals_for_per_match: float
    goals_against_per_match: float


@dataclass(frozen=True, slots=True)
class StrengthModel:
    league_home_goals: float
    league_away_goals: float
    home_advantage: float
    prior_matches: float
    teams: dict[str, TeamStrength]


def fit_team_strengths(
    matches: Iterable[HistoricalMatch],
    *,
    prior_matches: float = 5.0,
    home_advantage: float = 1.08,
) -> StrengthModel:
    """Fit normalized attack and defensive-weakness multipliers from finished matches."""
    if not isfinite(prior_matches) or prior_matches <= 0:
        raise ValueError("prior_matches must be finite and greater than zero")
    if not isfinite(home_advantage) or not 0.5 <= home_advantage <= 2.0:
        raise ValueError("home_advantage must be finite and between 0.5 and 2.0")

    rows = list(matches)
    if not rows:
        raise ValueError("at least one historical match is required")
    ids = [row.match_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate historical match_id")

    league_home = sum(row.home_goals for row in rows) / len(rows)
    league_away = sum(row.away_goals for row in rows) / len(rows)
    if league_home <= 0 or league_away <= 0:
        raise ValueError("historical sample must have positive home and away goal averages")

    # team -> matches, goals for, goals against, expected scoring baseline
    aggregates: dict[str, list[float]] = {}
    for row in rows:
        home, away = row.home_team.strip(), row.away_team.strip()
        if home.casefold() == away.casefold():
            raise ValueError("a team cannot play itself")
        aggregates.setdefault(home.casefold(), [0.0, 0.0, 0.0, 0.0, 0.0])
        aggregates.setdefault(away.casefold(), [0.0, 0.0, 0.0, 0.0, 0.0])
        aggregates[home.casefold()][0] += 1
        aggregates[home.casefold()][1] += row.home_goals
        aggregates[home.casefold()][2] += row.away_goals
        aggregates[home.casefold()][3] += league_home
        aggregates[home.casefold()][4] += league_away
        aggregates[away.casefold()][0] += 1
        aggregates[away.casefold()][1] += row.away_goals
        aggregates[away.casefold()][2] += row.home_goals
        aggregates[away.casefold()][3] += league_away
        aggregates[away.casefold()][4] += league_home

    league_average = (league_home + league_away) / 2
    teams: dict[str, TeamStrength] = {}
    for key, (count, goals_for, goals_against, expected_for, expected_against) in aggregates.items():
        for_baseline = expected_for / count
        against_baseline = expected_against / count
        shrunk_for = (goals_for + prior_matches * for_baseline) / (count + prior_matches)
        shrunk_against = (goals_against + prior_matches * against_baseline) / (count + prior_matches)
        teams[key] = TeamStrength(
            matches=int(count),
            attack=shrunk_for / league_average,
            defence=shrunk_against / league_average,
            goals_for_per_match=goals_for / count,
            goals_against_per_match=goals_against / count,
        )
    return StrengthModel(league_home, league_away, home_advantage, prior_matches, teams)


def expected_goals(model: StrengthModel, home_team: str, away_team: str) -> tuple[float, float]:
    """Estimate home/away xG using attack and opponent defensive-weakness multipliers."""
    if not home_team.strip() or not away_team.strip():
        raise ValueError("team names must not be empty")
    if home_team.strip().casefold() == away_team.strip().casefold():
        raise ValueError("home_team and away_team must differ")
    try:
        home = model.teams[home_team.strip().casefold()]
        away = model.teams[away_team.strip().casefold()]
    except KeyError as exc:
        raise ValueError(f"team not present in historical sample: {exc.args[0]}") from exc

    home_xg = model.league_home_goals * home.attack * away.defence * model.home_advantage
    away_xg = model.league_away_goals * away.attack * home.defence
    return min(8.0, max(0.05, home_xg)), min(8.0, max(0.05, away_xg))
