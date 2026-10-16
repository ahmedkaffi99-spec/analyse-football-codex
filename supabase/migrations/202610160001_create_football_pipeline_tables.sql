-- Schema for the independent analyse-football-codex pipeline.
-- Apply through Supabase migrations; do not run against the production source project.
create extension if not exists pgcrypto;

create table if not exists public.matches (
  id uuid primary key default gen_random_uuid(),
  provider text not null default 'api-football',
  provider_match_id text not null,
  league_id text,
  league_name text,
  season integer,
  home_team text not null,
  away_team text not null,
  kickoff_at timestamptz not null,
  status text not null default 'scheduled',
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (provider, provider_match_id)
);
create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id) on delete cascade,
  model_name text not null,
  model_version text,
  home_expected_goals numeric(8,4),
  away_expected_goals numeric(8,4),
  probability_home numeric(7,6),
  probability_draw numeric(7,6),
  probability_away numeric(7,6),
  market_weight numeric(5,4) not null default 0,
  explanation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (home_expected_goals is null or home_expected_goals >= 0),
  check (away_expected_goals is null or away_expected_goals >= 0),
  check (probability_home is null or probability_home between 0 and 1),
  check (probability_draw is null or probability_draw between 0 and 1),
  check (probability_away is null or probability_away between 0 and 1),
  check (market_weight between 0 and 1)
);
create table if not exists public.coupons (
  id uuid primary key default gen_random_uuid(),
  coupon_date date not null,
  status text not null default 'draft' check (status in ('draft','validated','published','settled','cancelled')),
  title text not null default 'Daily football coupon',
  selection_count integer not null default 0 check (selection_count >= 0),
  combined_odds numeric(12,4),
  telegram_message_id text,
  published_at timestamptz,
  settled_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (coupon_date, title)
);
create table if not exists public.coupon_selections (
  id uuid primary key default gen_random_uuid(),
  coupon_id uuid not null references public.coupons(id) on delete cascade,
  match_id uuid not null references public.matches(id) on delete restrict,
  prediction_id uuid references public.predictions(id) on delete set null,
  market text not null default '1X2',
  selection text not null,
  odds numeric(12,4),
  probability numeric(7,6),
  result text not null default 'pending' check (result in ('pending','won','lost','void','push')),
  created_at timestamptz not null default now(),
  unique (coupon_id, match_id, market, selection),
  check (odds is null or odds > 1),
  check (probability is null or probability between 0 and 1)
);
create table if not exists public.match_results (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null unique references public.matches(id) on delete cascade,
  home_score integer,
  away_score integer,
  status text not null default 'pending' check (status in ('pending','finished','postponed','cancelled')),
  source text,
  raw_payload jsonb not null default '{}'::jsonb,
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  check (home_score is null or home_score >= 0),
  check (away_score is null or away_score >= 0)
);
create table if not exists public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  run_key text not null unique,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running' check (status in ('running','succeeded','failed','skipped')),
  fixtures_seen integer not null default 0 check (fixtures_seen >= 0),
  predictions_created integer not null default 0 check (predictions_created >= 0),
  coupon_id uuid references public.coupons(id) on delete set null,
  error_message text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists matches_kickoff_at_idx on public.matches (kickoff_at);
create index if not exists matches_status_idx on public.matches (status);
create index if not exists predictions_match_created_idx on public.predictions (match_id, created_at desc);
create index if not exists coupons_date_status_idx on public.coupons (coupon_date desc, status);
create index if not exists coupon_selections_coupon_idx on public.coupon_selections (coupon_id);
create index if not exists pipeline_runs_started_idx on public.pipeline_runs (started_at desc);
alter table public.matches enable row level security;
alter table public.predictions enable row level security;
alter table public.coupons enable row level security;
alter table public.coupon_selections enable row level security;
alter table public.match_results enable row level security;
alter table public.pipeline_runs enable row level security;
