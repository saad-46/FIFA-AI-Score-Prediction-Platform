# Changelog

## 2026-07-02 — Production readiness audit

A six-engineer audit pass covering the tournament simulation engine, ML
pipeline, database layer, backend API, performance, and test coverage. All
changes below are already on disk; this entry summarizes them for anyone
skimming release history. See `KNOWN_ASSUMPTIONS.md` for what was flagged
but deliberately left unfixed, and the individual `ARCHITECTURE.md` /
`MODEL_PIPELINE.md` / `TOURNAMENT_ENGINE.md` docs for full technical detail.

### Critical fixes

- **Tournament simulation was silently broken.** A dict key-case mismatch
  (`"Group"` vs. `"group"`) inside `_run_simulation_batch` caused a
  `KeyError` in every single Monte Carlo batch, on every run — caught and
  logged inside the `ProcessPoolExecutor` worker rather than raised, so
  `POST /tournament/simulate` always returned `group: 1.0` (correct) and
  **every other stage (r32/r16/qf/sf/third_place/final/winner) as `0.0`,
  for every team, with zero visible error.** Fixed the key; added real
  failure-rate tracking (new `TournamentSimulationError`, raised — and
  mapped to **HTTP 503** — if more than 25% of simulation batches fail,
  instead of silently returning skewed or all-zero results). See
  `TOURNAMENT_ENGINE.md`.
- **Missing scaler could silently corrupt predictions.** If
  `xgboost_model.pkl` was present but `scaler.pkl` was missing,
  `MatchPredictor` used to feed raw, unscaled features into a model trained
  on standardized data — producing plausible-looking but meaningless
  predictions with no error. Now falls back to the historical-average path
  and logs an error instead.
- **Schema/ORM column-name drift.** `database/schema.sql` and the Python
  codebase disagreed on prediction column names
  (`home_expected_goals`/`away_expected_goals` vs.
  `expected_home_goals`/`expected_away_goals`), which would have broken
  every prediction INSERT against a freshly-provisioned database. Aligned.
- **NaN propagation in feature engineering.** `compute_head_to_head` and
  `compute_team_rolling_stats` didn't filter out NULL-scored (unplayed/
  scheduled) matches before windowing, which could deflate or NaN rolling
  stats used at inference time. Both now drop null-score rows before
  windowing/aggregation.
- **Startup used to lie about health.** A misconfigured `DATABASE_URL`
  previously let the API start and report `/health` as healthy while every
  DB-backed route 500'd on first use. Startup now fails loudly (raises) if
  the database isn't reachable.
- **`neutral_venue` insight-suppression bug.** The "home advantage" insight
  in `prediction_service.py` never suppressed itself for neutral-venue
  matches — it was reading a `neutral_venue` key back out of the predictor's
  output dict that the predictor never actually emits, so the check always
  evaluated to "not neutral." Fixed to use the caller's actual request flag.
- **N+1 query and a silently-ignored filter** in the matches endpoint's
  service layer (`match_service.py`) — the `team` query parameter on
  `GET /matches` was accepted but never applied to the query.
- **SHAP feature-name mismatch** — `elo_diff` (expected by the SHAP
  formatter) vs. `elo_difference` (the actual feature name) meant Elo's
  attribution silently never appeared in prediction explanations. Both names
  now map correctly.

### New features

- **Official FIFA World Cup 2026 reference data**, extracted from the
  official wallchart PDF (2026-07-02): 12 groups / 48 teams
  (`groups.json`), all 104 real fixtures with dates/kickoff times/venues
  (`schedule.json`), and the 16 host cities with region groupings
  (`venues.json`). Verified 104/104 matches extracted, correct stage-count
  breakdown, zero uncertain reads (one documented structural inference for
  the bronze-final/final participant codes — see `KNOWN_ASSUMPTIONS.md`).
- **New endpoints:** `GET /api/v1/tournament/2026/groups`,
  `GET /api/v1/tournament/2026/schedule` (filterable by `stage`/
  `venue_city`).
- **`use_fifa_2026_groups: bool` flag** on `POST /api/v1/tournament/
  simulate` — simulate the real 2026 bracket without the caller needing to
  paste all 48 team names into the request body.
