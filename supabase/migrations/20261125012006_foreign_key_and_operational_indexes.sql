-- Add supporting indexes for foreign-key lookups and operational queries.
create index if not exists coupon_selections_match_idx on public.coupon_selections(match_id);
create index if not exists coupon_selections_prediction_idx on public.coupon_selections(prediction_id);
create index if not exists pipeline_runs_coupon_idx on public.pipeline_runs(coupon_id);
create index if not exists match_results_status_idx on public.match_results(status);
create index if not exists team_absences_team_observed_idx on public.team_absences(lower(team_name), observed_at desc);
