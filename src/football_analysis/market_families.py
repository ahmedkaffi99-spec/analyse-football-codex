"""Market-family taxonomy adapted from the read-only specialist-agent catalogue.

Only deterministic classification is migrated. The source's AI review calls,
measured family facts and veto behaviour are intentionally not included.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketFamily:
    id: str
    name: str
    categories: frozenset[str]


FAMILIES = (
    MarketFamily("result", "Match result / double chance", frozenset({"1x2", "double_chance", "dnb", "match_result"})),
    MarketFamily("goals_total", "Match total goals", frozenset({"total_goals", "goals_total"})),
    MarketFamily("team_goals", "Team goals / win to nil", frozenset({"team_goals", "win_to_nil", "clean_sheet"})),
    MarketFamily("btts", "Both teams to score", frozenset({"btts"})),
    MarketFamily("handicap", "Goal handicap", frozenset({"handicap", "asian_handicap", "european_handicap"})),
    MarketFamily("corners", "Corners", frozenset({"corners"})),
    MarketFamily("cards", "Cards", frozenset({"yellow_cards", "red_cards", "total_cards", "cards"})),
    MarketFamily("shots", "Shots", frozenset({"shots", "shots_on_target"})),
    MarketFamily("fouls", "Fouls", frozenset({"fouls"})),
    MarketFamily("offsides", "Offsides", frozenset({"offsides"})),
)
DERIVED = MarketFamily("derived", "Derived markets", frozenset())
_CATEGORY_MAP = {category: family for family in FAMILIES for category in family.categories}


def family_for_category(category: Any) -> MarketFamily:
    """Return the registered family, or the derived bucket for unknown categories."""
    key = str(category or "").strip().casefold().replace("-", "_").replace(" ", "_")
    return _CATEGORY_MAP.get(key, DERIVED)


def classify_market(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Add taxonomy metadata without altering market probabilities or selections."""
    category = candidate.get("market") or candidate.get("category") or ""
    family = family_for_category(category)
    return {"category": str(category), "family_id": family.id, "family_name": family.name,
            "known_category": family is not DERIVED}


def group_candidates_by_family(candidates: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Stable grouping for future specialist reviews; unknown markets stay grouped as derived."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates or ():
        if not isinstance(candidate, Mapping):
            continue
        family = family_for_category(candidate.get("market") or candidate.get("category"))
        groups.setdefault(family.id, []).append(dict(candidate))
    return groups
