# Daily pipeline — single entry and exit

## Flow

1. Provide verified upcoming fixtures as JSON.
2. Run one entry point: `python -m football_analysis.daily_pipeline fixtures.json`.
3. The central pipeline validates inputs, skips started matches, calculates 1X2 probabilities with the independent Poisson baseline, ranks predictions, and writes one JSON report.
4. Inspect the generated preview.
5. Run `python -m football_analysis.telegram_publisher artifacts/daily_coupon.json` for a dry-run.
6. Only after review, use `--send` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` configured.

## Fixture input

The input must be a JSON array. Each item requires:
- `match_id`: stable unique ID from the verified fixture source
- `home`, `away`: team names
- `kickoff`: ISO 8601 timestamp with timezone
- `home_expected_goals`, `away_expected_goals`: pre-match estimates from a documented model

No fixture, expected-goal estimate, or odds are fabricated by the pipeline. It does not fetch live data or calculate ROI without timestamped historical odds. The market weight is temporarily zero; the original production repository is untouched.

## Telegram configuration

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the execution environment. Never commit secrets. Sending is disabled unless `--send` is explicitly supplied. The message is a probabilistic preview, not a guarantee.

## Daily automation

Do not schedule automatic publication until a trusted live fixture/feature provider is configured, the data contract is verified, and the full pipeline has passed tests. This repository intentionally has no cron workflow that could publish empty or fabricated predictions.
