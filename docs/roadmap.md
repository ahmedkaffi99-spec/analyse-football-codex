# Roadmap

## Phase 1 — Offline core
- Validated match, prediction, and timestamped 1X2 odds models.
- Market-implied probabilities and margin removal.
- Brier score, log loss, unit-stake ROI.
- Temporal leakage protections and synthetic unit tests.

## Phase 2 — Data audit
- Inspect real migrations/models before table-specific SQL.
- Verify keys, timezone semantics, stable match IDs, score finality, odds timestamps, markets, selections, and duplicates.
- Keep database access disabled until separately authorized.

## Phase 3 — Baselines and validation
- Compare uniform and market-implied baselines on chronological splits.
- Report calibration, scoring metrics, sample size, and uncertainty.
- Never tune on the final test set.

## Phase 4 — Research models
- Add independent models with reproducible configs and model versions.
- Test by season and competition before considering any deployment.

## Phase 5 — Optional integrations (disabled)
- Live football APIs, Supabase, Telegram publishing, and production wiring require separate explicit authorization.
- Do not modify the original repository or its production behavior.
