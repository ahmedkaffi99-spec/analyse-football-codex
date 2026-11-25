# Offline historical model comparison and coupon preview

This document describes two migrated, deterministic helpers. Neither is called by the live daily pipeline. They consume supplied data only and do not place bets, publish Telegram messages, or write to external services.

## API-Football quota handling

Module: src/football_analysis/api_football_client.py

The client now distinguishes daily quota exhaustion from transient HTTP 429 rate limits. A zero daily-remaining header or recognized daily-quota response text raises ApiFootballDailyQuotaError immediately without retry/sleep; other 429s retain bounded retry/backoff. The response body is used only for classification and is not included in the error message. The client remains explicitly call-driven; no provider request is made by tests.

## OddsPapi payload normalizer

Module: src/football_analysis/oddspapi_normalizer.py

normalize_oddspapi_payload(raw_payload, market_catalog, bookmaker="1xbet") accepts already captured provider JSON and catalogue mappings. It preserves raw market/outcome labels, validates decimal prices (>1 and finite), supports a list of events or one event, and reports events, bookmaker, market and outcome counts plus invalid prices. Status distinguishes no events, no bookmaker, no markets, no usable prices and success. It performs no network access; the OddsPapi API collector, quotas and retry logic are still unmigrated.

## Local preview API

Module: src/football_analysis/preview_api.py

Run it with `python -m football_analysis.preview_api --host 127.0.0.1 --port 8000`. The local HTTP facade exposes:
- GET /health
- POST /api/preview/1x2
- POST /api/preview/coupon
- POST /api/audit/coverage

The API uses only local request data and pure Python modules. It is loopback-only, accepts an optional bearer token, refuses non-loopback HTTP binding even when a token is supplied, limits request bodies to 1 MB, and never logs request payloads. For remote use, place it behind a separately reviewed HTTPS reverse proxy. It is not a database-backed production API.

## Historical model selector

Module: src/football_analysis/historical_model_selector.py

- compare_market(model_a_rows, model_b_rows, n_min=30): compares two model histories on one market.
- select_by_market(model_a_by_market, model_b_by_market, n_min=30): returns independent comparisons per market.
- Decision is ROI only, with a minimum 1-percentage-point ROI separation; otherwise tie.
- Returns sample size, settled-bet count, win rate, Brier score, log loss, calibration bins, average model edge, profit units and ROI.
- Chronological-half stability is reported only when all rows are dated and each half has sufficient odds-backed settled bets. This diagnostic is not a holdout and does not authorize adaptive production selection.

Each row can use either target field names (probability, decimal_odds, result, date) or source-compatible French fields (proba_pct, cote, resultat, jour). Legacy proba_pct is interpreted as percentage. Outcomes accepted include win/won/gagne/gagné, loss/lost/perdu and push/refund/rembourse. Pushes are excluded from settled scoring and ROI. Rows without valid odds still contribute to graded sample and proper scoring metrics but not ROI.

## Deterministic market-family taxonomy

Module: src/football_analysis/market_families.py

family_for_category and classify_market map result/double chance, total/team goals, BTTS, goal handicap, corners, cards, shots, fouls and offsides to stable family IDs. Unknown categories remain explicitly grouped as derived. group_candidates_by_family preserves candidate order for future specialist review. This ports taxonomy only; source AI specialist prompts, production facts, token budgeting and review-veto limits remain unimplemented.

## Count-stat Bayesian shrinkage

Module: src/football_analysis/statistical_shrinkage.py

The migrated count-market rate now shrinks each team's measured recent mean toward the source prior using five pseudo-observations by default. This reduces the influence of extreme small samples and still requires both teams to have at least three observed matches in market_agents.py. Passing shrink_k=0 to team_metric_rate disables the shrinkage for an offline comparison. Metrics without a registered prior (currently red cards) remain raw rather than using a fabricated prior. Supported count markets also apply the source-measured venue multiplier to the home rate and its complement to the away rate, preserving the sum for equal means. Prior values, venue multipliers and k are not yet independently recalibrated on the target's historical data.

## Coupon risk preview

Module: src/football_analysis/risk_selection.py

- RiskConfig defines coupon leg limits, per-fixture cap, odds bounds, probability/edge filters, market allow/exclude lists and calibration minimums.
- select_coupon_preview(candidates, config) returns a preview, rejection reasons, or refuses to generate a coupon when the minimum leg count is not met.
- Candidates must explicitly mark binary=True and provide fixture id, market, selection, valid decimal odds and probability.
- Ranking is deterministic: probability descending, then edge descending (when present). No fitted/learned weights.
- Default cap is one pick per fixture. This intentionally avoids same-fixture correlation that the target currently cannot estimate reliably.
- Combined probability and total odds are preview-only; combined probability assumes independence across fixtures.

Example (offline data only):

```python
from football_analysis.risk_selection import RiskConfig, select_coupon_preview

candidates = [
    {"fixture_id": "fixture-a", "market": "1x2", "selection": "home",
     "probability": 0.62, "decimal_odds": 1.90, "edge": 0.04, "binary": True},
    {"fixture_id": "fixture-b", "market": "total_goals", "selection": "under 3.5",
     "probability": 0.71, "decimal_odds": 1.70, "edge": 0.06, "binary": True},
]
preview = select_coupon_preview(candidates, RiskConfig(coupon_min=2, coupon_max=5))
```

## Important limitations

- These helpers are not integrated into production orchestration.
- ROI selection is vulnerable to variance, multiple comparisons, small or biased samples; do not use it to promote a model without a separate chronological walk-forward/holdout.
- Correlation between fixtures, bankroll, staking, odds availability and push-aware Asian lines are not modelled in this preview.
- Rejection reasons are audit outputs; a preview must not be treated as a recommendation or execution authorization.
