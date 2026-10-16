"""Specialist market probability, edge and expected-value calculations."""
from __future__ import annotations
import math
import re
from typing import Any
from .all_markets import extract_market_predictions
from .market_agents import count_market_probability, team_metric_rate, win_to_nil_probability, dnb_probabilities

def _poisson_pmf(lam: float, k: int) -> float:
    if lam < 0: return 0.0
    return math.exp(-lam) * lam**k / math.factorial(k) if lam else float(k == 0)

def _line_from_selection(selection: str, fallback: Any) -> float | None:
    if fallback is not None:
        try: return float(fallback)
        except (TypeError,ValueError): pass
    match = re.search(r"(?<![A-Za-z])([+-]?\d+(?:[.,]\d+)?)", selection)
    try: return float(match.group(1).replace(",", ".")) if match else None
    except (TypeError,ValueError): return None

def _total_goals_probability(home_xg: float, away_xg: float, selection: str, line: float) -> float | None:
    if not (0 <= home_xg <= 8 and 0 <= away_xg <= 8): return None
    if abs(line-round(line)) < 1e-9: return None
    total=0.0
    for h in range(16):
        for a in range(16):
            goals=h+a
            if "over" in selection.casefold() and goals > line: total += _poisson_pmf(home_xg,h)*_poisson_pmf(away_xg,a)
            elif "under" in selection.casefold() and goals < line: total += _poisson_pmf(home_xg,h)*_poisson_pmf(away_xg,a)
    return max(0.0,min(1.0,total))

def _scoreline_probability(home_xg: float, away_xg: float, selection: str, market: str) -> float | None:
    label=selection.casefold()
    p=0.0
    # Parse handicap outcome labels such as "Home -1.5" / "Away +1.5".
    if market == "handicap":
        match=re.search(r"([+-]?\d+(?:[.,]\d+)?)",label)
        if not match: return None
        handicap=float(match.group(1).replace(",","."))
        is_home=any(x in label for x in ("home","team 1","team1"))
        is_away=any(x in label for x in ("away","team 2","team2"))
        if not is_home and not is_away: return None
        if abs(handicap-round(handicap)) < 1e-9: return None
        for h in range(16):
            for a in range(16):
                adjusted=(h-a+handicap) if is_home else (a-h+handicap)
                if adjusted > 0: p += _poisson_pmf(home_xg,h)*_poisson_pmf(away_xg,a)
        return max(0.0,min(1.0,p))
    return None

def _model_probability(market: str, selection: str, line: Any, model_1x2: dict[str,float],
                       home_xg: float, away_xg: float, market_stats: dict[str,Any]) -> float | None:
    label=selection.strip().casefold().replace(" ","")
    if market == "1x2":
        aliases={"home":"1","1":"1","draw":"x","x":"x","away":"2","2":"2","team1":"1","team2":"2"}
        key=aliases.get(label)
        return model_1x2.get(key) if key else None
    if market == "double_chance":
        if any(x in label for x in ("home/draw","1x","1/x","homeordraw")): return model_1x2.get("1",0)+model_1x2.get("x",0)
        if any(x in label for x in ("draw/away","x2","x/2","draworaway")): return model_1x2.get("x",0)+model_1x2.get("2",0)
        if any(x in label for x in ("home/away","12","1/2","homeoraway")): return model_1x2.get("1",0)+model_1x2.get("2",0)
    if market == "dnb":
        dnb=dnb_probabilities(model_1x2)
        if any(x in label for x in ("home","team1","1")): return dnb["1"]
        if any(x in label for x in ("away","team2","2")): return dnb["2"]
    if market == "btts":
        yes=(1-math.exp(-home_xg))*(1-math.exp(-away_xg))
        if label in {"yes","y"}: return yes
        if label in {"no","n"}: return 1-yes
    if market == "total_goals":
        ln=_line_from_selection(selection,line)
        return _total_goals_probability(home_xg,away_xg,selection,ln) if ln is not None else None
    if market in {"corners","shots","shots_on_target","yellow_cards","red_cards","fouls","offsides"}:
        rate=team_metric_rate(market,market_stats.get("home") or {},market_stats.get("away") or {})
        ln=_line_from_selection(selection,line)
        return count_market_probability(rate,selection,ln) if rate is not None and ln is not None else None
    if market == "win_to_nil":
        return win_to_nil_probability(home_xg,away_xg,selection)
    if market == "handicap":
        return _scoreline_probability(home_xg,away_xg,selection,market)
    return None

def score_market_predictions(odds_row: dict[str,Any], *, model_1x2: dict[str,float],
                             home_xg: float, away_xg: float,
                             market_stats: dict[str,Any] | None = None) -> list[dict[str,Any]]:
    """Score all exposed 1xBet outcomes with family-specific probability models.

    Count markets use their own recent-stat samples; unsupported or insufficient
    samples remain unscored instead of receiving fabricated edge/EV values.
    """
    market_stats=market_stats or {}
    scored=[]
    for market in extract_market_predictions(odds_row):
        family=market["market"]
        probabilities=market.get("probabilities") or {}
        p_market=probabilities.get(market["selection"],market.get("probability"))
        p_model=_model_probability(family,market["selection"],market.get("line"),
            model_1x2,home_xg,away_xg,market_stats)
        item={**market,"market_probability":round(float(p_market),6),"model_probability":None,
              "edge":None,"edge_pct_points":None,"expected_value":None,
              "value_status":"insufficient_market_specific_data"}
        if p_model is not None and 0 <= p_model <= 1:
            edge=p_model-float(p_market)
            ev=p_model*float(market["odds"])-1
            item.update(model_probability=round(p_model,6),edge=round(edge,6),
                edge_pct_points=round(edge*100,2),expected_value=round(ev,6),
                value_status="positive_ev" if ev>0 else "negative_ev")
        scored.append(item)
    return sorted(scored,key=lambda item:(item["expected_value"] is None,
        -(item["expected_value"] if item["expected_value"] is not None else -99),
        item["market"],str(item.get("line") or ""),item["selection"]))
