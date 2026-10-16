"""Extract every supported 1xBet market exposed by API-Football."""
from __future__ import annotations
import re
from typing import Any
from .markets import normalize_implied_probabilities
from .collect_odds import is_target_bookmaker

def _category(name: str) -> str | None:
    n = name.casefold()
    if "double chance" in n: return "double_chance"
    if "both teams to score" in n or "btts" in n or "team to score" in n: return "btts"
    if "corner" in n: return "corners"
    if "yellow card" in n or "yellow cards" in n: return "yellow_cards"
    if "shots on target" in n or "shots on target" in n: return "shots_on_target"
    if "shots" in n: return "shots"
    if "handicap" in n or "asian handicap" in n or "european handicap" in n: return "handicap"
    if any(word in n for word in ("over/under", "over under", "total goals", "goals over", "total")): return "total_goals"
    if n in {"match winner", "1x2", "fulltime result", "full time result", "match result"}: return "1x2"
    return None

def _line(value: str, fallback: Any = None) -> str:
    match = re.search(r"(?<![A-Za-z])([+-]?\\d+(?:[.,]\\d+)?)", value)
    raw = match.group(1).replace(",", ".") if match else (str(fallback) if fallback is not None else "main")
    return raw

def extract_market_predictions(odds_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one best-priced outcome per available market/line, only for 1xBet.

    Probabilities are de-vigged within each market/line group. They are market
    probabilities, not independently validated model forecasts.
    """
    results = []
    for bookmaker in odds_row.get("bookmakers") or []:
        if not is_target_bookmaker(bookmaker.get("name")): continue
        for bet in bookmaker.get("bets") or []:
            name = str(bet.get("name") or "unknown")
            category = _category(name)
            if not category: continue
            groups: dict[str, list[tuple[str, float]]] = {}
            for item in bet.get("values") or []:
                label = str(item.get("value") or "").strip()
                if not label: continue
                try: odd = float(item.get("odd"))
                except (TypeError, ValueError): continue
                if odd <= 1: continue
                point = item.get("handicap")
                line = _line(label, point) if category in {"total_goals","corners","shots","shots_on_target","yellow_cards","handicap"} else "main"
                if category == "handicap" and line != "main":
                    try: line = str(abs(float(line)))
                    except ValueError: pass
                # Preserve selection labels and group different totals/handicaps separately.
                groups.setdefault(line, []).append((label, odd))
            for line, pairs in groups.items():
                # Avoid treating one-sided/ambiguous quote groups as a probability distribution.
                if len(pairs) < 2: continue
                odds = {label: odd for label, odd in pairs}
                try: probs = normalize_implied_probabilities(odds)
                except (ValueError, ZeroDivisionError): continue
                best = max(probs, key=probs.get)
                results.append({
                    "market": category, "market_name": name, "line": None if line == "main" else line,
                    "selection": best, "odds": odds[best], "probability": round(probs[best], 6),
                    "probabilities": {k: round(v, 6) for k, v in probs.items()},
                    "bookmaker": "1xBet", "method": "normalized_implied_odds",
                })
    # A market may be duplicated in the provider response; keep unique market/line records.
    unique = {}
    for item in results:
        key = (item["market"], item["market_name"], item["line"])
        if key not in unique or item["probability"] > unique[key]["probability"]: unique[key] = item
    return sorted(unique.values(), key=lambda x: (x["market"], str(x["line"] or ""), -x["probability"]))
