from football_analysis.coverage_audit import audit_pipeline_coverage
def test_pipeline_coverage_reports_each_stage_and_reason():
    fixtures=[{"fixture_id":"1","home":"PSG","away":"Roma","competition":"UCL"},
              {"fixture_id":"2","home":"Lille","away":"Bayern","competition":"UCL"},
              {"fixture_id":"3","home":"Club Brugge","away":"Liverpool","competition":"UCL"}]
    report=audit_pipeline_coverage(fixtures,odds_fixture_ids={"2","3"},
        market_fixture_ids={"2"},candidate_fixture_ids={"2"},selected_fixture_ids={"2"},
        exclusion_reasons={"3":"provider fixture unmatched"})
    statuses={r["fixture_id"]:r["status"] for r in report["fixtures"]}
    assert statuses=={"1":"missing_odds","2":"selected","3":"excluded"}
    assert report["fixtures_total"]==3
    assert report["counts"]=={"missing_odds":1,"selected":1,"excluded":1}
def test_pipeline_coverage_does_not_silently_drop_candidate():
    report=audit_pipeline_coverage([{"fixture_id":"x","home":"A","away":"B"}],
        odds_fixture_ids={"x"},market_fixture_ids={"x"},candidate_fixture_ids={"x"})
    assert report["fixtures"][0]["status"]=="not_selected"
def test_pipeline_coverage_duplicate_fixture_ids_rejected():
    try:
        audit_pipeline_coverage([{"fixture_id":"1"},{"fixture_id":"1"}])
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        assert False,"expected duplicate fixture rejection"
