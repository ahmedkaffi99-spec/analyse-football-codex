# API-Football quota-safe collection plan

## Quota assumption
The user reports a quota of 7,500 requests/day. Treat this as a configurable ceiling, not a hard-coded guarantee. Confirm the plan and remaining requests with the provider account/status endpoint before a large backfill. Respect separate per-minute limits and provider response headers.

## Budget policy
- Keep a daily request ledger by endpoint, timestamp, HTTP status and purpose.
- Until actual usage is measured, plan against at most 80% of the reported quota (6,000 calls), retaining 20% as a safety margin.
- Prioritize fixtures/results and required historical statistics; request lineups/injuries only when useful close to kickoff.
- Cache finished fixtures and statistics; re-fetch only when missing, incomplete or explicitly refreshed.
- Paginate only when needed and stop when no further pages exist.
- Retry transient errors with bounded exponential backoff; never retry quota exhaustion repeatedly.
- Honor per-minute limits and Retry-After when supplied.
- Never infer that a missing statistic equals zero.
- Keep 1xBet as the only target bookmaker for odds. Do not assume every 1xBet market or historical quote is available through API-Football.
- Run a league/season coverage audit before a large backfill.

## Current offline coverage audit
Run this on a provider export; it does not call API-Football or Supabase:

    python -m football_analysis.coverage_audit export.json --output coverage-report.json
    python -m football_analysis.coverage_audit export.csv --output coverage-report.json

Each league/season report includes unique fixtures, finished matches, duplicate rows and availability percentages for scores, shots, shots on target, corners, cards, possession, xG/xGA, lineups, injuries and 1xBet odds observations.

## Safety boundaries
The audit only reads local CSV/JSON exports. It does not call external APIs, read secrets, execute SQL, write to Supabase or publish to Telegram. Database integration is a separate, explicitly approved step.
