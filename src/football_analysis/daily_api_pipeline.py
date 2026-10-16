"""Live daily match selection using API-Football fixtures and 1xBet odds.

Ranks complete 1X2 markets by de-vigged implied probability. This is a
market-based baseline, not a trained ML prediction; no xG is fabricated.
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from .collect_odds import api_get, is_target_bookmaker, only_target_bookmaker
from .api_football_client import ApiFootballResponseError
from .competitions import filter_priority_fixtures
from .markets import normalize_implied_probabilities
from .value_analysis import score_market_predictions
from .poisson import poisson_1x2
from .telegram_publisher import send_message

LOCAL_TZ = ZoneInfo("Africa/Djibouti")

def _fixture_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        fixture, teams = row.get("fixture") or {}, row.get("teams") or {}
        home, away, fid, kickoff = (teams.get("home") or {}).get("name"), (teams.get("away") or {}).get("name"), fixture.get("id"), fixture.get("date")
        if fid is None or not home or not away or not kickoff: continue
        try: start = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
        except ValueError: continue
        if start.tzinfo is None or start <= datetime.now(timezone.utc): continue
        if str((fixture.get("status") or {}).get("short") or "").upper() not in {"NS", "TBD"}: continue
        result[str(fid)] = {"match_id":str(fid),"kickoff":start.isoformat(),"home":str(home),"away":str(away),"league":str((row.get("league") or {}).get("name") or "Compétition inconnue")}
    return result

def _market_1x2(odds_row: dict[str, Any]) -> dict[str, float] | None:
    for bookmaker in odds_row.get("bookmakers") or []:
        if not is_target_bookmaker(bookmaker.get("name")): continue
        for market in bookmaker.get("bets") or []:
            if str(market.get("name") or "").casefold() not in {"match winner","1x2","fulltime result","full time result"}: continue
            values = {}
            aliases = {"home":"1","1":"1","team 1":"1","draw":"x","x":"x","away":"2","2":"2","team 2":"2"}
            for item in market.get("values") or []:
                key = aliases.get(str(item.get("value") or "").strip().casefold())
                try: odd = float(item.get("odd"))
                except (TypeError, ValueError): continue
                if key and odd > 1: values[key] = odd
            if set(values) == {"1","x","2"}: return values
    return None

def estimate_recent_xg(team_id: int, history_rows: list[dict[str, Any]]) -> tuple[float, float, int]:
    """Estimate goals for/against from up to ten completed recent fixtures."""
    scored, conceded = [], []
    for row in history_rows:
        status = str(((row.get("fixture") or {}).get("status") or {}).get("short") or "").upper()
        if status not in {"FT", "AET", "PEN"}: continue
        teams, goals = row.get("teams") or {}, row.get("goals") or {}
        home_id, away_id = (teams.get("home") or {}).get("id"), (teams.get("away") or {}).get("id")
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None: continue
        if home_id == team_id: scored.append(float(hg)); conceded.append(float(ag))
        elif away_id == team_id: scored.append(float(ag)); conceded.append(float(hg))
    if not scored: return 1.25, 1.25, 0
    return sum(scored)/len(scored), sum(conceded)/len(conceded), len(scored)


def _completed_matches(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    completed = []
    for row in rows:
        status = str(((row.get("fixture") or {}).get("status") or {}).get("short") or "").upper()
        goals = row.get("goals") or {}
        if status in {"FT", "AET", "PEN"} and goals.get("home") is not None and goals.get("away") is not None:
            completed.append(row)
    completed.sort(key=lambda row: str((row.get("fixture") or {}).get("date") or ""), reverse=True)
    return completed[:limit]


STAT_ALIASES = {
    "total shots": "shots", "shots": "shots",
    "shots on goal": "shots_on_target", "shots on target": "shots_on_target",
    "corner kicks": "corners", "corners": "corners",
    "yellow cards": "yellow_cards", "red cards": "red_cards",
    "fouls": "fouls", "ball possession": "possession_pct",
    "expected goals": "xg", "offsides": "offsides",
}


def _parse_fixture_statistics(response: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    """Parse API-Football fixture statistics into team-name keyed numeric metrics."""
    parsed: dict[str, dict[str, float | None]] = {}
    for team_block in response:
        team = team_block.get("team") or {}
        team_name = str(team.get("name") or team.get("id") or "")
        if not team_name:
            continue
        metrics: dict[str, float | None] = {}
        for item in team_block.get("statistics") or []:
            key = STAT_ALIASES.get(str(item.get("type") or "").strip().casefold())
            value = item.get("value")
            if not key or value is None or value == "":
                continue
            try:
                numeric = float(str(value).replace("%", "").replace(",", "."))
            except (TypeError, ValueError):
                continue
            metrics[key] = numeric
        parsed[team_name] = metrics
    return parsed


def summarize_last_ten(team_id: int, history_rows: list[dict[str, Any]],
                       stats_by_fixture: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Mean goals and available match stats over the team's latest ten completed games."""
    rows = _completed_matches(history_rows, 10)
    metrics: dict[str, list[float]] = {
        key: [] for key in ("goals_for", "goals_against", "shots", "shots_on_target",
                            "corners", "yellow_cards", "red_cards", "fouls",
                            "possession_pct", "xg", "offsides")
    }
    for row in rows:
        fixture = row.get("fixture") or {}
        fid = str(fixture.get("id") or "")
        teams, goals = row.get("teams") or {}, row.get("goals") or {}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        hg, ag = goals.get("home"), goals.get("away")
        if hg is not None and ag is not None:
            if home.get("id") == team_id:
                metrics["goals_for"].append(float(hg)); metrics["goals_against"].append(float(ag))
                own_name = str(home.get("name") or home.get("id") or "")
            elif away.get("id") == team_id:
                metrics["goals_for"].append(float(ag)); metrics["goals_against"].append(float(hg))
                own_name = str(away.get("name") or away.get("id") or "")
            else:
                continue
        else:
            continue
        match_stats = stats_by_fixture.get(fid) or {}
        own = match_stats.get(own_name) or {}
        for metric in metrics:
            if metric in {"goals_for", "goals_against"}:
                continue
            value = own.get(metric)
            if value is not None:
                metrics[metric].append(float(value))
    means = {f"{key}_mean": round(sum(values) / len(values), 3) if values else None
             for key, values in metrics.items()}
    counts = {f"{key}_n": len(values) for key, values in metrics.items()}
    return {"matches_used": len(rows), **means, **counts}


