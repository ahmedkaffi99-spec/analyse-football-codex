"""Offline candidate filtering and coupon preview migrated/adapted from the reference.

Selection is deterministic and side-effect free. Unknown/non-binary markets are
rejected by default; this is a research preview, not a betting executor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RiskConfig:
    coupon_min: int = 2
    coupon_max: int = 8
    max_per_fixture: int = 1
    odds_min: float = 1.01
    odds_max: float = 10.0
    probability_min: float = 0.0
    edge_min: float | None = None
    edge_max: float | None = None
    allowed_markets: frozenset[str] = field(default_factory=frozenset)
    excluded_markets: frozenset[str] = field(default_factory=frozenset)
    require_calibration: bool = False
    calibration_min_n: int = 30

    def __post_init__(self) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (self.coupon_min, self.coupon_max)):
            raise ValueError("coupon leg limits must be integers")
        if not 1 <= self.coupon_min <= self.coupon_max:
            raise ValueError("coupon leg limits must satisfy 1 <= min <= max")
        if isinstance(self.max_per_fixture, bool) or not isinstance(self.max_per_fixture, int) or self.max_per_fixture < 1:
            raise ValueError("max_per_fixture must be an integer >= 1")
        if not isfinite(self.odds_min) or not isfinite(self.odds_max) or self.odds_min <= 1 or self.odds_max < self.odds_min:
            raise ValueError("invalid decimal-odds bounds")
        if not isfinite(self.probability_min) or not 0 <= self.probability_min <= 1:
            raise ValueError("probability_min must be in [0, 1]")
        for label, value in (("edge_min", self.edge_min), ("edge_max", self.edge_max)):
            if value is not None and not isfinite(value):
                raise ValueError(f"{label} must be finite")
        if self.edge_min is not None and self.edge_max is not None and self.edge_min > self.edge_max:
            raise ValueError("edge_min must not exceed edge_max")
        if isinstance(self.calibration_min_n, bool) or not isinstance(self.calibration_min_n, int) or self.calibration_min_n < 1:
            raise ValueError("calibration_min_n must be an integer >= 1")


def _candidate_reasons(candidate: Mapping[str, Any], config: RiskConfig) -> list[str]:
    reasons: list[str] = []
    fixture = str(candidate.get("fixture_id") or candidate.get("match_id") or "").strip()
    market = str(candidate.get("market") or candidate.get("category") or "").strip()
    if not fixture:
        reasons.append("missing fixture id")
    if not market:
        reasons.append("missing market label")
    if not str(candidate.get("selection") or "").strip():
        reasons.append("missing selection label")
    if not candidate.get("binary", False):
        reasons.append("market not confirmed binary (push/refund possible)")
    if config.allowed_markets and market not in config.allowed_markets:
        reasons.append("market not allowlisted")
    if market in config.excluded_markets:
        reasons.append("market excluded")
    try:
        odds = float(candidate.get("decimal_odds"))
        if not isfinite(odds) or not config.odds_min <= odds <= config.odds_max:
            reasons.append(f"odds outside [{config.odds_min}, {config.odds_max}]")
    except (TypeError, ValueError):
        reasons.append("missing/invalid odds")
    try:
        probability = float(candidate.get("probability"))
        if not isfinite(probability) or not 0 <= probability <= 1:
            reasons.append("invalid probability")
        elif probability < config.probability_min:
            reasons.append("probability below minimum")
    except (TypeError, ValueError):
        reasons.append("missing/invalid probability")
    edge = candidate.get("edge")
    if edge is not None:
        try:
            edge = float(edge)
            if not isfinite(edge):
                reasons.append("invalid edge")
            elif config.edge_min is not None and edge < config.edge_min:
                reasons.append("edge below minimum")
            elif config.edge_max is not None and edge > config.edge_max:
                reasons.append("edge above maximum (suspicious)")
        except (TypeError, ValueError):
            reasons.append("invalid edge")
    elif config.edge_min is not None or config.edge_max is not None:
        reasons.append("edge unavailable while edge filter enabled")
    if config.require_calibration:
        if not candidate.get("calibrated", False):
            reasons.append("calibration required")
        try:
            sample_n = int(candidate.get("calibration_n", 0))
            if sample_n < config.calibration_min_n:
                reasons.append(f"calibration sample too small ({sample_n} < {config.calibration_min_n})")
        except (TypeError, ValueError):
            reasons.append("invalid calibration sample size")
    return reasons


def select_coupon_preview(
    candidates: Sequence[Mapping[str, Any]],
    config: RiskConfig = RiskConfig(),
) -> dict[str, Any]:
    """Validate candidates, rank deterministically, and build a preview or reject it.

    Ranking uses probability then edge (if available), not a fitted weighting.
    The default cap is one selection per fixture, avoiding unknown same-match
    correlation. Duplicate market/line/selection keys are never admitted.
    """
    accepted, rejected = [], []
    for candidate in candidates or ():
        reasons = _candidate_reasons(candidate, config)
        record = dict(candidate)
        if reasons:
            record["rejection_reasons"] = reasons
            rejected.append(record)
        else:
            record["rejection_reasons"] = []
            accepted.append(record)
    accepted.sort(key=lambda c: (float(c["probability"]), float(c.get("edge") or 0)), reverse=True)
    selected, seen_fixture, seen_pick = [], set(), set()
    for candidate in accepted:
        if len(selected) >= config.coupon_max:
            candidate["rejection_reasons"] = ["coupon leg cap reached"]
            rejected.append(candidate)
            continue
        fixture = str(candidate.get("fixture_id") or candidate.get("match_id")).strip()
        pick_key = (fixture, str(candidate.get("market") or candidate.get("category") or "").strip(),
                    str(candidate.get("selection") or "").strip().casefold(), candidate.get("line"))
        if fixture in seen_fixture and config.max_per_fixture <= 1:
            candidate["rejection_reasons"] = ["fixture already represented in preview"]
            rejected.append(candidate)
            continue
        if pick_key in seen_pick:
            candidate["rejection_reasons"] = ["duplicate pick key"]
            rejected.append(candidate)
            continue
        if sum(1 for item in selected if str(item.get("fixture_id") or item.get("match_id")).strip() == fixture) >= config.max_per_fixture:
            candidate["rejection_reasons"] = ["fixture leg cap reached"]
            rejected.append(candidate)
            continue
        selected.append(candidate)
        seen_fixture.add(fixture)
        seen_pick.add(pick_key)
        if len(selected) >= config.coupon_max:
            break
    if len(selected) < config.coupon_min:
        return {"generated": False, "selections": [], "accepted_count": len(accepted),
                "rejected": rejected, "reason": f"not enough safe candidates ({len(selected)} < {config.coupon_min})"}
    total_odds = 1.0
    combined_probability = 1.0
    for candidate in selected:
        total_odds *= float(candidate["decimal_odds"])
        combined_probability *= float(candidate["probability"])
    return {"generated": True, "selections": selected, "accepted_count": len(accepted),
            "rejected": rejected, "total_odds": round(total_odds, 4),
            "combined_probability": combined_probability,
            "independence_assumption": "fixture-level cap; cross-fixture independence is assumed"}
