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


## Local validation and baseline comparison

Run the full offline test suite with:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The chronological backtest uses verified `finished_at` timestamps when supplied. When missing, it uses a documented three-hour kickoff-based proxy; results relying on that proxy are exploratory only.

For baseline comparison, use `compare_baselines(predictions, results, odds_snapshots)`. It compares model probabilities against a uniform 1/3 baseline and normalized implied market probabilities, using only odds available at prediction time. Inspect `BaselineComparison.sample_size` and `market_sample_size` before interpreting scores.

The historical schema checklist is in [docs/historical-schema-audit.md](docs/historical-schema-audit.md). No Supabase query is run by this codebase; the real schema must be verified before any table-specific SQL or historical-data import.
