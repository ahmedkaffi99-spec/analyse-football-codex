"""Persist API-Football collection and daily predictions to Supabase REST."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


class SupabaseWriteError(RuntimeError):
    pass


def _request(table: str, rows: list[dict[str, Any]], *, conflict: str | None = None) -> list[dict[str, Any]]:
    if not rows:
        return []
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        raise SupabaseWriteError("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant")
    query = f"?on_conflict={conflict}" if conflict else ""
    url = f"{base}/rest/v1/{table}{query}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    req = urllib.request.Request(url, data=json.dumps(rows, ensure_ascii=False).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else []
    except urllib.error.HTTPError as exc:
        # Do not include request URL or headers (which can contain credentials).
        detail = exc.read().decode("utf-8", "replace")[:1200]
        raise SupabaseWriteError(f"Supabase {table} HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SupabaseWriteError(f"Supabase {table}: {exc.__class__.__name__}") from None


def _upsert_batches(table: str, rows: list[dict[str, Any]], conflict: str, batch_size: int = 100) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for offset in range(0, len(rows), batch_size):
        result.extend(_request(table, rows[offset:offset + batch_size], conflict=conflict))
    return result


def persist_collection(*, report: dict[str, Any], fixture_rows: list[dict[str, Any]],
                       odds_rows: list[dict[str, Any]], histories: dict[str, list[dict[str, Any]]],
                       history_stats: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Idempotently store fixtures, 1xBet odds, historical team stats and predictions."""
    started = datetime.now(timezone.utc).isoformat()
    run_key = f"api-football-daily:{report.get('local_date')}:{report.get('generated_at')}"
    _request("data_ingestion_runs", [{
        "provider": "api-football", "dataset": "daily-football-analysis",
        "run_key": run_key, "status": "running",
        "metadata": {"local_date": report.get("local_date"), "bookmaker": "1xBet",
                     "market_weight": report.get("market_weight", 0.65)},
    }])
    try:
        # Include today's priority fixtures and all unique completed history fixtures.
        all_rows: dict[str, dict[str, Any]] = {}
        for row in fixture_rows:
            fid = (row.get("fixture") or {}).get("id")
            if fid is not None:
                all_rows[str(fid)] = row
        for team_rows in histories.values():
            for row in team_rows:
                fid = (row.get("fixture") or {}).get("id")
                if fid is not None:
                    all_rows.setdefault(str(fid), row)

        match_payload = []
        for fid, row in all_rows.items():
            fixture, teams, league = row.get("fixture") or {}, row.get("teams") or {}, row.get("league") or {}
            home, away = teams.get("home") or {}, teams.get("away") or {}
            kickoff = fixture.get("date")
            if not home.get("name") or not away.get("name") or not kickoff:
                continue
            match_payload.append({
                "provider": "api-football", "provider_match_id": str(fid),
                "league_id": str(league["id"]) if league.get("id") is not None else None,
                "league_name": league.get("name"), "season": league.get("season"),
                "home_team": str(home["name"]), "away_team": str(away["name"]),
                "kickoff_at": kickoff,
                "status": str(((fixture.get("status") or {}).get("short") or "unknown")).lower(),
                "raw_payload": row,
            })
        saved_matches = _upsert_batches("matches", match_payload, "provider,provider_match_id")
        ids = {str(row.get("provider_match_id")): row.get("id") for row in saved_matches}

        # Persist every available 1xBet quote as an immutable timestamped snapshot.
        captured_at = report.get("generated_at") or started
        odds_payload = []
        for row in odds_rows:
            fid = (row.get("fixture") or {}).get("id")
            if fid is None:
                continue
            for bookmaker in row.get("bookmakers") or []:
                name = str(bookmaker.get("name") or "")
                if "".join(c for c in name.casefold() if c.isalnum()) != "1xbet":
                    continue
                bookmaker_id = str(bookmaker.get("id") or "1xbet")
                for market in bookmaker.get("bets") or []:
                    market_id = str(market.get("id") or market.get("name") or "unknown")
                    market_name = str(market.get("name") or "unknown")
                    for item in market.get("values") or []:
                        try:
                            odd = float(item.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if odd <= 1:
                            continue
                        odds_payload.append({
                            "provider": "api-football", "fixture_id": str(fid),
                            "bookmaker_id": bookmaker_id, "bookmaker_name": "1xBet",
                            "market_id": market_id, "market_name": market_name,
                            "selection": str(item.get("value") or "unknown"), "odds": odd,
                            "point": float(item.get("handicap") or -999),
                            "captured_at": captured_at, "raw_payload": item,
                        })
        saved_odds = _upsert_batches(
            "football_odds", odds_payload,
            "provider,fixture_id,bookmaker_id,market_id,selection,point,captured_at")

        # Historical stats table is keyed by match UUID + side + provider.
        stats_payload = []
        for team_rows in histories.values():
            for row in team_rows:
                fixture, teams, goals = row.get("fixture") or {}, row.get("teams") or {}, row.get("goals") or {}
                fid = str(fixture.get("id") or "")
                match_uuid = ids.get(fid)
                if not match_uuid:
                    continue
                for side in ("home", "away"):
                    team = teams.get(side) or {}
                    if not team.get("name"):
                        continue
                    stats = (history_stats.get(fid) or {}).get(str(team.get("name")) or "") or {}
                    own_goals, other_goals = goals.get(side), goals.get("away" if side == "home" else "home")
                    def metric(name: str, cast=float):
                        value = stats.get(name)
                        if value is None:
                            return None
                        try:
                            return cast(value)
                        except (TypeError, ValueError):
                            return None
                    available = any(v is not None for v in stats.values())
                    stats_payload.append({
                        "match_id": match_uuid, "provider": "api-football",
                        "provider_team_id": str(team["id"]) if team.get("id") is not None else None,
                        "team_side": side, "team_name": str(team["name"]),
                        "goals_for": own_goals, "goals_against": other_goals,
                        "xg": metric("xg"), "shots": metric("shots", int),
                        "shots_on_target": metric("shots_on_target", int),
                        "corners": metric("corners", int), "yellow_cards": metric("yellow_cards", int),
                        "red_cards": metric("red_cards", int), "fouls": metric("fouls", int),
                        "possession_pct": metric("possession_pct"),
                        "provider_observed_at": captured_at,
                        "coverage_status": "complete" if available else "missing",
                        "raw_stats": stats,
                    })
        # De-duplicate within the same request before upsert.
        unique_stats = {(x["match_id"], x["team_side"], x["provider"]): x for x in stats_payload}
        saved_stats = _upsert_batches("team_match_stats", list(unique_stats.values()),
                                      "match_id,team_side,provider")

        predictions_payload = []
        for item in report.get("coupon") or []:
            match_uuid = ids.get(str(item.get("match_id")))
            probs = item.get("probabilities_combined") or {}
            goals = item.get("estimated_goals") or {}
            if not match_uuid:
                continue
            predictions_payload.append({
                "match_id": match_uuid, "model_name": item.get("model", report.get("model", "daily-baseline")),
                "model_version": "v1", "home_expected_goals": goals.get("home"),
                "away_expected_goals": goals.get("away"),
                "probability_home": probs.get("1"), "probability_draw": probs.get("x"),
                "probability_away": probs.get("2"), "market_weight": report.get("market_weight", 0.65),
                "explanation": {"pick": item.get("pick"), "odds_1xbet": item.get("odds_1xbet"),
                    "selected_odds": item.get("selected_odds"), "edge": item.get("edge"),
                    "expected_value": item.get("expected_value"), "markets": item.get("markets"),
                    "history_coverage": item.get("history_coverage"),
                    "history_averages": item.get("history_averages")},
            })
        saved_predictions = _request("predictions", predictions_payload)

        counts = {"matches": len(saved_matches), "odds": len(saved_odds),
                  "team_stats": len(saved_stats), "predictions": len(saved_predictions)}
        _request("data_ingestion_runs", [{
            "provider": "api-football", "dataset": "daily-football-analysis",
            "run_key": run_key, "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "succeeded", "requested_count": len(all_rows),
            "received_count": len(all_rows), "inserted_count": sum(counts.values()),
            "updated_count": 0, "missing_count": max(0, len(all_rows) - len(match_payload)),
            "metadata": {"local_date": report.get("local_date"), "bookmaker": "1xBet",
                         "market_weight": report.get("market_weight", 0.65), "saved": counts},
        }], conflict="run_key")
        return counts
    except Exception as exc:
        # Mark the ingestion run failed without leaking secrets.
        try:
            _request("data_ingestion_runs", [{
                "provider": "api-football", "dataset": "daily-football-analysis",
                "run_key": run_key, "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed", "error_summary": str(exc)[:1000],
                "metadata": {"local_date": report.get("local_date"), "bookmaker": "1xBet"},
            }], conflict="run_key")
        except Exception:
            pass
        raise
