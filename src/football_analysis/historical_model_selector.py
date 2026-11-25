"""Historical, per-market model comparison migrated from the read-only reference.

This is a pure/offline evaluation helper. It consumes already-graded outcomes and
must not be used to pick a model from a sample that is too small. A winner is
based on ROI, with chronological split stability reported separately.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite, log
from typing import Any

RESULTS = {
    "win": "win", "won": "win", "gagne": "win", "gagné": "win",
    "loss": "loss", "lost": "loss", "perdu": "loss",
    "push": "push", "refund": "push", "rembourse": "push",
}
MIN_DECISION_ROWS = 30
MIN_ROI_DIFFERENCE = 0.01


def _graded_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep rows with a recognized graded result, valid probability, and date text."""
    valid = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        outcome = RESULTS.get(str(row.get("result") or row.get("resultat") or "").strip().lower())
        if outcome is None:
            continue
        raw_probability = row.get("probability", row.get("proba_pct"))
        try:
            probability = float(raw_probability)
        except (TypeError, ValueError):
            continue
        raw_odds = row.get("decimal_odds", row.get("cote"))
        try:
            odds = float(raw_odds) if raw_odds is not None else None
        except (TypeError, ValueError):
            odds = None
        if not isfinite(probability) or not 0 <= probability <= 1:
            # Legacy French records use percent. Accept only explicitly named proba_pct.
            try:
                probability = float(row.get("proba_pct")) / 100
            except (TypeError, ValueError):
                continue
        if not isfinite(probability) or not 0 <= probability <= 1:
            continue
        if odds is not None and (not isfinite(odds) or odds <= 1):
            odds = None
        valid.append({**row, "_outcome": outcome, "_probability": probability, "_odds": odds,
                     "_date": str(row.get("date") or row.get("jour") or row.get("kickoff") or row.get("horodatage") or "")})
    return valid


def _metrics(rows: Sequence[Mapping[str, Any]], n_min: int) -> dict[str, Any]:
    graded = _graded_rows(rows)
    n = len(graded)
    settled = [row for row in graded if row["_outcome"] != "push"]
    scored = [(row["_probability"], 1 if row["_outcome"] == "win" else 0) for row in settled]
    brier = sum((probability - actual) ** 2 for probability, actual in scored) / len(scored) if scored else None
    epsilon = 1e-15
    log_loss = (\n        sum(\n            -actual * log(max(probability, epsilon))\n            -(1 - actual) * log(max(1 - probability, epsilon))\n            for probability, actual in scored\n        ) / len(scored) if scored else None\n    )
    calibration = []
    for index in range(10):
        lower, upper = index / 10, (index + 1) / 10
        sample = [(p, y) for p, y in scored if lower <= p < upper or (index == 9 and p == 1.0)]
        if sample:
            calibration.append({"bin": f"{lower:.1f}-{upper:.1f}", "n": len(sample),
                               "mean_probability": round(sum(p for p, _ in sample) / len(sample), 4),
                               "observed_rate": round(sum(y for _, y in sample) / len(sample), 4)})
    wins = sum(row["_outcome"] == "win" for row in settled)
    bets = [row for row in settled if row["_odds"] is not None]
    profit = sum(row["_odds"] - 1 if row["_outcome"] == "win" else -1 for row in bets)
    edge = [(row["_probability"] * row["_odds"] - 1) for row in bets]
    metrics = {"available": n >= n_min, "n": n, "n_bets": len(bets), "wins": wins,
               "win_rate": round(wins / len(settled), 4) if settled else None,
               "brier": round(brier, 4) if brier is not None else None,
               "log_loss": round(log_loss, 4) if log_loss is not None else None,
               "calibration": calibration,
               "mean_edge": round(sum(edge) / len(edge), 4) if edge else None,
               "profit_units": round(profit, 4) if bets else None,
               "roi": round(profit / len(bets), 4) if bets else None,
               "n_min": n_min}
    if n < n_min:
        metrics["reason"] = f"insufficient graded sample ({n} < {n_min})"
    elif not bets:
        metrics["reason"] = "no settled bets with valid odds"
    return metrics


def _winner(roi_a: float | None, roi_b: float | None, model_a: str, model_b: str) -> str | None:
    if roi_a is None or roi_b is None or abs(roi_a - roi_b) < MIN_ROI_DIFFERENCE:
        return "tie" if roi_a is not None and roi_b is not None else None
    return model_a if roi_a > roi_b else model_b


def _chronological_halves(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graded = _graded_rows(rows)
    ordered = sorted(graded, key=lambda row: row["_date"])
    midpoint = len(ordered) // 2
    return ordered[:midpoint], ordered[midpoint:]


def compare_market(
    rows_a: Sequence[Mapping[str, Any]],
    rows_b: Sequence[Mapping[str, Any]],
    *,
    model_a: str = "model_a",
    model_b: str = "model_b",
    n_min: int = MIN_DECISION_ROWS,
) -> dict[str, Any]:
    """Compare two model histories for one market using settled ROI only.

    Returns no decision below the sample threshold. Stability is reported only
    when both chronological halves have sufficient rows; it does not replace an
    independent holdout/walk-forward evaluation.
    """
    if isinstance(n_min, bool) or not isinstance(n_min, int) or n_min < 2:
        raise ValueError("n_min must be an integer >= 2")
    metrics_a, metrics_b = _metrics(rows_a, n_min), _metrics(rows_b, n_min)
    if not (metrics_a["available"] and metrics_b["available"]):
        return {"decision": "unavailable", "reason": "insufficient historical sample for one or both models",
                "model_a": metrics_a, "model_b": metrics_b, "stable": None}
    if metrics_a["roi"] is None or metrics_b["roi"] is None:
        return {"decision": "unavailable", "reason": "ROI unavailable because no settled bets have valid odds for one or both models",
                "model_a": metrics_a, "model_b": metrics_b, "stable": None}
    decision = _winner(metrics_a["roi"], metrics_b["roi"], model_a, model_b)
    split_a1, split_a2 = _chronological_halves(rows_a)
    split_b1, split_b2 = _chronological_halves(rows_b)
    half_min = max(n_min // 2, 1)
    halves = [_metrics(split_a1, half_min), _metrics(split_b1, half_min),
              _metrics(split_a2, half_min), _metrics(split_b2, half_min)]
    stable = None
    dates_complete = all(row["_date"] for row in _graded_rows(rows_a) + _graded_rows(rows_b))
    if dates_complete and all(m["available"] and m["roi"] is not None for m in halves):
        first = _winner(halves[0]["roi"], halves[1]["roi"], model_a, model_b)
        second = _winner(halves[2]["roi"], halves[3]["roi"], model_a, model_b)
        stable = first == decision and second == decision
    return {"decision": decision, "reason": f"ROI comparison ({model_a}: {metrics_a['roi']:+.1%}; {model_b}: {metrics_b['roi']:+.1%})",
            "model_a": metrics_a, "model_b": metrics_b, "stable": stable,
            "stability_note": "chronological halves are diagnostic, not an independent holdout"}


def select_by_market(
    rows_a: Mapping[str, Sequence[Mapping[str, Any]]],
    rows_b: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    model_a: str = "model_a",
    model_b: str = "model_b",
    n_min: int = MIN_DECISION_ROWS,
) -> dict[str, dict[str, Any]]:
    """Compare each market independently; absent model histories stay unavailable."""
    markets = sorted(set(rows_a or {}) | set(rows_b or {}))
    return {market: compare_market((rows_a or {}).get(market, ()), (rows_b or {}).get(market, ()),
                                  model_a=model_a, model_b=model_b, n_min=n_min)
            for market in markets}
