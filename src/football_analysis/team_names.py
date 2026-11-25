"""Traceable team-name normalization migrated from the read-only reference repo."""
from __future__ import annotations
import re
from typing import Optional
ALIASES={"manchester united":"man united","manchester city":"man city","paris saint germain":"paris sg","borussia monchengladbach":"m'gladbach","atletico madrid":"ath madrid","athletic club":"ath bilbao","real betis":"betis","real sociedad":"sociedad","ac milan":"milan","hellas verona":"verona","borussia dortmund":"dortmund","bayer leverkusen":"leverkusen","eintracht frankfurt":"ein frankfurt","newcastle united":"newcastle","wolverhampton wanderers":"wolves","tottenham hotspur":"tottenham","west ham united":"west ham","nottingham forest":"nott'm forest","leeds united":"leeds","brighton hove albion":"brighton","olympique marseille":"marseille","olympique lyonnais":"lyon","stade rennais":"rennes","as monaco":"monaco","1 fc union berlin":"union berlin","fsv mainz 05":"mainz","vfl wolfsburg":"wolfsburg","bayern munchen":"bayern munich","1 fc heidenheim":"heidenheim","sc freiburg":"freiburg","tsg hoffenheim":"hoffenheim","celta vigo":"celta","rayo vallecano":"vallecano","deportivo alaves":"alaves","espanyol":"espanol"}
def normalize_team(name: Optional[str])->str:
    if not name:return ""
    try:
        from unidecode import unidecode
        text=unidecode(name)
    except ImportError:text=name
    text=re.sub(r"[^a-z0-9' ]"," ",text.lower())
    if text.strip() not in {"ac milan","as monaco"}:text=re.sub(r"\b(fc|afc|cf|sc|ssc|ac|as)\b"," ",text)
    text=re.sub(r"\s+"," ",text).strip()
    return ALIASES.get(text,text)
def similarity_score(a:str,b:str)->int:
    try:
        from rapidfuzz import fuzz
        return int(fuzz.token_set_ratio(normalize_team(a),normalize_team(b)))
    except ImportError:
        from difflib import SequenceMatcher
        return int(SequenceMatcher(None,normalize_team(a),normalize_team(b)).ratio()*100)
