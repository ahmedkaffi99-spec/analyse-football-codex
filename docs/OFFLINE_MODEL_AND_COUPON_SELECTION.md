# Offline historical model comparison and coupon preview

This document describes two migrated, deterministic helpers. Neither is called by the live daily pipeline. They consume supplied data only and do not place bets, publish Telegram messages, or write to external services.

## Historical model selector

Module: src/football_analysis/historical_model_selector.py

- compare_market(model_a_rows, model_b_rows, n_min=30): compares two model histories on one market.
- select_by_market(model_a_by_market, model_b_by_market, n_min=30): returns independent comparisons per market.
- Decision is ROI only, with a minimum 1-percentage-point ROI separation; otherwise tie.
- Returns sample size, settled-bet count, win rate, Brier score, log loss, calibration bins, average model edge, profit units and ROI.
- Chronological-half stability is reported only when all rows are dated and each half has sufficient odds-backed settled bets. This diagnostic is not a holdout and does not authorize adaptive production selection.

Each row can use either target field names (probability, decimal_odds, result, date) or source-compatible French fields (proba_pct, cote, resultat, jour). Legacy proba_pct is interpreted as percentage. Outcomes accepted include win/won/gagne/gagné, loss/lost/perdu and push/refund/rembourse. Pushes are excluded from settled scoring and ROI. Rows without valid odds still contribute to graded sample and proper scoring metrics but not ROI.

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
