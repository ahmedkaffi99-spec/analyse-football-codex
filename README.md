# Analyse Football Codex

Independent, test-first workspace for football match analysis and historical backtesting.

## Scope of the first iteration

- Pure Python core; no network access in the analysis engine.
- Typed domain objects for matches, predictions, and timestamped odds snapshots.
- Probability utilities and a backtest evaluator with proper scoring metrics.
- Strict temporal validation: odds used for a prediction must be timestamped before kickoff.
- Synthetic fixtures only until the database schema and data provenance are verified.

## Safety boundaries

- This repository is developed independently; no files are copied from `ahmedkaffi99-spec/analyse-football`.
- API-Football is the only external football-data provider. Its resilient client and a **manual-only** odds snapshot workflow are available; a real call requires the `API_FOOTBALL_KEY` GitHub Actions secret and a manual workflow run.
- The snapshot workflow writes a downloadable JSON artifact only. It does not write to Supabase, send Telegram messages, or publish betting coupons. Those integrations remain disabled.
- The existing production setting `POIDS_MARCHE=0.65` is not changed by this project.
- Development happens on a dedicated branch; do not merge into `main` without explicit approval.

## Development

Requires Python 3.11+.

```bash
python -m unittest discover -s tests -v
```

See `docs/roadmap.md` for the implementation sequence and `docs/data-contract.md` for the initial data rules. The schema of `hist_matchs` and `hist_cotes` remains unverified; SQL examples must not assume their columns until migration/model files are available.


## Local validation and baseline comparison

Run the full offline test suite with:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The chronological backtest uses verified `finished_at` timestamps when supplied. When missing, it uses a documented three-hour kickoff-based proxy; results relying on that proxy are exploratory only.

For baseline comparison, use `compare_baselines(predictions, results, odds_snapshots)`. It compares model probabilities against a uniform 1/3 baseline and normalized implied market probabilities, using only odds available at prediction time. Inspect `BaselineComparison.sample_size` and `market_sample_size` before interpreting scores.

The historical schema checklist is in [docs/historical-schema-audit.md](docs/historical-schema-audit.md). No Supabase query is run by this codebase; the real schema must be verified before any table-specific SQL or historical-data import.


## Ten-model data foundation (offline proposal)

- Sole data provider: [API-Football](docs/api-provider-matrix.md). This is a selected provider, but live coverage has not been tested; its pre-match odds endpoint retains only about seven days, so historical odds must be captured prospectively.
- Proposed normalized schema: [docs/database-schema.md](docs/database-schema.md) and [migrations/0001_research_schema.sql](migrations/0001_research_schema.sql). The SQL is a draft and has **not** been applied to Supabase.
- Model-specific data requirements: [docs/model-data-contract.md](docs/model-data-contract.md).
- Point-in-time rolling feature engine: `football_analysis.feature_engine`. It uses only supplied history, filters by final-whistle time and stat availability time, keeps missing stats as `None`, and emits quality flags. It has no network or database access.

The first feature version covers rolling goals and available xG, shots, corners and card stats with overall and venue-specific windows. Elo, standings, injuries and durable historical storage remain later tasks and must be added with explicit point-in-time provenance.


## Ten-model data foundation (offline proposal)

- Sole data provider: [API-Football](docs/api-provider-matrix.md). Live coverage has not been tested; pre-match odds history is limited to about seven days, so future odds snapshots must be captured prospectively.
- Proposed normalized schema: [docs/database-schema.md](docs/database-schema.md) and [migrations/0001_research_schema.sql](migrations/0001_research_schema.sql). The SQL is a draft and has **not** been applied to Supabase.
- Model-specific data requirements: [docs/model-data-contract.md](docs/model-data-contract.md).
- Point-in-time rolling feature engine: `football_analysis.feature_engine`. It uses supplied history only, filters by final-whistle time and stat availability time, preserves missing statistics as `None`, and emits quality flags. It has no network or database access.

The first feature version covers rolling goals and available xG, shots, corners and card stats with overall and venue-specific windows. Elo, standings, injuries and durable historical storage remain later tasks and require explicit point-in-time provenance.


## API-Football integration (manual, API-only)

- Client: `football_analysis.api_football_client.ApiFootballClient`; reads `API_FOOTBALL_KEY` from the environment, uses bounded retries, handles 429/5xx responses, and exposes quota headers.
- Snapshot command: `python -m football_analysis.provider_snapshot --date YYYY-MM-DD --max-pages 10 --output artifacts/api_football_odds.json`.
- GitHub Actions: run **Manual API-Football odds snapshot** from the Actions tab. Only `API_FOOTBALL_KEY` is required; the workflow uploads a JSON artifact.
- This workflow is manual-only. No live request was run during code authoring. Supabase writes and Telegram publication are deliberately disabled.
- API-Football's pre-match odds history is limited to about seven days; snapshots collected now cannot recreate missing historical prices.
