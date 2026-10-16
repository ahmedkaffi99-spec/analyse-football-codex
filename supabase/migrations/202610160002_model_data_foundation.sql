-- Phase 3: data foundation for ten market-specific research models.
-- Apply only in the dedicated codex Supabase project after review.
-- The original analyse-football project is out of scope.

create table if not exists public.team_match_stats (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id) on delete cascade,
  provider text not null,
  provider_team_id text,
  team_side text not null check (team_side in ('home','away')),
  team_name text not null,
  goals_for integer check (goals_for is null or goals_for >= 0),
  goals_against integer check (goals_against is null or goals_against >= 0),
  xg numeric(8,4) check (xg is null or xg >= 0),
  xga numeric(8,4) check (xga is null or xga >= 0),
  shots integer check (shots is null or shots >= 0),
  shots_on_target integer check (shots_on_target is null or shots_on_target >= 0),
  shots_off_target integer check (shots_off_target is null or shots_off_target >= 0),
  shots_blocked integer check (shots_blocked is null or shots_blocked >= 0),
  shots_inside_box integer check (shots_inside_box is null or shots_inside_box >= 0),
  corners integer check (corners is null or corners >= 0),
  yellow_cards integer check (yellow_cards is null or yellow_cards >= 0),
  red_cards integer check (red_cards is null or red_cards >= 0),
  fouls integer check (fouls is null or fouls >= 0),
  possession_pct numeric(5,2) check (possession_pct is null or possession_pct between 0 and 100),
  dangerous_attacks integer check (dangerous_attacks is null or dangerous_attacks >= 0),
  big_chances integer check (big_chances is null or big_chances >= 0),
  provider_observed_at timestamptz,
  coverage_status text not null default 'unknown'
    check (coverage_status in ('complete','partial','missing','unknown')),
  raw_stats jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now(),
  unique (match_id, team_side, provider)
);
create index if not exists team_match_stats_match_idx on public.team_match_stats (match_id);
create index if not exists team_match_stats_team_idx on public.team_match_stats (lower(team_name), ingested_at desc);

create table if not exists public.match_feature_snapshots (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id) on delete cascade,
  generated_at timestamptz not null default now(),
  feature_cutoff_at timestamptz not null,
  feature_schema_version text not null,
  model_domain text not null check (model_domain in ('match','goals','corners','cards','shots','shared')),
  features jsonb not null,
  source_summary jsonb not null default '{}'::jsonb,
  validation_status text not null default 'pending' check (validation_status in ('pending','valid','rejected')),
  validation_errors jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  unique (match_id, feature_cutoff_at, feature_schema_version, model_domain)
);
create index if not exists match_features_match_cutoff_idx on public.match_feature_snapshots (match_id, feature_cutoff_at desc);
create index if not exists match_features_domain_cutoff_idx on public.match_feature_snapshots (model_domain, feature_cutoff_at desc);

create or replace function public.guard_match_feature_cutoff()
returns trigger language plpgsql as $$
declare
  target_kickoff timestamptz;
begin
  select kickoff_at into target_kickoff from public.matches where id = new.match_id;
  if target_kickoff is null then
    raise exception 'feature snapshot references missing match %', new.match_id;
  end if;
  if new.feature_cutoff_at >= target_kickoff then
    raise exception 'feature_cutoff_at must be strictly before kickoff_at';
  end if;
  if new.generated_at >= target_kickoff then
    raise exception 'generated_at must be strictly before kickoff_at';
  end if;
  return new;
end;
$$;
drop trigger if exists trg_guard_match_feature_cutoff on public.match_feature_snapshots;
create trigger trg_guard_match_feature_cutoff
before insert or update of match_id, generated_at, feature_cutoff_at
on public.match_feature_snapshots
for each row execute function public.guard_match_feature_cutoff();

create table if not exists public.team_absences (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  provider_match_id text,
  provider_team_id text,
  team_name text not null,
  player_provider_id text,
  player_name text not null,
  absence_type text,
  status text not null default 'unknown' check (status in ('out','doubtful','suspended','available','unknown')),
  observed_at timestamptz not null,
  source_payload jsonb not null default '{}'::jsonb,
  ingested_at timestamptz not null default now(),
  unique (provider, provider_match_id, player_provider_id, observed_at)
);
create index if not exists team_absences_match_observed_idx on public.team_absences (provider_match_id, observed_at desc);

create table if not exists public.data_ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  dataset text not null,
  run_key text not null unique,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','succeeded','failed','partial','skipped')),
  requested_count integer not null default 0 check (requested_count >= 0),
  received_count integer not null default 0 check (received_count >= 0),
  inserted_count integer not null default 0 check (inserted_count >= 0),
  updated_count integer not null default 0 check (updated_count >= 0),
  missing_count integer not null default 0 check (missing_count >= 0),
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists data_ingestion_runs_provider_started_idx on public.data_ingestion_runs (provider, started_at desc);

alter table public.team_match_stats enable row level security;
alter table public.match_feature_snapshots enable row level security;
alter table public.team_absences enable row level security;
alter table public.data_ingestion_runs enable row level security;
