# Data contract — ten-model data foundation

## Entities

- matches: one provider fixture with timezone-aware kickoff and stable provider identity.
- match_results: final score and verified final status, separate from fixture metadata.
- team_match_stats: one row per fixture side and provider. Unsupported values remain NULL; raw payload and coverage status are retained.
- football_odds: timestamped snapshots restricted to 1xBet, including market, selection and line/point.
- team_absences: timestamped pre-match availability reports; usable only if observed before kickoff.
- match_feature_snapshots: versioned features by domain (match/goals/corners/cards/shots/shared), with cutoff strictly before kickoff.
- data_ingestion_runs: counts, status and errors for every collection run.

## Domain separation

- match: outcome, draw and goal-difference features.
- goals: goals, xG/xGA, shots and scoring splits.
- corners: corners for/against and optional attacking-volume context.
- cards: cards, fouls, referee context and settlement rules.
- shots: total/on-target/off-target/blocked shots and optional possession/xG.
- shared: common identity, time, venue and audited team-strength features only.

Missingness and coverage are first-class, not imputed as zero.

## Data leakage

A database trigger should reject feature snapshots when feature_cutoff_at or generated_at is at or after kickoff. Feature-generation code must also ensure every input result, injury report and odds observation was available at the cutoff. The trigger is a guardrail, not a substitute for chronological feature logic.