- **Request validation hardening** — `TournamentSimulationRequest` gained a
  Pydantic v2 `model_validator` enforcing exactly 48 teams and no
  duplicate team names across groups (422 on violation).
- **Accurate Pot-1 runner-up seeding** — the R32 bracket's "best 4
  runners-up" used to always be groups A-D by list position, regardless of
  actual ranking. Now properly ranked by points → GD → GF → H2H across all
  12 runners-up, matching real FIFA 2026 draw rules.
- **`database/seed_fifa_2026_teams.sql`** — idempotent (`ON CONFLICT (name)
  DO NOTHING`) seed script for all 48 official 2026 teams (name + country
  only; other fields intentionally left NULL — not present in source data).
- **Honest synthetic-data labeling** — the `/matches/analytics/
  goal-distribution` endpoint can't be made real (no goal-minute event data
  exists in the schema); rather than faking precision, its response schema
  now carries an explicit `is_synthetic: bool = True` field.
- **`is_synthetic`/pagination/status-code cleanup** across the analytics and
  predictions endpoints, including `POST /predictions/{id}/save` now
  correctly returning **201 Created**, and API responses no longer leaking
  raw internal exception text to clients.

### Performance improvements

Benchmarked against a realistic 45,000-match synthetic dataset through the
real trained model bundle:

- **Prediction latency: ~3191ms → ~150-220ms median (roughly 15-20x
  faster).** Root cause of the original cost: `build_team_index` did a full
  `.iterrows()` scan of the entire match history on every single request.
  Vectorized via `groupby().indices`, plus a data-generation-keyed cache so
  the index isn't rebuilt when the underlying DataFrame hasn't changed.
- **Tournament matchup precompute (48 teams, 1128 pairs): ~268s → ~13.3s
  (roughly 20x faster).** Added `MatchPredictor.predict_batch()` — one
  vectorized model call across the whole batch instead of 1128 sequential
  ones — plus per-team stats memoization.
- **Team stats aggregation (220 teams): ~4588ms → ~55ms (roughly 83x
  faster).** Replaced a per-team DB-query-plus-full-scan loop with a single
  grouped pandas aggregation.
- **New in-process TTL cache** (`app/core/cache.py`, stdlib only — no Redis
  anywhere in this stack) applied to `GET /teams/top` and
  `GET /analytics/global`.
- Connection pool sizing tuned for the actual 2-worker Render deployment
  (`pool_size=5, max_overflow=5`).
- Verified (not changed): `ProcessPoolExecutor` pickling overhead for the
  tournament matchup cache is negligible (~1.5ms/submit); tournament
  simulator memory use is bounded regardless of `n_simulations` (aggregated
  counts only, no per-simulation history retained).

### Test coverage

Backend test suite grew from **13 to 52 passing tests**, zero failures, zero
regressions, nothing weakened to force a pass. New files: `test_fifa_2026_
data.py`, `test_cache.py`, `test_predictor.py`; expanded `test_tournament.
py`, `test_simulator.py`, `test_predictions.py` with regression coverage
directly proving the tournament fix (winner probabilities across all 48
teams now sum to ~1.0, not 0.0), the new FIFA 2026 endpoints, request
validation (422s), robustness edge cases (missing/corrupted model file,
unknown team names), and the new cache decorator.

### Known limitations carried forward (not fixed in this pass)

See `KNOWN_ASSUMPTIONS.md` for full detail on each:

- **Elo ratings are not populated at inference time** — `compute_dynamic_
  elo()` runs during training but never on the request-time DataFrame, so
  `elo_difference` is a constant `0.0` on every live prediction despite
  being a real, trained-on signal. Flagged with a suggested fix direction.
- **`ON DELETE CASCADE` from `teams` to `matches`** is a latent data-loss
  footgun if a team-delete endpoint is ever added (none exists today).
  Recommended `ON DELETE RESTRICT` instead; left as a product decision.
- Cosmetic: `test_tournament.py` contains `TournamentSimulator` unit tests
  while `test_simulator.py` contains the HTTP endpoint tests — file names
  are swapped relative to the usual convention. Flagged only, not renamed.
