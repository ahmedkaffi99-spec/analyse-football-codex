# Initial data contract

This describes in-memory research objects only. It does not assert actual columns or relationships for `hist_matchs` or `hist_cotes`.

- Match: stable ID, timezone-aware kickoff, non-negative integer final scores.
- Prediction: stable match ID, timezone-aware generation time strictly before kickoff, H/D/A probabilities in [0,1] summing to 1.
- Odds snapshot: stable match ID, timezone-aware observation time, decimal H/D/A odds greater than 1.
- A backtest uses only odds observed no later than prediction generation and before kickoff; later closing odds are excluded.
- Duplicate prediction/result IDs and duplicate odds timestamps per match are rejected.
- Scores are evaluated only for IDs with both prediction and result; Brier and log loss include sample size.
- One-unit staking is a research convention, not a recommendation to bet. No bets are placed or coupons published.
- The original `POIDS_MARCHE=0.65` setting is untouched.
