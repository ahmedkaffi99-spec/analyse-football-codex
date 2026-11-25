# Reference migration audit (read-only source)

**Scope:** ahmedkaffi99-spec/analyse-football is inspected only; target writes are limited to codex/full-system-from-original. This audit is a migration checkpoint, not a declaration of parity or production readiness.

## Existing target coverage

| Source capability | Target/adaptation | Status |
|---|---|---|
| Team names, aliases, normalization | team_names.py, match_resolution.py | Ported/adapted; needs cross-provider parity fixtures |
| Competition catalogue | competitions.py | Ported; coverage audit needed |
| API-Football fixtures/stat client | api_football_client.py, daily_api_pipeline.py | Ported; provider quota/coverage checks remain |
| Odds collection and provider snapshots | collect_odds.py, provider_snapshot.py | Partial; source OddsPapi/provider-specific behaviours not fully parity-tested |
| Market catalogue and probability math | markets.py, all_markets.py, poisson.py, probability.py | Ported/adapted; integer-line pushes and market-specific distributions remain gaps |
| Features/team strengths | feature_engine.py, strengths.py, statistical_shrinkage.py | Count-market means now shrink toward source priors (k=5); historical feature parity, home-advantage corrections and calibration remain |
| Market specialists / edge / value | market_agents.py, value_analysis.py, probability_blend.py | Partial; several source market families/LLM review rules not migrated |
| Bookmaker no-vig consensus | bookmaker_consensus.py | Ported; input validation and duplicate-market handling hardened in this branch |
| Coupon profile and risk | coupon_profiles.py, daily_bet_cap.py, risk_selection.py | Offline candidate filtering/preview ported; production family agents, selection constraints and daily cross-run dedupe need parity review |
| Backtest and baseline evaluation | backtest.py, baseline_comparison.py, walk_forward.py, historical_model_selector.py | Ported foundation plus offline per-market ROI/Brier/log-loss/calibration; production-path parity, historic datasets and out-of-sample calibration remain incomplete |
| Daily orchestration | daily_pipeline.py, daily_api_pipeline.py | Adapted/offline-first; source production orchestrator/agent path not ported |
| Persistence/database schema | supabase_persistence.py, SQL migrations | Foundation only; API/schema compatibility and offline persistence tests still needed |
| Telegram output | telegram_publisher.py | Isolated/opt-in; real publishing remains disabled during migration |
| GitHub Actions | .github/workflows/ | Offline tests and safe previews exist; live integrations deliberately disabled |

## Audited source areas and remaining migration work

### bet_agent/
- collecte_donnees.py, fournisseurs.py, adaptateur_api_football.py: provider selection, quotas, fallback, retry and fixture/odds coverage. Target collector exists, but provider-specific behaviours and coverage accounting must be checked fixture-by-fixture.
- analyser_et_envoyer.py, modele_probabilites.py, moteur_deterministe.py, vote.py, agent_pilote.py, agent_strategie.py: production model path, xG fallback/shrinkage, deterministic math and AI orchestration. Not yet production-parity migrated.
- agents_familles.py, consensus_bookmakers.py, profils_smart.py, desequilibre.py, handicaps.py, coupons_score_exact.py, plafonds_coupon.py: specialist family rules, market consensus, risk, handicaps, exact score and cross-run caps. Consensus is adapted; specialist/risk rules remain incomplete.
- backtest_*.py, phase2_*.py, phase5_comptages.py, phase6_stats_vs_marche.py, historique_local.py, verifier_resultats.py, verifier_stats_detaillees.py: production-path and market-depth evaluation, history, grading and comparison. Core evaluation modules exist, but source parity, real historical replay and calibration have not been verified.
- AI provider budget/diagnostics and coupon text/Telegram safety need migration/review; no credentials or send operations are allowed here.

### moteur/ and moteur_central/
- Pure model contracts, feature calculations, Poisson/negative-binomial market math, specialist catalogue, calibration, backtest, profiles, deterministic selection and model-comparison shadow logic.
- Target now has an offline per-market historical model selector with ROI, Brier, log-loss, calibration bins, edge and chronological stability checks. It is not wired into production selection; the full central shadow selector, model registry and all source specialists remain missing.

### backend/app/
- FastAPI configuration, database models, auth/guards, routers for matches/coupons/runs, persistence, archives, stats, alerts, budgets, learning, scheduled verification and pipeline service adapters.
- Target currently has no equivalent full backend/router/service layer. Persistence SQL and pipeline adapters are a foundation, not a migrated backend.

### Operational workflows and documentation
- Source scheduled daily pipeline, data listing, result verification, learning/backfill and diagnostics workflows are not all migrated.
- Live Supabase writes, Telegram delivery, live external collection and betting must remain off during migration. Workflows should be safe previews/offline checks only.

## Priority next steps

1. Add source-to-target parity tests for provider fixture matching, all-fixture coverage states and odds-market completeness.
2. Port pure source production model functions behind explicit target contracts; keep API/LLM calls out of unit tests.
3. Port specialist family market coverage and coupon constraints with deterministic offline tests.
4. Port source central shadow comparison, calibration and historical evaluation; enforce minimum sample sizes and temporal splits.
5. Implement the backend API/service surface and persistence adapters with mocked/offline tests only.
6. Migrate result grading, scheduled checks, diagnostics and learning/backfill workflows in safe preview mode.
7. Final audit: source inventory coverage, tests/CI green, data leakage/temporal checks, secrets scan, schema compatibility and documented limitations.

## Safety and completion gates

- Do not modify source repository or main; do not merge.
- Never include secrets in source, logs, test fixtures or artifacts.
- No real API write, Supabase write, Telegram publish or wager.
- Migration completion requires verified coverage, offline tests/CI, documented unresolved gaps, and an explicit review of the production path—not simply a green unit-test run.
