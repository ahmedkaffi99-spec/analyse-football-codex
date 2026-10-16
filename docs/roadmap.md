# Roadmap

## Phase 1 — Offline core
- Validated match, prediction, and timestamped 1X2 odds models.
- Market-implied probabilities and margin removal.
- Brier score, log loss, unit-stake ROI.
- Temporal leakage protections and synthetic unit tests.

## Phase 2 — Data audit and data foundation
- Use API-Football as the sole provider. The secure client, bounded retry/quota-header handling, unit tests, and manual local-snapshot workflow are implemented; run the target league/season coverage pilot to verify 1xBet market and statistics coverage.
- Draft a normalized provider-neutral schema; do not apply it until reviewed against actual Supabase migrations and policies.
- Build point-in-time rolling features with explicit data availability and missingness.
- Inspect real migrations/models before table-specific SQL.
- Verify keys, timezone semantics, stable match IDs, score finality, odds timestamps, markets, selections, and duplicates. Account for API-Football's approximately seven-day pre-match odds history limit; capture future snapshots prospectively.
- Keep database access and Telegram publication disabled; snapshots are local JSON artifacts only. API collection is manual-only.

## Phase 3 — Baselines and validation
- Compare uniform and market-implied baselines on chronological splits.
- Report calibration, scoring metrics, sample size, and uncertainty.
- Never tune on the final test set.

## Phase 4 — Research models
- Add independent models with reproducible configs and model versions.
- Test by season and competition before considering any deployment.

## Phase 5 — Optional integrations (scope restricted)
- API-Football client and manual local snapshot collection are implemented on this branch. A real request requires API_FOOTBALL_KEY and a manual workflow run.
- Supabase writes, Telegram publishing, scheduled live collection, and production wiring remain disabled pending separate authorization.
- Do not modify the original repository or its production behavior.
