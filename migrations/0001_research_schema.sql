-- PROPOSED ONLY: offline research schema for Analyse-Football-Codex.
-- NOT EXECUTED. Review against actual Supabase migrations/RLS/policies before use.
-- All instants use timestamptz. Do not store secrets or raw licensed data without permission.

create table if not exists research_competitions (
  id bigint generated always as identity primary key,
  name text not null,
  country_code text,
  unique (name, country_code)
);

create table if not exists research_seasons (
  id bigint generated always as identity primary key,
  competition_id bigint not null references research_competitions(id),
  season_key text not null,
  starts_on date,
  ends_on date,
  unique (competition_id, season_key),
  check (ends_on is null or starts_on is null or ends_on >= starts_on)
);

create table if not exists research_teams (
  id bigint generated always as identity primary key,
  canonical_name text not null,
  country_code text,
  unique (canonical_name, country_code)
);

create table if not exists research_matches (
  id bigint generated always as identity primary key,
  season_id bigint not null references research_seasons(id),
  home_team_id bigint not null references research_teams(id),
  away_team_id bigint not null references research_teams(id),
  kickoff_at timestamptz not null,
  status text not null,
  finished_at timestamptz,
  home_score integer,
  away_score integer,
  venue text,
  created_at timestamptz not null default now(),
  check (home_team_id <> away_team_id),
  check (home_score is null or home_score >= 0),
  check (away_score is null or away_score >= 0),
  check (finished_at is null or finished_at >= kickoff_at),
  check ((home_score is null) = (away_score is null))
);
create index if not exists research_matches_season_kickoff_idx
  on research_matches(season_id, kickoff_at);
create index if not exists research_matches_status_idx
  on research_matches(status);

create table if not exists research_provider_ids (
  id bigint generated always as identity primary key,
  provider text not null,
  entity_type text not null check (entity_type in ('competition','season','team','match','bookmaker','market')),
  provider_id text not null,
  canonical_id bigint not null,
  valid_from timestamptz,
  valid_to timestamptz,
  unique (provider, entity_type, provider_id),
  check (valid_to is null or valid_from is null or valid_to >= valid_from)
);

create table if not exists research_match_team_stats (
  id bigint generated always as identity primary key,
  match_id bigint not null references research_matches(id),
  team_id bigint not null references research_teams(id),
  stat_code text not null,
  stat_value numeric,
  unit text,
  period text not null default 'FT',
  provider text not null,
  observed_at timestamptz not null,
  source_updated_at timestamptz,
  quality_status text not null default 'unverified'
    check (quality_status in ('unverified','verified','suspect','rejected')),
  unique (match_id, team_id, stat_code, period, provider, observed_at)
);
create index if not exists research_stats_match_code_idx
  on research_match_team_stats(match_id, stat_code);
create index if not exists research_stats_observed_idx
  on research_match_team_stats(observed_at);

create table if not exists research_availability_reports (
  id bigint generated always as identity primary key,
  match_id bigint references research_matches(id),
  team_id bigint not null references research_teams(id),
  player_provider_id text,
  report_type text not null check (report_type in ('injury','suspension','return','unknown')),
  status text,
  reported_at timestamptz not null,
  source text not null,
  source_updated_at timestamptz,
  payload jsonb not null default '{}'::jsonb
);

create table if not exists research_odds_snapshots (
  id bigint generated always as identity primary key,
  match_id bigint not null references research_matches(id),
  provider text not null,
  bookmaker text not null,
  observed_at timestamptz not null,
  source_updated_at timestamptz,
  is_in_play boolean not null default false,
  raw_reference text,
  unique (match_id, provider, bookmaker, observed_at, is_in_play)
);
create index if not exists research_odds_match_time_idx
  on research_odds_snapshots(match_id, observed_at);

