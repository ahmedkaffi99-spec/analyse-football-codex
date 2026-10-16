# Proposed PostgreSQL schema for the 10-model research system

**Proposal only. Not applied to Supabase.** This file defines a target logical model, not the live schema. It is intentionally provider-neutral and normalized around fixtures, time-stamped observations, market selections, model versions, and evaluation.

## Entity map

- `competitions`, `seasons`, `teams`: stable reference data.
- `matches`: one canonical fixture with kickoff and finality metadata.
- `provider_ids`: maps provider-specific fixture/team/competition identifiers to canonical IDs.
- `match_team_stats`: long-form team statistics with stat code, value, source and observation time. Long form handles differing provider coverage without adding columns every time.
- `availability_reports`: timestamped injuries/suspensions; never infer pre-match availability from a later report.
- `odds_snapshots` and `odds_selections`: immutable time series, bookmaker, market line, selection and decimal price.
- `feature_snapshots`: model-specific feature payload computed at a recorded cutoff, with feature schema version.
- `model_runs` and `predictions`: model/version/config and probability output.
- `settled_predictions`: actual outcome, settlement rule, profit convention and evaluation state.

## Market ownership

1. 1X2: probabilities for home/draw/away.
2. Double Chance: derive 1X, X2, 12 from calibrated 1X2 probabilities unless validation proves a separately trained head adds value.
3. Handicap: derive settlement probabilities from a validated score distribution; Asian quarter-lines require push/half-win/half-loss settlement logic.
4. Total goals: score distribution generates Over/Under thresholds.
5. Home-team goals: home-goal distribution.
6. Away-team goals: away-goal distribution.
7. BTTS: joint score distribution, or a separately validated calibrated model.
8. Corners: independent corner-count distribution and corner-specific features.
9. Cards: separate card-count features, with referee and competition effects where covered.
10. Shots: separate shots and shots-on-target count/line models.

A market not supported by enough trustworthy historical data is disabled, not filled with a fabricated probability.

## Data-time rules

- Store timestamps as `timestamptz` and normalize instants to UTC.
- Never overwrite odds observations; insert new snapshots.
- Features used for a prediction must have `available_at <= generated_at < kickoff`.
- Post-match stats are targets/training labels only; they cannot enter that match's pre-match features.
- Keep provider raw payloads or auditable references where license and storage terms permit.
- Missing statistic is NULL/absent, never silently converted to zero.
- Stable IDs must be mapped through `provider_ids`; team names are not join keys.
- Preserve model, feature schema, source and settlement-rule versions for every evaluated prediction.

See `migrations/0001_research_schema.sql` for a draft DDL. Do not apply it until reviewed against the actual Supabase migrations, policies, grants and project conventions.
