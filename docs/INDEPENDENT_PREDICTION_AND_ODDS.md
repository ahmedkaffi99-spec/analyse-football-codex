# Independent prediction and odds collection

This branch is the only implementation target for this project.

## First delivery

- `football_analysis.markets`: provider-neutral decimal-odds utilities, overround normalization, baseline Poisson market probabilities, and a generic API-Football odds-response flattener.
- `football_analysis.collect_odds`: paginates API-Football `/odds` for a UTC date and stores each returned bookmaker/market/selection quote as a timestamped snapshot.
- `supabase/migrations/202610160001_football_odds.sql`: schema for historical odds snapshots.
- `.github/workflows/collect-football-odds.yml`: scheduled every four hours and manually runnable.

## Required setup before live collection

1. Review and apply `supabase/migrations/202610160001_football_odds.sql` to Supabase project `tsfaupmafzuylsfjampt`.
2. Confirm GitHub Actions secrets `API_FOOTBALL_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` are configured. Never put secret values in this repository.
3. Open GitHub Actions → **Collect API-Football odds snapshots** → **Run workflow**.
4. Inspect logs for pages fetched, fixtures with odds, and quotes sent to Supabase.

The workflow is intentionally separate from the live Telegram coupon pipeline. Applying the migration is a prerequisite; no production odds collection should be launched before the table exists.

## Model limitations

The Poisson functions currently derive markets from supplied expected goals; they do not yet estimate expected goals from team history. The next implementation phase must build a time-aware feature dataset and estimate team attack/defence strengths from historical results, then validate with chronological backtests. Never describe the baseline as proven profitable.

## Coverage and data integrity

API-Football only returns markets and bookmakers available to the subscription and the selected fixtures/date. The collector preserves unknown market names rather than assuming a fixed list. Snapshots have a capture timestamp so odds movement can be analyzed later.
