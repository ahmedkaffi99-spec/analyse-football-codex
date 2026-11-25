"""Offline dynamic coupon sizing and cross-coupon match uniqueness.

Adapted from the read-only reference system's 11/10/2026 dynamic coupon sizing.
This module only sizes research previews; it never submits bets or publishes messages.
"""
from __future__ import annotations

from typing import Any

MIN_LEGS_PER_COUPON = 2
MAX_LEGS_PER_COUPON = 5
COUPON_COUNT_TIERS = ((2, 1), (6, 2), (10, 3), (16, 4), (20, 5))
MEDALS = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣")


def coupon_count_for_matches(eligible_matches: int) -> int:
    """Return 0–5 coupons based on the number of distinct eligible fixtures."""
    if isinstance(eligible_matches, bool) or not isinstance(eligible_matches, int):
        raise ValueError("eligible_matches must be an integer")
    if eligible_matches < 0:
        raise ValueError("eligible_matches must be non-negative")
    count = 0
    for threshold, value in COUPON_COUNT_TIERS:
        if eligible_matches >= threshold:
            count = value
    return count


def build_dynamic_profiles(eligible_matches: int) -> list[dict[str, Any]]:
    """Build deterministic profiles; never request more selections than the real pool."""
    count = coupon_count_for_matches(eligible_matches)
    if count == 0:
        return []
    leg_budget = max(
        MIN_LEGS_PER_COUPON,
        min(MAX_LEGS_PER_COUPON, eligible_matches // count),
    )
    return [
        {
            "key": f"coupon_{index + 1}",
            "label": f"{MEDALS[index]} COUPON #{index + 1}",
            "min_legs": MIN_LEGS_PER_COUPON,
            "max_legs": leg_budget,
        }
        for index in range(count)
    ]


def verify_cross_coupon_match_uniqueness(coupons: list[dict[str, Any]]) -> None:
    """Raise if any fixture ID is repeated, including duplicates within one coupon."""
    seen: dict[str, str] = {}
    for coupon in coupons:
        profile = str(coupon.get("profile") or coupon.get("key") or "unknown")
        for selection in coupon.get("selections") or []:
            match_id = str(selection.get("match_id") or "").strip()
            if not match_id:
                raise ValueError(f"coupon {profile} contains a selection without match_id")
            if match_id in seen:
                raise ValueError(
                    f"match_id {match_id!r} appears in both {seen[match_id]} and {profile}"
                )
            seen[match_id] = profile
