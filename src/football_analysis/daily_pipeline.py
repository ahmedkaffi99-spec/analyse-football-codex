"""Single entry point for preparing a daily 1X2 coupon preview.

This module is deliberately offline-first. It consumes explicitly supplied fixtures
and expected-goal estimates; it does not invent fixtures or fetch live odds.
Telegram delivery is a separate, opt-in step handled by telegram_publisher.py.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Outcome
from .poisson import poisson_1x2


@dataclass(frozen=True, slots=True)
class FixtureInput:
    match_id: str
    home: str
    away: str
    kickoff: datetime
    home_expected_goals: float
    away_expected_goals: float


def parse_fixture(row: dict[str, Any]) -> FixtureInput:
    required = ("match_id", "home", "away", "kickoff", "home_expected_goals", "away_expected_goals")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"fixture missing fields: {', '.join(missing)}")
    kickoff = datetime.fromisoformat(str(row["kickoff"]).replace("Z", "+00:00"))
    if kickoff.tzinfo is None or kickoff.utcoffset() is None:
        raise ValueError(f"kickoff for {row['match_id']} must include a timezone")
    for key in ("match_id", "home", "away"):
        if not str(row[key]).strip():
            raise ValueError(f"{key} must not be empty")
    return FixtureInput(
        match_id=str(row["match_id"]),
        home=str(row["home"]).strip(),
        away=str(row["away"]).strip(),
        kickoff=kickoff,
        home_expected_goals=float(row["home_expected_goals"]),
        away_expected_goals=float(row["away_expected_goals"]),
    )


def build_daily_coupon(rows: list[dict[str, Any]], *, max_legs: int = 5) -> dict[str, Any]:
    """Build a transparent prediction preview from supplied, pre-match estimates.

    This is not a guarantee of outcomes. Legs are ranked by the highest 1X2
    outcome probability; no market/odds weighting is applied.
    """
    if not 1 <= max_legs <= 20:
        raise ValueError("max_legs must be between 1 and 20")
    fixtures = [parse_fixture(row) for row in rows]
    ids = [fixture.match_id for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate match_id in daily input")

    now = datetime.now().astimezone()
    predictions = []
    for fixture in fixtures:
        if fixture.kickoff <= now:
            continue
        probabilities = poisson_1x2(
            fixture.home_expected_goals, fixture.away_expected_goals
        )
        pick = max(Outcome, key=lambda outcome: probabilities[outcome])
        predictions.append({
            "match_id": fixture.match_id,
            "kickoff": fixture.kickoff.isoformat(),
            "home": fixture.home,
            "away": fixture.away,
            "pick": pick.value,
            "pick_label": {Outcome.HOME: "1", Outcome.DRAW: "X", Outcome.AWAY: "2"}[pick],
            "probability": round(probabilities[pick], 4),
            "probabilities": {key.value: round(value, 6) for key, value in probabilities.items()},
            "model": "independent_poisson_baseline",
        })
    predictions.sort(key=lambda item: (-item["probability"], item["kickoff"], item["match_id"]))
    selected = predictions[:max_legs]
    return {
        "generated_at": now.isoformat(),
        "model": "independent_poisson_baseline",
        "market_weight": 0.0,
        "fixtures_received": len(fixtures),
        "upcoming_fixtures_scored": len(predictions),
        "coupon": selected,
        "status": "preview_only" if selected else "no_upcoming_fixtures",
        "warning": "Prediction estimates are uncertain; this is not a guarantee or financial advice.",
    }


def render_telegram_message(report: dict[str, Any]) -> str:
    legs = report.get("coupon", [])
    if not legs:
        return "⚽ Analyse Football Codex\nAucun match futur exploitable dans les données fournies. Aucun coupon généré."
    lines = [
        "⚽ ANALYSE FOOTBALL — PRÉVISUALISATION",
        f"Modèle : {report['model']} | Influence des cotes : désactivée",
        "",
    ]
    for index, leg in enumerate(legs, 1):
        kickoff = datetime.fromisoformat(leg["kickoff"]).strftime("%d/%m %H:%M")
        lines.append(f"{index}. {leg['home']} – {leg['away']} ({kickoff})")
        lines.append(f"   Pronostic 1X2 : {leg['pick_label']} | Probabilité modèle : {leg['probability']:.0%}")
    lines.extend(["", "⚠️ Estimations incertaines, pas une garantie de résultat."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Single offline daily prediction pipeline")
    parser.add_argument("input", type=Path, help="JSON file containing a list of fixture objects")
    parser.add_argument("--output", type=Path, default=Path("artifacts/daily_coupon.json"))
    parser.add_argument("--max-legs", type=int, default=5)
    args = parser.parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("input JSON must be a list of fixture objects")
    report = build_daily_coupon(rows, max_legs=args.max_legs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(render_telegram_message(report))
    print(f"Rapport écrit dans : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
