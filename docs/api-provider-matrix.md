# Data/API provider decision — research phase

Status: public-documentation review only. No credentials were used and no provider endpoint was called. Exact coverage must be verified for the competitions and seasons we actually intend to model before purchase or collection.

## Provisional recommendation

- **Primary candidate for historical match statistics:** API-Football (API-Sports), because the project already has an adapter in its research history and the provider documents fixtures, fixture statistics, injuries, lineups, standings, and pre-match odds. It advertises a Pro quota of 7,500 requests/day, but odds history is limited: the provider says the `/odds` endpoint retains only about seven days. Do not assume it can backfill years of historical bookmaker prices.
- **Specialist fallback / candidate for richer statistics:** Sportmonks. Its docs describe team match statistics including shots, shots on target, corners, cards and possession, with xG available for selected competitions or add-ons. Historical depth and statistic availability vary by league/season and plan.
- **Odds specialist:** OddsPapi, since its docs expose historical odds as a dedicated endpoint and bookmaker/market catalogs. Confirm 1xBet is included, the exact markets/settlement rules are covered, and how far back the historical odds go under the chosen plan.
- **Do not add all providers immediately.** First run a coverage pilot across target leagues and seasons, compare data completeness and IDs, then choose one statistics provider and one odds provider only if needed.

## Capability matrix (docs-level, not yet validated against our target leagues)

| Data requirement | API-Football | Sportmonks | OddsPapi |
|---|---|---|---|
| Fixtures, results, seasons | Documented | Documented | Fixtures documented; score endpoint exists |
| Team stats: shots, corners, cards, possession | Fixture statistics endpoint; check coverage per league/season | Rich fixture statistics documented; exact depth varies | Not the main purpose; do not rely on it |
| xG | Verify per league/season and endpoint response | Available for selected competitions / add-on | Not the main purpose |
| Injuries / suspensions | Endpoint documented; coverage varies | Check product/plan and competition coverage | Not the main purpose |
| Pre-match odds | Documented | Odds API documented | Core capability |
| Historical odds for multi-season backtest | Major caveat: docs say `/odds` retains only the last seven days; capture prospectively or use another source | Verify archive and plan in writing | Dedicated historical-odds endpoint documented; depth/markets need confirmation |
| Bookmaker-specific 1xBet | Verify bookmaker/market coverage before relying on it | Verify exact bookmaker coverage | Verify 1xBet bookmaker ID and market availability |
| Quota / cost fit | Current pricing page advertises Pro at 7,500 requests/day; confirm account entitlement and current limits | Plan/league-dependent; request a quote or inspect plan | Plan/quota-dependent; confirm contract |

## Primary documentation

- [API-Football documentation and coverage](https://www.api-football.com/documentation-v3), [coverage matrix](https://www.api-football.com/coverage), [pricing](https://www.api-football.com/pricing/), [historical odds limitation explained in provider guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide).
- [Sportmonks football API documentation](https://docs.sportmonks.com/v3), [statistics API overview](https://www.sportmonks.com/football-api/football-stats-api/), [historical/statistical coverage FAQ](https://www.sportmonks.com/faq/).
- [OddsPapi API v4 docs](https://oddspapi.io/en/docs), [historical odds endpoint catalogue](https://oddspapi.io/en/docs/methods).

## Pilot acceptance criteria before committing

For each target league-season, measure:
1. fixture coverage and stable match IDs;
2. final scores and reliable finality/status fields;
3. completeness of shots, shots on target, corners, yellow/red cards and possession;
4. xG availability and its provenance;
5. injury/suspension coverage and timestamps;
6. odds coverage for the exact bookmaker, market, selection and observation time;
7. historical depth and gaps by season;
8. request cost to backfill and daily refresh cost.

Do not treat provider marketing coverage as proof that every fixture has every statistic. Store field-level missingness and source provenance. No live API integration is enabled by this document.
