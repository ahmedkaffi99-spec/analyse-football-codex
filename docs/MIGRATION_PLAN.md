# Migration of analyse-football into analyse-football-codex

## Source of truth and safety
- `ahmedkaffi99-spec/analyse-football` is the reference repository and must remain read-only.
- Work is performed only in `ahmedkaffi99-spec/analyse-football-codex`, branch `codex/full-system-from-original`.
- Never copy secrets, environment files containing credentials, tokens, or live data.
- Do not call Supabase, publish to Telegram, place bets, or run production pipelines during migration.

## Target
Port the original repository's full functional system into Codex, adapting it to the Codex structure rather than blindly overwriting files. Keep the existing Codex API-Football daily pipeline and preserve its current behavior until tests prove the migrated system is compatible.

## Migration stages
1. Inventory and architecture mapping: compare source/target files, identify overlapping modules and interfaces.
2. Core domain and probability: team names, competition catalog, market definitions, probability models, Poisson, feature calculations, strengths.
3. Data providers and collection: API-Football fixtures, odds providers, matching, rate limits, retries, normalized IDs, snapshots, coverage diagnostics.
4. Decision/market system: all-market analysis, agents/specialists, deterministic selection, coupon profiles, risk limits, validations, deduplication, coverage guarantees and explanations.
5. History, learning and evaluation: local/persistent history adapters, backtesting, walk-forward, calibration, comparison and shadow evaluation.
6. Orchestration and services: daily pipelines, central engine, backend/API, persistence adapters, budget and alert services; secrets remain environment-only.
7. Operational workflows: GitHub Actions, scheduled verification, result checking, diagnostics, Telegram publishing kept disabled unless separately authorized.
8. Tests and parity: port tests, add migration/parity tests, run offline test suite, audit source/target coverage.
9. Documentation and deployment: configs, env example, SQL/migrations, README, deployment instructions, architecture and rollback notes.

## Known regression to prevent
Fixture/odds coverage must be explicit. Every fixture discovered at collection time must be accounted for as: matched to provider fixture, odds available, market complete, selected, or excluded with a machine-readable reason. No fixture should silently disappear. Fixture identity should prefer stable provider IDs and only use conservative name/date/competition matching as a documented fallback.

## Completion criteria
- Source reference inspected read-only.
- Target modules migrated and adapted.
- Secrets and real external actions excluded.
- Tests passing in the target branch.
- Coverage report explains fixture/odds/market/selection losses.
- No changes merged to `main` until the user explicitly requests it.
