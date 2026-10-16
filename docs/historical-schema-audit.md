# Historical schema audit — read-only preparation

Status: **not executed against Supabase**. This document is a checklist, not a claim about the live schema. Do not run SQL against any remote database without separate explicit authorization.

## Required evidence before writing table-specific queries

1. Export or inspect migrations and ORM models defining `hist_matchs` and `hist_cotes`.
2. Record primary keys, foreign keys, unique constraints, indexes, nullability, and column types.
3. Establish match identity mapping and whether IDs are provider-specific.
4. Establish timezone semantics for kickoff, result-finalization, and odds-observation timestamps.
5. Identify the authoritative final score and status indicating a completed match; exclude abandoned/postponed/live fixtures.
6. Identify odds market/selection vocabulary, decimal-odds units, bookmaker/provider, and snapshot timestamps.
7. Check duplicate rows, null rates, stale snapshots, invalid odds (<= 1), and score inconsistencies.
8. Verify competition/season coverage and historical depth per team without assuming column names.
9. Document query date, source, row count, exclusions, and reproducible checksums where possible.

## Safe workflow

- First read local migrations/models and produce a schema map.
- Prepare SELECT-only diagnostics against confirmed identifiers.
- Review every identifier against the schema before execution.
- Obtain explicit authorization before any remote database query.
- Keep credentials out of logs, commits, reports, and test fixtures.

## Acceptance criteria

- Stable match IDs can be joined without cross-competition collisions.
- Final scores have a documented finality rule and timezone-aware completion time.
- Odds snapshots can be ordered in time and linked to the correct market and selection.
- Historical training rows were available at prediction time; no future or closing odds leak into a backtest.
- Missingness, duplicates, coverage, and exclusions are reported before model evaluation.