create table if not exists research_odds_selections (
  id bigint generated always as identity primary key,
  snapshot_id bigint not null references research_odds_snapshots(id) on delete cascade,
  market_code text not null,
  line_value numeric,
  selection_code text not null,
  decimal_odds numeric not null check (decimal_odds > 1),
  settlement_rule_version text,
  unique (snapshot_id, market_code, line_value, selection_code)
);

create table if not exists research_feature_snapshots (
  id bigint generated always as identity primary key,
  match_id bigint not null references research_matches(id),
  model_key text not null,
  feature_schema_version text not null,
  generated_at timestamptz not null,
  data_cutoff_at timestamptz not null,
  source_manifest jsonb not null default '{}'::jsonb,
  features jsonb not null,
  quality_flags jsonb not null default '[]'::jsonb,
  check (data_cutoff_at <= generated_at)
);

-- Cross-table temporal invariant: a feature snapshot must be generated before kickoff.
create or replace function research_validate_feature_snapshot_time()
returns trigger language plpgsql as $
declare match_kickoff timestamptz;
begin
  select kickoff_at into match_kickoff from research_matches where id = new.match_id;
  if match_kickoff is null then
    raise exception 'feature snapshot references missing match %', new.match_id;
  end if;
  if new.generated_at >= match_kickoff then
    raise exception 'feature snapshot must be generated before kickoff';
  end if;
  if new.data_cutoff_at > new.generated_at then
    raise exception 'feature data cutoff cannot be after generation time';
  end if;
  return new;
end;
$;
create trigger research_feature_snapshot_time_guard
before insert or update on research_feature_snapshots
for each row execute function research_validate_feature_snapshot_time();

create table if not exists research_model_runs (
  id bigint generated always as identity primary key,
  model_key text not null,
  model_version text not null,
  config jsonb not null default '{}'::jsonb,
  training_started_at timestamptz,
  training_cutoff_at timestamptz,
  dataset_fingerprint text,
  code_revision text,
  created_at timestamptz not null default now(),
  unique (model_key, model_version, dataset_fingerprint)
);

create table if not exists research_predictions (
  id bigint generated always as identity primary key,
  match_id bigint not null references research_matches(id),
  model_run_id bigint not null references research_model_runs(id),
  feature_snapshot_id bigint references research_feature_snapshots(id),
  market_code text not null,
  selection_code text not null,
  line_value numeric,
  probability numeric not null check (probability >= 0 and probability <= 1),
  generated_at timestamptz not null,
  odds_snapshot_id bigint references research_odds_snapshots(id),
  decimal_odds numeric check (decimal_odds is null or decimal_odds > 1),
  implied_probability numeric check (implied_probability is null or (implied_probability > 0 and implied_probability <= 1)),
  edge numeric,
  calibration_version text,
  unique (match_id, model_run_id, market_code, selection_code, line_value, generated_at)
);
create index if not exists research_predictions_match_model_idx
  on research_predictions(match_id, model_run_id);

create table if not exists research_settled_predictions (
  id bigint generated always as identity primary key,
  prediction_id bigint not null unique references research_predictions(id),
  settled_at timestamptz not null,
  settlement_status text not null check (settlement_status in ('won','lost','push','half_won','half_lost','void','pending')),
  actual_value numeric,
  stake_units numeric not null default 1 check (stake_units > 0),
  net_units numeric,
  settlement_rule_version text not null,
  notes text
);

create table if not exists research_ingestion_runs (
  id bigint generated always as identity primary key,
  provider text not null,
  dataset_key text not null,
  started_at timestamptz not null,
  completed_at timestamptz,
  status text not null check (status in ('running','succeeded','partial','failed')),
  records_received integer not null default 0 check (records_received >= 0),
  records_inserted integer not null default 0 check (records_inserted >= 0),
  records_rejected integer not null default 0 check (records_rejected >= 0),
  error_summary text,
  source_manifest jsonb not null default '{}'::jsonb,
  check (completed_at is null or completed_at >= started_at)
);
create index if not exists research_ingestion_runs_provider_time_idx
  on research_ingestion_runs(provider, started_at desc);
