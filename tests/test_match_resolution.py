from football_analysis.match_resolution import score_fixture_match,resolve_fixture
def test_resolves_same_match_with_different_team_spelling():
    source={"home":"Paris Saint-Germain","away":"Roma","date":"2026-11-25","competition":"UEFA Champions League"}
    candidate={"home":"Paris SG","away":"AS Roma","date":"2026-11-25","league":"UEFA Champions League"}
    assert score_fixture_match(source,candidate)["score"]>=92
    assert resolve_fixture(source,[candidate])["status"]=="matched"
def test_reversed_home_away_is_not_auto_matched():
    source={"home":"Paris SG","away":"Roma","date":"2026-11-25","competition":"UCL"}
    candidate={"home":"Roma","away":"Paris SG","date":"2026-11-25","competition":"UCL"}
    assert resolve_fixture(source,[candidate])["status"]!="matched"
def test_ambiguous_duplicate_candidates_are_not_auto_matched():
    source={"home":"Lille","away":"Bayern Munich","date":"2026-11-25","competition":"UCL"}
    c={"home":"Lille","away":"Bayern","date":"2026-11-25","competition":"UCL"}
    result=resolve_fixture(source,[c,{**c,"fixture_id":2}])
    assert result["status"]=="ambiguous"
    assert result["match"] is None
def test_different_date_reduces_confidence():
    a={"home":"PSG","away":"Roma","date":"2026-11-25","competition":"UCL"}
    b={"home":"PSG","away":"Roma","date":"2026-11-27","competition":"UCL"}
    assert score_fixture_match(a,b)["score"]<92
def test_empty_candidates():
    assert resolve_fixture({"home":"A","away":"B"},[])["status"]=="not_found"
