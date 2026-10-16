-- Odds snapshots for the independent prediction engine.
-- Apply through the Supabase SQL editor/migration process after review.
create table if not exists public.football_odds (
    id uuid primary key default gen_random_uuid(),
    provider text not null default 'api-football',
    fixture_id text not null,
    bookmaker_id text not null default 'unknown',
    bookmaker_name text not null,
    market_id text not null default 'unknown',
    market_name text not null,
    selection text not null,
    odds numeric not null check (odds > 1),
    -- -999 denotes a market outcome without a line/handicap.
    point numeric not null default -999,
    captured_at timestamptz not null,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint football_odds_snapshot_unique unique
        (provider, fixture_id, bookmaker_id, market_id, selection, point, captured_at)
);

create index if not exists football_odds_fixture_market_time_idx
    on public.football_odds (fixture_id, market_id, captured_at desc);
create index if not exists football_odds_capture_time_idx
    on public.football_odds (captured_at desc);
create index if not exists football_odds_bookmaker_market_idx
    on public.football_odds (bookmaker_id, market_id, captured_at desc);

alter table public.football_odds enable row level security;