def build_live_report(fixtures_response: dict[str, Any], odds_response: dict[str, Any], *, histories: dict[str, list[dict[str, Any]]] | None = None, head_to_head: dict[str, list[dict[str, Any]]] | None = None, collected_stats: dict[str, Any] | None = None, history_stats: dict[str, dict[str, Any]] | None = None, max_legs: int = 8, market_weight: float = 0.65) -> dict[str, Any]:
    if not 1 <= max_legs <= 20: raise ValueError("max_legs must be between 1 and 20")
    if not 0.0 <= market_weight <= 1.0: raise ValueError("market_weight must be between 0 and 1")
    histories, head_to_head, collected_stats = histories or {}, head_to_head or {}, collected_stats or {}
    history_stats = history_stats or {}
    fixture_rows = fixtures_response.get("response") or []
    fixtures = _fixture_map(fixture_rows)
    raw_by_id = {str((row.get("fixture") or {}).get("id")): row for row in fixture_rows}
    odds_rows = only_target_bookmaker(odds_response.get("response") or [])
    selected, odds_fixtures, complete_ids = [], set(), set()
    for row in odds_rows:
        fid = str(((row.get("fixture") or {}).get("id") or ""))
        if fid not in fixtures: continue
        odds_fixtures.add(fid)
        market = _market_1x2(row)
        if not market: continue
        complete_ids.add(fid)
        market_probs = normalize_implied_probabilities(market)
        teams = (raw_by_id.get(fid) or {}).get("teams") or {}
        home_id, away_id = (teams.get("home") or {}).get("id"), (teams.get("away") or {}).get("id")
        hf, ha, hn = estimate_recent_xg(int(home_id), histories.get(str(home_id), [])) if home_id is not None else (1.25, 1.25, 0)
        af, aa, an = estimate_recent_xg(int(away_id), histories.get(str(away_id), [])) if away_id is not None else (1.25, 1.25, 0)
        home_xg = max(0.05, min(5.0, ((hf + aa) / 2) * 1.08))
        away_xg = max(0.05, min(5.0, (af + ha) / 2))
        raw_model = poisson_1x2(home_xg, away_xg)
        model_probs = {"1": raw_model[next(k for k in raw_model if k.value == "H")], "x": raw_model[next(k for k in raw_model if k.value == "D")], "2": raw_model[next(k for k in raw_model if k.value == "A")]}
        combined = {key: market_weight * market_probs[key] + (1-market_weight) * model_probs[key] for key in ("1", "x", "2")}
        norm = sum(combined.values())
        combined = {key: value/norm for key, value in combined.items()}
        pick = max(combined, key=combined.get)
        home_history = _completed_matches(histories.get(str(home_id), []), 10) if home_id is not None else []
        away_history = _completed_matches(histories.get(str(away_id), []), 10) if away_id is not None else []
        h2h_history = _completed_matches(head_to_head.get(fid, []), 5)
        market_family_predictions = score_market_predictions(
            row, model_1x2=combined, home_xg=home_xg, away_xg=away_xg)
        selected_odds = market[pick]
        selected_market_probability = market_probs[pick]
        selected_edge = combined[pick] - selected_market_probability
        selected_ev = combined[pick] * selected_odds - 1
        selected.append({**fixtures[fid], "market":"1X2", "pick":pick,
            "pick_label":{"1":"Victoire domicile","x":"Match nul","2":"Victoire extérieur"}[pick],
            "probability":round(combined[pick],4), "selected_odds":selected_odds,
            "market_probability":round(selected_market_probability,6),
            "edge":round(selected_edge,6), "edge_pct_points":round(selected_edge*100,2),
            "expected_value":round(selected_ev,6),
            "value_status":"positive_ev" if selected_ev > 0 else "negative_ev",
            "markets":market_family_predictions,
            "probabilities_combined":{k:round(v,6) for k,v in combined.items()},
            "probabilities_1xbet_normalized":{k:round(v,6) for k,v in market_probs.items()},
            "probabilities_recent_form":{k:round(v,6) for k,v in model_probs.items()},
            "recent_form_sample":{"home":hn,"away":an}, "estimated_goals":{"home":round(home_xg,3),"away":round(away_xg,3)},
            "last_10_home_team_matches":home_history, "last_10_away_team_matches":away_history,
            "last_5_head_to_head":h2h_history,
            "history_averages":{"home":summarize_last_ten(int(home_id), home_history, history_stats) if home_id is not None else {},
                                "away":summarize_last_ten(int(away_id), away_history, history_stats) if away_id is not None else {}},
            "history_coverage":{"home":len(home_history),"away":len(away_history),"head_to_head":len(h2h_history)},
            "fixture_statistics":collected_stats.get(fid,[]), "odds_1xbet":market,
            "model":"recent_10_matches_poisson_plus_1xbet", "market_weight":market_weight})
    selected.sort(key=lambda x:(-x["probability"],x["kickoff"],x["match_id"]))
    selected = selected[:max_legs]
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"local_date":datetime.now(LOCAL_TZ).date().isoformat(),
        "timezone":"Africa/Djibouti","source_fixtures":len(fixtures),"fixtures_with_1xbet_odds":len(odds_fixtures),
        "fixtures_with_complete_1x2":len(complete_ids),"teams_with_recent_history":sum(bool(v) for v in histories.values()),
        "fixtures_with_statistics":sum(bool(v) for v in collected_stats.values()),
        "head_to_head_fixtures_collected":sum(bool(v) for v in head_to_head.values()),
        "history_policy":{"per_team_last_matches":10,"head_to_head_matches":5},"bookmaker":"1xBet",
        "model":"recent_10_matches_poisson_plus_1xbet","market_weight":market_weight,"coupon":selected,
        "status":"ready" if selected else "no_eligible_matches",
        "warning":"Baseline sur les dix derniers matchs disponibles, combiné à 65 % au marché 1xBet. Modèle non encore validé par backtest; aucun résultat n'est garanti."}

