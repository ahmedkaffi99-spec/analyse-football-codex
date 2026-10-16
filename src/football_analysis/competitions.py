"""Competition and club scope for the daily European football pipeline."""
from __future__ import annotations
import unicodedata
from typing import Any

# API-Football league IDs: Premier League, La Liga, Bundesliga, Serie A,
# Ligue 1 and UEFA Champions League.
PRIORITY_LEAGUE_IDS = {39, 140, 78, 135, 61, 2}

# Major European clubs are also included when they play outside those leagues,
# for example in domestic cups or European competitions.
MAJOR_CLUBS = {
    "real madrid", "barcelona", "atletico madrid", "atletico de madrid",
    "girona", "athletic club", "real sociedad", "sevilla", "valencia",
    "manchester city", "manchester united", "liverpool", "arsenal",
    "chelsea", "tottenham", "newcastle united", "aston villa",
    "bayern munich", "borussia dortmund", "bayer leverkusen", "rb leipzig",
    "eintracht frankfurt", "stuttgart", "inter", "ac milan", "milan",
    "juventus", "napoli", "roma", "lazio", "atalanta", "fiorentina",
    "paris saint germain", "psg", "marseille", "monaco", "lille", "lyon",
    "benfica", "porto", "sporting cp", "sporting lisbon", "ajax",
    "psv", "feyenoord", "celtic", "rangers", "galatasaray", "fenerbahce",
    "besiktas", "club brugge", "anderlecht", "shakhtar donetsk",
}

def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in raw if not unicodedata.combining(ch)).replace("-", " ").split())

def is_priority_fixture(row: dict[str, Any]) -> bool:
    league = row.get("league") or {}
    try:
        if int(league.get("id")) in PRIORITY_LEAGUE_IDS:
            return True
    except (TypeError, ValueError):
        pass
    teams = row.get("teams") or {}
    names = {_norm((teams.get(side) or {}).get("name")) for side in ("home", "away")}
    return bool(names & {_norm(name) for name in MAJOR_CLUBS})

def filter_priority_fixtures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep matches in the top five European leagues, UCL, or involving a major club."""
    return [row for row in rows if is_priority_fixture(row)]
