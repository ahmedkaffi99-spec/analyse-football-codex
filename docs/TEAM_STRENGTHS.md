# Team-strength baseline

The offline module estimates normalized attack and defensive-weakness multipliers
from explicitly supplied historical final scores. Small samples are shrunk toward
league scoring averages. It produces expected goals (home xG, away xG) that can be
passed to the existing independent Poisson 1X2 baseline.

## Safety and limitations

- Only use results known before the target match kickoff; callers are responsible
  for chronological filtering to prevent data leakage.
- Team names are matched case-insensitively, not by provider ID; normalize aliases
  upstream before fitting.
- This is a research baseline, not a validated or calibrated production model.
- It performs no network, API, database, or Telegram operations.
- No live predictions or coupons are created by this module.
