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
from .markets import normalize_implied_probabilities
from .telegram_publisher import send_message

LOCAL_TZ = ZoneInfo("Asia/Djibouti")

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

def build_live_report(fixtures_response: dict[str, Any], odds_response: dict[str, Any], *, max_legs: int = 8) -> dict[str, Any]:
    if not 1 <= max_legs <= 20: raise ValueError("max_legs must be between 1 and 20")
    fixtures = _fixture_map(fixtures_response.get("response") or [])
    odds_rows = only_target_bookmaker(odds_response.get("response") or [])
    selected, odds_fixtures, complete_ids = [], set(), set()
    for row in odds_rows:
        fid = str(((row.get("fixture") or {}).get("id") or ""))
        if fid not in fixtures: continue
        odds_fixtures.add(fid)
        market = _market_1x2(row)
        if not market: continue
        complete_ids.add(fid)
        probs = normalize_implied_probabilities(market)
        pick = max(probs, key=probs.get)
        selected.append({**fixtures[fid],"market":"1X2","pick":pick,"pick_label":{"1":"Victoire domicile","x":"Match nul","2":"Victoire extérieur"}[pick],"probability":round(probs[pick],4),"odds_1xbet":market,"probabilities_1xbet_normalized":{k:round(v,6) for k,v in probs.items()},"model":"1xbet_de_vigged_market_baseline"})
    selected.sort(key=lambda x:(-x["probability"],x["kickoff"],x["match_id"]))
    selected = selected[:max_legs]
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"local_date":datetime.now(LOCAL_TZ).date().isoformat(),"timezone":"Asia/Djibouti","source_fixtures":len(fixtures),"fixtures_with_1xbet_odds":len(odds_fixtures),"fixtures_with_complete_1x2":len(complete_ids),"bookmaker":"1xBet","model":"1xbet_de_vigged_market_baseline","market_weight":1.0,"coupon":selected,"status":"ready" if selected else "no_eligible_matches","warning":"Sélection basée sur les cotes 1xBet normalisées, pas sur un modèle ML validé. Les probabilités ne garantissent aucun résultat."}

def render_message(report: dict[str, Any]) -> str:
    lines = ["⚽ ANALYSE FOOTBALL CODEX — MATCHS DU JOUR",f"Date Djibouti : {report['local_date']} | Source cotes : 1xBet",f"Matchs API : {report['source_fixtures']} | Avec cotes 1xBet : {report['fixtures_with_1xbet_odds']}",""]
    legs = report.get("coupon") or []
    if not legs: lines.append("Aucune sélection éligible : pas de marché 1X2 complet 1xBet pour les matchs à venir.")
    for i, item in enumerate(legs,1):
        kickoff = datetime.fromisoformat(item["kickoff"]).astimezone(LOCAL_TZ).strftime("%H:%M")
        lines += [f"{i}. {item['home']} – {item['away']} ({kickoff}, {item['league']})",f"   Choix 1X2 : {item['pick']} — {item['pick_label']} | Probabilité marché ajustée : {item['probability']:.0%}",f"   Cotes 1xBet : 1={item['odds_1xbet']['1']:.2f} | X={item['odds_1xbet']['x']:.2f} | 2={item['odds_1xbet']['2']:.2f}"]
    lines += ["","⚠️ Basé sur le marché 1xBet, pas un modèle ML validé. Aucun résultat n'est garanti."]
    return "\n".join(lines)

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",default=datetime.now(LOCAL_TZ).date().isoformat(),help="Date locale Djibouti YYYY-MM-DD")
    parser.add_argument("--max-legs",type=int,default=8)
    parser.add_argument("--output",type=Path,default=Path("artifacts/daily_coupon.json"))
    parser.add_argument("--send",action="store_true",help="Send the real result to Telegram")
    args=parser.parse_args()
    fixtures=api_get("fixtures",{"date":args.date})
    odds_first=api_get("odds",{"date":args.date,"page":"1"})
    paging=odds_first.get("paging") or {}
    try: pages=min(50,max(1,int(paging.get("total",1))))
    except (TypeError,ValueError): pages=1
    all_odds=list(odds_first.get("response") or [])
    for page in range(2,pages+1): all_odds.extend(api_get("odds",{"date":args.date,"page":str(page)}).get("response") or [])
    report=build_live_report(fixtures,{"response":all_odds},max_legs=args.max_legs)
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