def render_message(report: dict[str, Any]) -> str:
    lines = ["⚽ ANALYSE FOOTBALL CODEX — MARCHÉS DU JOUR",f"Date Djibouti : {report['local_date']} | Source cotes : 1xBet",f"Matchs API : {report['source_fixtures']} | Cotes 1xBet : {report['fixtures_with_1xbet_odds']} | Historique : {report.get('teams_with_recent_history', 0)} équipes",""]
    legs = report.get("coupon") or []
    if not legs: lines.append("Aucune sélection : aucun marché éligible disponible chez 1xBet pour les matchs à venir.")
    for i, item in enumerate(legs,1):
        kickoff = datetime.fromisoformat(item["kickoff"]).astimezone(LOCAL_TZ).strftime("%H:%M")
        lines.append(f"{i}. {item['home']} – {item['away']} ({kickoff}, {item['league']})")
        averages = item.get("history_averages") or {}
        for side, label in (("home", item["home"]), ("away", item["away"])):
            summary = averages.get(side) or {}
            def fmt_avg(key):
                value = summary.get(key)
                return f"{value:.1f}" if isinstance(value, (int, float)) else "N/D"
            lines.append(
                f"   Historique 10 matchs — {label}: buts {fmt_avg('goals_for_mean')}, "
                f"corners {fmt_avg('corners_mean')}, tirs {fmt_avg('shots_mean')}, "
                f"cadrés {fmt_avg('shots_on_target_mean')}, jaunes {fmt_avg('yellow_cards_mean')} "
                f"(échantillon buts {summary.get('goals_for_n', 0)}, corners {summary.get('corners_n', 0)})"
            )
        if item.get("odds_1xbet"):
            lines.append(f"   1X2 : {item['pick']} — prob. modèle {item['probability']:.0%} | cote {item['selected_odds']:.2f} | edge {item['edge_pct_points']:+.1f} pts | EV {item['expected_value']:+.1%}")
            lines.append(f"   Cotes 1xBet : 1={item['odds_1xbet']['1']:.2f}, X={item['odds_1xbet']['x']:.2f}, 2={item['odds_1xbet']['2']:.2f}")
        markets = item.get("markets") or []
        if markets:
            supported = [m for m in markets if m.get("expected_value") is not None]
            supported.sort(key=lambda m: m["expected_value"], reverse=True)
            for market in supported[:5]:
                line = f" {market['line']}" if market.get("line") is not None else ""
                lines.append(f"   {market['market']}{line} — {market['selection']} | cote {market['odds']:.2f} | modèle {market['model_probability']:.0%} | edge {market['edge_pct_points']:+.1f} pts | EV {market['expected_value']:+.1%}")
            unsupported = sorted({m["market"] for m in markets if m.get("expected_value") is None})
            if unsupported:
                lines.append("   Cotes sans modèle indépendant (edge non calculé) : " + ", ".join(unsupported))
    lines += ["", "Marchés selon disponibilité 1xBet : 1X2, double chance, buts, BTTS (les deux équipes marquent), handicap, corners, tirs et cartons jaunes.", "⚖️ Le 1X2 combine 65 % marché + 35 % forme récente (Poisson). Les autres probabilités sont normalisées depuis les cotes 1xBet; modèle non validé par backtest, aucun résultat garanti."]
    return "\n".join(lines)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",default=datetime.now(LOCAL_TZ).date().isoformat(),help="Date locale Djibouti YYYY-MM-DD")
    parser.add_argument("--max-legs",type=int,default=8)
    parser.add_argument("--max-history-stat-fixtures",type=int,default=0,
                        help="Maximum unique historical fixture-statistics API calls; 0 means all available historical fixtures")
    parser.add_argument("--market-weight",type=float,default=0.65)
    parser.add_argument("--output",type=Path,default=Path("artifacts/daily_coupon.json"))
    parser.add_argument("--send",action="store_true",help="Send the real result to Telegram")
    args=parser.parse_args()
    fixtures=api_get("fixtures",{"date":args.date,"timezone":"Africa/Djibouti"})
    all_fixture_rows=fixtures.get("response") or []
    fixture_rows=filter_priority_fixtures(all_fixture_rows)
    fixtures={**fixtures,"response":fixture_rows}
    print(f"Filtre compétitions : {len(fixture_rows)}/{len(all_fixture_rows)} matchs conservés (5 grands championnats, Ligue des champions UEFA, grands clubs européens).")
    odds_first=api_get("odds",{"date":args.date,"page":"1"})
    paging=odds_first.get("paging") or {}
    try: pages=min(50,max(1,int(paging.get("total",1))))
    except (TypeError,ValueError): pages=1
    all_odds=list(odds_first.get("response") or [])
    for page in range(2,pages+1): all_odds.extend(api_get("odds",{"date":args.date,"page":str(page)}).get("response") or [])
    team_ids=set()
    for row in fixture_rows:
        teams=row.get("teams") or {}
        for side in ("home","away"):
            tid=(teams.get(side) or {}).get("id")
            if tid is not None: team_ids.add(int(tid))
    histories={}
    # Bounded collection: 10 recent matches per team and 5 H2H per fixture.
    for tid in sorted(team_ids)[:250]:
        histories[str(tid)]=(api_get("fixtures",{"team":str(tid),"last":"10","timezone":"Africa/Djibouti"}).get("response") or [])
    head_to_head={}
    for row in fixture_rows:
        fid=(row.get("fixture") or {}).get("id")
        teams=row.get("teams") or {}
        home_id=(teams.get("home") or {}).get("id")
        away_id=(teams.get("away") or {}).get("id")
        if fid is None or home_id is None or away_id is None: continue
        try:
            head_to_head[str(fid)] = (
                api_get("fixtures", {"h2h": f"{home_id}-{away_id}", "last": "5",
                                     "timezone": "Africa/Djibouti"}).get("response") or []
            )
        except ApiFootballResponseError as exc:
            # H2H is supplementary: a provider validation error must not abort
            # today's 1xBet availability check or the last-ten statistics run.
            print(f"H2H indisponible pour fixture {fid}; collecte principale continue ({exc}).")
            head_to_head[str(fid)] = []
    # Pull full match statistics for unique historical fixtures, deduplicated across both teams.
    historical_fixture_rows = {}
    for team_rows in histories.values():
        for hist_row in _completed_matches(team_rows, 10):
            hist_fid = (hist_row.get("fixture") or {}).get("id")
            if hist_fid is not None:
                historical_fixture_rows[str(hist_fid)] = hist_row
    history_stats = {}
    ranked_history = sorted(historical_fixture_rows.items(),
                            key=lambda pair: str((pair[1].get("fixture") or {}).get("date") or ""),
                            reverse=True)
    history_stats_limit = len(ranked_history) if args.max_history_stat_fixtures == 0 else min(
        len(ranked_history), max(0, args.max_history_stat_fixtures))
    for hist_fid, _ in ranked_history[:history_stats_limit]:
        history_stats[hist_fid] = _parse_fixture_statistics(
            api_get("fixtures/statistics", {"fixture": hist_fid}).get("response") or [])
    collected_stats={}
    for row in fixture_rows[:100]:
        fid=(row.get("fixture") or {}).get("id")
        if fid is not None:
            collected_stats[str(fid)]=_parse_fixture_statistics(
                api_get("fixtures/statistics",{"fixture":str(fid)}).get("response") or [])
    report=build_live_report(fixtures,{"response":all_odds},histories=histories,
        collected_stats=collected_stats,history_stats=history_stats,
        max_legs=args.max_legs,market_weight=args.market_weight)
    report["historical_statistics_collection"] = {
        "unique_completed_fixtures_available": len(historical_fixture_rows),
        "fixtures_with_statistics_requested": len(history_stats),
        "fixtures_with_statistics_data": sum(bool(v) for v in history_stats.values()),
        "max_history_stat_fixtures": history_stats_limit,
        "statistics_fields": sorted(STAT_ALIASES.values()),
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    message=render_message(report); print(message)
    if args.send and report["coupon"]:
        result=send_message(message,token=os.environ.get("TELEGRAM_BOT_TOKEN",""),chat_id=os.environ.get("TELEGRAM_CHAT_ID",""))
        print(f"Telegram envoyé : message_id={result['result']['message_id']}")
    elif args.send: print("Aucun message envoyé : aucune sélection éligible.")
    else: print("DRY RUN : aucun message Telegram envoyé.")
    print(f"Rapport sauvegardé : {args.output}")
    return 0
if __name__=="__main__": raise SystemExit(main())
