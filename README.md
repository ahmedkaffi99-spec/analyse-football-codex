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
- No live football API, Supabase, database connection, or Telegram integration is enabled.
- No real betting coupons are generated or published.
- The existing production setting `POIDS_MARCHE=0.65` is not changed by this project.
- Development happens on a dedicated branch; do not merge into `main` without explicit approval.

## Development

Requires Python 3.11+.

```bash
python -m unittest discover -s tests -v
```

See `docs/roadmap.md` for the implementation sequence and `docs/data-contract.md` for the initial data rules. The schema of `hist_matchs` and `hist_cotes` remains unverified; SQL examples must not assume their columns until migration/model files are available.
