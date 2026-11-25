"""Traceable team-name normalization migrated from the read-only reference repo."""
from __future__ import annotations
import re
import unicodedata
from typing import Optional

ALIASES = {
    # National-team name translations from the reference fixture resolver.
    "allemagne": "germany",
    "angleterre": "england",
    "espagne": "spain",
    "italie": "italy",
    "belgique": "belgium",
    "pays bas": "netherlands",
    "hollande": "netherlands",
    "ecosse": "scotland",
    "pays de galles": "wales",
    "irlande du nord": "northern ireland",
    "cote d ivoire": "ivory coast",
    "cote d'ivoire": "ivory coast",
    "cameroun": "cameroon",
    "algerie": "algeria",
    "maroc": "morocco",
    "tunisie": "tunisia",
    "egypte": "egypt",
    "afrique du sud": "south africa",
    "bosnie herzegovine": "bosnia and herzegovina",
    "bosnie": "bosnia and herzegovina",
    "macedonie du nord": "north macedonia",
    "coree du sud": "south korea",
    "rd congo": "dr congo",
    "republique democratique du congo": "dr congo",
    "congo dr": "dr congo",
    "emirats arabes unis": "united arab emirates",
    "uae": "united arab emirates",
    "nouvelle zelande": "new zealand",
    "russie": "russia",
    "suede": "sweden",
    "norvege": "norway",
    "danemark": "denmark",
    "croatie": "croatia",
    "serbie": "serbia",
    "hongrie": "hungary",
    "roumanie": "romania",
    "pologne": "poland",
    "grece": "greece",
    "irlande": "ireland",
    "japon": "japan",
    "chine": "china",
    "inde": "india",
    "mexique": "mexico",
    "jamaique": "jamaica",
    "republique dominicaine": "dominican republic",
    "trinite et tobago": "trinidad and tobago",
    "iles feroe": "faroe islands",
    "tchequie": "czechia",
    "republique tcheque": "czechia",
    "turkiye": "turkey",
    "manchester united": "man united",
    "manchester city": "man city",
    "man utd": "man united",
    "man u": "man united",
    "paris saint germain": "paris sg",
    "psg": "paris sg",
    "borussia monchengladbach": "m'gladbach",
    "atletico madrid": "ath madrid",
    "atletico": "ath madrid",
    "athletic club": "ath bilbao",
    "athletic bilbao": "ath bilbao",
    "real betis": "betis",
    "real sociedad": "sociedad",
    "ac milan": "milan",
    "hellas verona": "verona",
    "borussia dortmund": "dortmund",
    "bayer leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt",
    "newcastle united": "newcastle",
    "wolverhampton wanderers": "wolves",
    "tottenham hotspur": "tottenham",
    "spurs": "tottenham",
    "west ham united": "west ham",
    "nottingham forest": "nott'm forest",
    "leeds united": "leeds",
    "brighton hove albion": "brighton",
    "olympique marseille": "marseille",
    "olympique lyonnais": "lyon",
    "stade rennais": "rennes",
    "as monaco": "monaco",
    "1 fc union berlin": "union berlin",
    "fsv mainz 05": "mainz",
    "vfl wolfsburg": "wolfsburg",
    "bayern munchen": "bayern munich",
    "bayern": "bayern munich",
    "1 fc heidenheim": "heidenheim",
    "sc freiburg": "freiburg",
    "tsg hoffenheim": "hoffenheim",
    "celta vigo": "celta",
    "rayo vallecano": "vallecano",
    "deportivo alaves": "alaves",
    "espanyol": "espanol",
    "internazionale": "inter milan",
    "inter": "inter milan",
    "barca": "barcelona",
}


def normalize_team(name: Optional[str]) -> str:
    if not name:
        return ""
    try:
        from unidecode import unidecode
        text = unidecode(name)
    except ImportError:
        # Keep accented names usable even when the optional transliteration
        # package is not installed. NFKD removes combining marks for Latin text.
        text = unicodedata.normalize("NFKD", name)
        text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9' ]", " ", text.lower())
    if text.strip() not in {"ac milan", "as monaco"}:
        text = re.sub(r"\b(fc|afc|cf|sc|ssc|ac|as)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def similarity_score(a: str, b: str) -> int:
    try:
        from rapidfuzz import fuzz
        return int(fuzz.token_set_ratio(normalize_team(a), normalize_team(b)))
    except ImportError:
        from difflib import SequenceMatcher
        return int(SequenceMatcher(None, normalize_team(a), normalize_team(b)).ratio() * 100)
