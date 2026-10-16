# API source decision and coverage matrix

## Initial decision

- Fixtures, final scores, standings, team statistics, lineups and injuries: API-Football is the primary candidate because the project already has an adapter. Verify the subscribed plan's historical depth and league-by-league field coverage before bulk backfill.
- Odds: retain the existing collector restricted to 1xBet. Store every observed price with a timestamp; never use a quote captured after kickoff in a pre-match feature set.
- Optional statistics alternative: Sportmonks is a candidate if API-Football's historical coverage is insufficient for shots, corners, cards or xG. Add it only after a small league-by-league coverage test and cost review.
- OddsPapi documents current and historical odds endpoints, but is not selected as the match-statistics source. 1xBet remains the only target bookmaker.

## Model-to-data map

| Model | Historical labels | Pre-match features | Coverage gate |
|---|---|---|---|
| 1. 1X2 | final score / outcome | form, venue splits, goals, xG if available, standings/Elo | finished results and stable fixture IDs |
| 2. Double chance | H/D/A outcome | same base as 1X2; derive 1X/X2/12 from calibrated H/D/A | probabilities reconcile consistently |
| 3. DNB / Asian handicap | goal difference and settlement | expected goals and goal-difference distribution | push and quarter-line settlement tested |
| 4. Total goals | total final goals | goals for/against, xG/xGA, shots, venue splits | market definitions consistent |
| 5. Home-team goals | home score | home attack, away defensive weakness, home splits | home/away side mapping verified |
| 6. Away-team goals | away score | away attack, home defensive weakness, away splits | home/away side mapping verified |
| 7. BTTS | both scores greater than zero | attack/defence, xG/xGA, scoring frequency | both final scores present |
| 8. Corners | final corners by team and total | corners for/against, venue splits, shots/possession | historical corner coverage measured by league |
| 9. Cards | settled card count by bookmaker rules | cards for/against, fouls, referee, venue splits | weighting and settlement rules documented |
| 10. Shots | shots and shots on target by team | shots for/against, possession, xG, venue splits | statistic definitions and missingness audited |

## Coverage and leakage rules

For each league and season, record fixture coverage, finished results, shots, shots on target, corners, cards, possession, xG, injuries/lineups before kickoff, duplicates, missingness, timezone consistency and historical 1xBet odds depth by market.

Do not infer that a null statistic is zero. Keep NULL plus a coverage status. Treat xG, injuries, dangerous attacks, referee data and historical 1xBet prices as optional until the subscription plan and actual responses confirm availability.

Store raw payloads and normalized fields. Use provider plus provider fixture ID as external identity. Keep observation timestamps. Features must use only information available strictly before kickoff. Split train/validation/test chronologically, never randomly across time. Produce a league/season coverage report before training a market-specific model.
