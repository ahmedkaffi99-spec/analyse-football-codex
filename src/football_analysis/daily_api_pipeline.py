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
from .competitions import filter_priority_fixtures
from .markets import normalize_implied_probabilities
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


def build_live_report(fixtures_response: dict[str, Any], odds_response: dict[str, Any], *, histories: dict[str, list[dict[str, Any]]] | None = None, head_to_head: dict[str, list[dict[str, Any]]] | None = None, collected_stats: dict[str, Any] | None = None, max_legs: int = 8, market_weight: float = 0.65) -> dict[str, Any]:
    if not 1 <= max_legs <= 20: raise ValueError("max_legs must be between 1 and 20")
    if not 0.0 <= market_weight <= 1.0: raise ValueError("market_weight must be between 0 and 1")
    histories, head_to_head, collected_stats = histories or {}, head_to_head or {}, collected_stats or {}
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
        selected.append({**fixtures[fid], "market":"1X2", "pick":pick,
            "pick_label":{"1":"Victoire domicile","x":"Match nul","2":"Victoire extérieur"}[pick],
            "probability":round(combined[pick],4), "probabilities_combined":{k:round(v,6) for k,v in combined.items()},
            "probabilities_1xbet_normalized":{k:round(v,6) for k,v in market_probs.items()},
            "probabilities_recent_form":{k:round(v,6) for k,v in model_probs.items()},
            "recent_form_sample":{"home":hn,"away":an}, "estimated_goals":{"home":round(home_xg,3),"away":round(away_xg,3)},
            "last_10_home_team_matches":home_history, "last_10_away_team_matches":away_history,
            "last_5_head_to_head":h2h_history,
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
        "model":"recent_5_matches_poisson_plus_1xbet","market_weight":market_weight,"coupon":selected,
        "status":"ready" if selected else "no_eligible_matches",
        "warning":"Baseline sur les dix derniers matchs disponibles, combiné à 65 % au marché 1xBet. Modèle non encore validé par backtest; aucun résultat n'est garanti."}

def render_message(report: dict[str, Any]) -> str:
    lines = ["⚽ ANALYSE FOOTBALL CODEX — MARCHÉS DU JOUR",f"Date Djibouti : {report['local_date']} | Source cotes : 1xBet",f"Matchs API : {report['source_fixtures']} | Cotes 1xBet : {report['fixtures_with_1xbet_odds']} | Historique : {report.get('teams_with_recent_history', 0)} équipes",""]
    legs = report.get("coupon") or []
    if not legs: lines.append("Aucune sélection : aucun marché éligible disponible chez 1xBet pour les matchs à venir.")
    for i, item in enumerate(legs,1):
        kickoff = datetime.fromisoformat(item["kickoff"]).astimezone(LOCAL_TZ).strftime("%H:%M")
        lines.append(f"{i}. {item['home']} – {item['away']} ({kickoff}, {item['league']})")
        if item.get("odds_1xbet"):
            lines.append(f"   1X2 : {item['pick']} — probabilité combinée {item['probability']:.0%} | cotes 1={item['odds_1xbet']['1']:.2f}, X={item['odds_1xbet']['x']:.2f}, 2={item['odds_1xbet']['2']:.2f}")
        markets = item.get("markets") or []
        if markets:
            for market in markets:
                line = f" ligne {market['line']}" if market.get("line") is not None else ""
                lines.append(f"   {market['market']}{line} : {market['selection']} | cote {market['odds']:.2f} | prob. marché {market['probability']:.0%}")
        else:
            lines.append("   Aucun autre marché reconnu fourni pour ce match.")
    lines += ["", "Marchés selon disponibilité 1xBet : 1X2, double chance, buts, BTTS (les deux équipes marquent), handicap, corners, tirs et cartons jaunes.", "⚖️ Le 1X2 combine 65 % marché + 35 % forme récente (Poisson). Les autres probabilités sont normalisées depuis les cotes 1xBet; modèle non validé par backtest, aucun résultat garanti."]
    return "\n".join(lines)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",default=datetime.now(LOCAL_TZ).date().isoformat(),help="Date locale Djibouti YYYY-MM-DD")
    parser.add_argument("--max-legs",type=int,default=8)
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
        head_to_head[str(fid)]=(api_get("fixtures",{"h2h":f"{home_id}-{away_id}","last":"5","timezone":"Africa/Djibouti"}).get("response") or [])
    collected_stats={}
    for row in fixture_rows[:100]:
        fid=(row.get("fixture") or {}).get("id")
        if fid is not None: collected_stats[str(fid)]=(api_get("fixtures/statistics",{"fixture":str(fid)}).get("response") or [])
    report=build_live_report(fixtures,{"response":all_odds},histories=histories,collected_stats=collected_stats,max_legs=args.max_legs,market_weight=args.market_weight)
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
