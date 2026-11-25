"""Conservative cross-provider fixture resolver.

Uses normalized team names plus kickoff date/competition context. It never guesses
when candidates are ambiguous: callers must handle the unresolved result.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
from .team_names import normalize_team, similarity_score

def _date(value: Any) -> date | None:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError): return None

def _team_pair(row: dict[str, Any]) -> tuple[str, str]:
    home = row.get("home") or row.get("home_team") or (row.get("teams") or {}).get("home", {}).get("name")
    away = row.get("away") or row.get("away_team") or (row.get("teams") or {}).get("away", {}).get("name")
    return normalize_team(home), normalize_team(away)

def _kickoff(row: dict[str, Any]) -> date | None:
    return _date(row.get("kickoff") or row.get("date") or row.get("fixture_date") or
                 (row.get("fixture") or {}).get("date"))

def _competition(row: dict[str, Any]) -> str:
    value = row.get("competition") or row.get("league") or (row.get("league") or {}).get("name") or ""
    if isinstance(value, dict): value = value.get("name") or value.get("id") or ""
    return normalize_team(str(value))

def score_fixture_match(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Return explainable score (0..100); reversed home/away is penalized, not accepted."""
    lh, la = _team_pair(left); rh, ra = _team_pair(right)
    if not all((lh, la, rh, ra)):
        return {"score": 0, "reason": "missing_team_name", "home_score": 0, "away_score": 0}
    home_score, away_score = similarity_score(lh, rh), similarity_score(la, ra)
    team_score = (home_score + away_score) / 2
    ld, rd = _kickoff(left), _kickoff(right)
    date_score = 100 if ld and rd and ld == rd else 60 if ld and rd and abs((ld-rd).days) == 1 else 0 if ld and rd else 50
    lc, rc = _competition(left), _competition(right)
    comp_score = 100 if lc and rc and lc == rc else 65 if lc and rc else 50
    score = round(team_score * .75 + date_score * .20 + comp_score * .05)
    if (lh, la) != (rh, ra) and (lh, la) == (ra, rh):
        score = min(score, 45)
    return {"score": score, "home_score": home_score, "away_score": away_score,
            "date_score": date_score, "competition_score": comp_score,
            "reason": "scored"}

def resolve_fixture(source: dict[str, Any], candidates: list[dict[str, Any]], *,
                   threshold: int = 92, min_margin: int = 8) -> dict[str, Any]:
    """Resolve only a high-confidence unique match; report ambiguity otherwise."""
    if not 0 <= threshold <= 100: raise ValueError("threshold must be between 0 and 100")
    if min_margin < 0: raise ValueError("min_margin must be non-negative")
    scored=[]
    for candidate in candidates:
        result=score_fixture_match(source,candidate)
        scored.append({"fixture":candidate,**result})
    scored.sort(key=lambda item:item["score"],reverse=True)
    if not scored: return {"status":"not_found","match":None,"score":0,"runner_up_score":0,"candidates":[]}
    top=scored[0]; runner=scored[1]["score"] if len(scored)>1 else 0
    if top["score"] < threshold:
        status="below_threshold"
    elif top["score"]-runner < min_margin:
        status="ambiguous"
    else:
        status="matched"
    return {"status":status,"match":top["fixture"] if status=="matched" else None,
            "score":top["score"],"runner_up_score":runner,"candidates":scored[:5]}
