# Data provider decision — API-Football only

Status: **selected and integrated in code** for this project. The Python client, tests, and manual snapshot workflow are committed. No real provider endpoint has been called from this coding session; exact coverage still needs to be verified for each target competition and season.

## Decision

- **Use API-Football (API-Sports) as the sole external football-data provider.**
- Do not integrate OddsPapi, Sportmonks, or a second provider.
- Build our own prediction models; API-Football is a data source, not the source of our predictions.
- Collect fixtures/results, match statistics, and bookmaker odds only where the account plan and competition coverage expose them.
- The API client is available, but collection is **manual-only** through GitHub Actions. The workflow requires the user-configured API_FOOTBALL_KEY secret and writes only a downloadable JSON artifact.

## Important odds-history limitation

API-Football documents that the `/odds` endpoint retains only approximately the last **seven days** of pre-match odds. Historical bookmaker odds from earlier dates cannot be assumed available for a multi-season backtest. To build our own odds archive, snapshots must be collected and timestamped prospectively, when the user manually runs the snapshot workflow.

The provider advertises a Pro quota of **7,500 requests/day** on its pricing page; the project must still confirm the user's active plan and current quota in the account. Pagination and per-fixture calls can consume quota quickly, so cache reference data and request only missing or stale data.

## Required coverage pilot (not yet run)

For every target league and season, record:
1. Fixture coverage, stable fixture IDs, final scores, and finality/status fields.
2. Availability of shots, shots on target, corners, yellow/red cards, possession, and xG where offered.
3. Injury/suspension availability and the timestamp/meaning of each field.
4. Exact bookmaker availability for **1xBet**, plus supported market and selection IDs.
5. Odds timestamps, update frequency, pagination, and the seven-day historical limitation.
6. Requests required for an initial backfill and for daily refresh under the 7,500/day quota.
7. Missingness per field, competition, season, and fixture.

Do not treat provider marketing coverage as proof that every fixture has every statistic. Persist field-level missingness, provider identifiers, retrieval time, and original source timestamps. Models must accept missing features rather than fabricate values.

## Official documentation

- [API-Football v3 documentation](https://www.api-football.com/documentation-v3)
- [Competition/season coverage](https://www.api-football.com/coverage)
- [Pricing and request quotas](https://www.api-football.com/pricing/)
- [Provider guide: odds endpoint and seven-day retention](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
- [Provider guide: quota optimization](https://www.api-football.com/news/post/how-to-optimize-api-sports-calls-and-quota-usage)

## Implementation boundary

No live API call was executed while implementing this change. The manual snapshot workflow can call API-Football after the user configures API_FOOTBALL_KEY and starts the workflow. It writes a JSON artifact only; Supabase operations, Telegram publication, and production wiring remain disabled.
