"""Daily coupon duplicate cap migrated from the reference repository; pure Python."""
from __future__ import annotations
import os
def cap_enabled()->bool:
    return os.getenv("DAILY_BET_CAP","1").strip().lower() not in {"0","false","no","off"}
def bet_key(match,category,selection,handicap):
    line=None
    if handicap is not None:
        try:line=round(float(handicap),2)
        except (TypeError,ValueError):line=str(handicap)
    return (str(match or "").strip(),str(category or "").strip(),str(selection if selection is not None else "").strip().lower(),line)
def key_from_candidate(candidate):
    pick=candidate.get("pick") or {}
    return bet_key(candidate.get("match"),pick.get("category") or pick.get("categorie"),pick.get("selection"),pick.get("handicap"))
