"""Offline league/season coverage audit; never calls external APIs or a database."""
from __future__ import annotations
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

STAT_FIELDS = ("home_goals", "away_goals", "shots", "shots_on_target", "corners",
               "cards", "possession", "xg", "xga", "lineups", "injuries", "odds_1xbet")

def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "null", "none", "nan", "n/a"}
    return True  # Numeric zero is a valid observation, not missing data.

def audit_coverage(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize fixture and field coverage by league/season."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    duplicates: dict[tuple[str, str], int] = defaultdict(int)
    for index, row in enumerate(rows, start=1):
        league, season, fixture_id = (str(row.get(k) or "").strip()
                                      for k in ("league", "season", "fixture_id"))
        if not league or not season or not fixture_id:
            raise ValueError(f"row {index}: league, season and fixture_id are required")
        key = (league, season)
        if fixture_id in seen[key]:
            duplicates[key] += 1
            continue
        seen[key].add(fixture_id)
        groups[key].append(row)
    reports = []
    for (league, season), items in sorted(groups.items()):
        total = len(items)
        finished = sum(str(row.get("status") or "").strip().upper()
                       in {"FT", "AET", "PEN", "FINISHED"} for row in items)
        fields = {}
        for field in STAT_FIELDS:
            count = sum(_present(row.get(field)) for row in items)
            fields[field] = {"available": count, "total": total,
                             "coverage_pct": round(100 * count / total, 2) if total else 0.0}
        reports.append({"league": league, "season": season, "fixtures_unique": total,
                        "finished_fixtures": finished,
                        "finished_pct": round(100 * finished / total, 2) if total else 0.0,
                        "duplicate_rows": duplicates[(league, season)], "fields": fields})
    return {"groups": reports, "group_count": len(reports)}

def load_rows(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.casefold() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))
    if path.suffix.casefold() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("rows", payload.get("response", payload))
        if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
            raise ValueError("JSON must contain a list of fixture objects (or rows/response list)")
        return payload
    raise ValueError("input must be a .csv or .json file")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Offline CSV or JSON export; no API calls are made")
    parser.add_argument("--output", help="Write report JSON to this path")
    args = parser.parse_args()
    rendered = json.dumps(audit_coverage(load_rows(args.input)), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

if __name__ == "__main__":
    main()

def audit_pipeline_coverage(fixtures, odds_fixture_ids=(), market_fixture_ids=(),
                           candidate_fixture_ids=(), selected_fixture_ids=(),
                           exclusion_reasons=None):
    """Trace fixture coverage across pipeline stages; inputs are fixture mappings with fixture_id.

    Every discovered fixture gets a final status: selected, excluded (reason), no odds,
    no markets, or no candidate. No external calls or persistence.
    """
    exclusion_reasons=exclusion_reasons or {}
    indexed={}
    for row in fixtures:
        fid=str(row.get("fixture_id") or "").strip()
        if not fid: raise ValueError("every fixture requires fixture_id")
        if fid in indexed: raise ValueError(f"duplicate fixture_id: {fid}")
        indexed[fid]=row
    odds=set(map(str,odds_fixture_ids))
    markets=set(map(str,market_fixture_ids))
    candidates=set(map(str,candidate_fixture_ids))
    selected=set(map(str,selected_fixture_ids))
    report=[]
    for fid,row in indexed.items():
        if fid in selected: status="selected"; reason=None
        elif fid in exclusion_reasons: status="excluded"; reason=str(exclusion_reasons[fid])
        elif fid not in odds: status="missing_odds"; reason="No odds fixture matched"
        elif fid not in markets: status="missing_markets"; reason="No usable markets"
        elif fid not in candidates: status="no_candidates"; reason="Markets did not pass candidate filters"
        else: status="not_selected"; reason="Candidate available but not selected"
        report.append({"fixture_id":fid,"home":row.get("home"),"away":row.get("away"),
                      "competition":row.get("competition"),"status":status,"reason":reason,
                      "has_odds":fid in odds,"has_markets":fid in markets,
                      "has_candidates":fid in candidates,"selected":fid in selected})
    counts={}
    for row in report: counts[row["status"]]=counts.get(row["status"],0)+1
    return {"fixtures_total":len(report),"counts":counts,"fixtures":report}
