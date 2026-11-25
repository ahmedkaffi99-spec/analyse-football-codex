"""Regression tests for pure helpers ported from the read-only reference."""
from football_analysis.team_names import normalize_team, similarity_score
from football_analysis.daily_bet_cap import bet_key, key_from_candidate
from football_analysis.bookmaker_consensus import no_vig_probabilities, consensus


def test_team_normalization():
    assert normalize_team("Paris Saint-Germain") == "paris sg"
    assert normalize_team("Manchester United FC") == "man united"


def test_team_aliases_cover_common_provider_abbreviations():
    assert normalize_team("PSG") == "paris sg"
    assert normalize_team("Man Utd") == "man united"
    assert normalize_team("Spurs") == "tottenham"
    assert normalize_team("Inter") == "inter milan"
    assert similarity_score("PSG", "Paris Saint-Germain") >= 90


def test_diacritics_are_normalized_without_optional_unidecode():
    # This assertion is stable with either the optional unidecode package or the
    # built-in Unicode fallback.
    assert normalize_team("München") == "munchen"


def test_similarity_bounded():
    assert 0 <= similarity_score("PSG", "Paris Saint-Germain") <= 100


def test_bet_key_handicap_normalization():
    assert bet_key("Match", "Total", "OVER", 2.5) == bet_key(" Match ", "Total", "over", 2.50)


def test_candidate_key():
    c = {"match": "M", "pick": {"categorie": "Corners", "selection": "Over", "handicap": "9.5"}}
    assert key_from_candidate(c) == ("M", "Corners", "over", 9.5)


def test_no_vig():
    p = no_vig_probabilities({"selections": [{"selection": "H", "odds": 2.0}, {"selection": "A", "odds": 2.0}]})
    assert p == {"H": 0.5, "A": 0.5}


def test_consensus():
    markets = {
        b: [{"market": "1X2", "selections": [{"selection": "Home", "odds": h}, {"selection": "Away", "odds": 2.0}]}]
        for b, h in [("Pinnacle", 1.8), ("Book2", 2.0), ("Book3", 2.0)]
    }
    out = consensus(markets, min_books=3)
    assert ("1X2", None, "Home") in out
    assert out[("1X2", None, "Home")]["bookmakers"] == 3
