"""Extract supported 1xBet market families without confusing count markets with goals."""
from __future__ import annotations
import re
from typing import Any
from .markets import normalize_implied_probabilities
from .collect_odds import is_target_bookmaker

def _category(name: str) -> str | None:
    n = name.casefold().replace("-", " ")
    if "double chance" in n: return "double_chance"
    if "win to nil" in n or "win without conceding" in n: return "win_to_nil"
    if "draw no bet" in n or n.strip() == "dnb": return "dnb"
    if "both teams to score" in n or "btts" in n: return "btts"
    if "corner" in n: return "corners"
    if "yellow card" in n: return "yellow_cards"
    if "red card" in n: return "red_cards"
    if "foul" in n: return "fouls"
    if "offside" in n: return "offsides"
    if "shots on target" in n or "shots on goal" in n: return "shots_on_target"
    if "shot" in n: return "shots"
    if "handicap" in n: return "handicap"
    if "over/under" in n or "over under" in n or "total goals" in n or "goals over" in n or "goals under" in n: return "total_goals"
    if n.strip() in {"match winner", "1x2", "fulltime result", "full time result", "match result"}: return "1x2"
    return None

def _line(value: str, fallback: Any = None) -> str:
    match = re.search(r"(?<![A-Za-z])([+-]?\d+(?:[.,]\d+)?)", value)
    return match.group(1).replace(",", ".") if match else (str(fallback) if fallback is not None else "main")

def extract_market_predictions(odds_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize outcomes within each available market/line; only 1xBet."""
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
                line = _line(label, point) if category in {"total_goals","corners","shots","shots_on_target","yellow_cards","red_cards","fouls","offsides","handicap"} else "main"
                if category == "handicap" and line != "main":
                    try: line = str(abs(float(line)))
                    except ValueError: pass
                groups.setdefault(line, []).append((label, odd))
            for line, pairs in groups.items():
                if len(pairs) < 2: continue
                odds = {label: odd for label, odd in pairs}
                try: probs = normalize_implied_probabilities(odds)
                except (ValueError, ZeroDivisionError): continue
                # Retain every outcome, not only the most likely one, so each market
                # agent can score both sides and the EV ranking isn't biased by odds.
                for label, odd in pairs:
                    results.append({"market":category,"market_name":name,
                        "line":None if line == "main" else line,"selection":label,"odds":odd,
                        "probability":round(probs[label],6),
                        "probabilities":{k:round(v,6) for k,v in probs.items()},
                        "bookmaker":"1xBet","method":"normalized_implied_odds"})
    unique = {}
    for item in results:
        key = (item["market"],item["market_name"],item["line"],item["selection"])
        if key not in unique or item["odds"] > unique[key]["odds"]: unique[key] = item
    return sorted(unique.values(),key=lambda x:(x["market"],str(x["line"] or ""),x["selection"]))
