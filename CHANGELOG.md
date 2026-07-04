# Changelog

## 2026-07-04 (later) — Live database validation pass

Raw network access to the live Supabase Postgres project
(`<project-ref>`) became reachable from this dev environment for the
first time this session — every prior entry in this changelog and the docs
it references (`DATABASE_SCHEMA.md`, `DATA_PIPELINE.md`) was written under
the accurate-at-the-time assumption that the DB was unreachable. This entry
covers what changed once it actually became reachable: two real bugs found
and fixed that could not have been caught before (they only manifest
against a live, queryable database), a handful of smaller robustness fixes,
a code cleanup pass, and full end-to-end verification against production
infrastructure. See `README.md`'s "Live database validation" section,
`DATABASE_SCHEMA.md`'s "Open questions," and `DATA_PIPELINE.md` for the
full corrected narrative.

### Fixed

- **ML inference was not scoped to the WC-only corpus (severe train/serve
  skew).** `app/ml/data/loader.py::load_matches_dataframe()` — the query
  every live prediction and tournament simulation depends on — was missing
  a `data_source IS NOT NULL` filter. The live `matches` table holds 49,389
  rows total; only 419 (330 `wc_2002_2022_dataset` + 89 `wc_2026_live`) are
  the WC-only corpus the shipped model was actually trained on. Without the
  filter, every live prediction would have been served against the full,
  ~49k-row superseded legacy dataset instead. Fixed by adding
  `AND m.data_source IS NOT NULL` to the query. Undetectable in any prior
  session since there was no live DB to run this query against.
- **SQLAlchemy `Uuid`/`String` type mismatch broke joins.** `app/models/
  match.py` declared `id`/foreign-key columns (`teams.id`, `matches.id`,
  `matches.home_team_id`/`away_team_id`, `team_statistics.id`/`match_id`/
  `team_id`, `saved_predictions.id`/`user_id`) as `Column(String, ...)`,
  but the live schema stores all of these as native Postgres `uuid`. This
  raised `operator does not exist: uuid = character varying` on joins once
  actually run against the real database. Fixed by introducing a shared
  `Uuid(as_uuid=False)` type (`_UUID` in `match.py`) across every affected
  column — `as_uuid=False` keeps every existing caller's plain-`str` usage
  (schemas, services, `default=lambda: str(uuid.uuid4())`) working
  unchanged.
- **UUID-format validation guards added to team/match lookups.** Passing a
  malformed (non-UUID) `team_id`/`match_id`/`home_team_id`/`away_team_id`
  to `app/services/team_service.py` (`get_team_by_id`, `get_team_stats`,
  `get_head_to_head`, `get_performance_trend`) or `app/services/
  match_service.py` (`get_match_by_id`) previously reached asyncpg directly
  and raised a raw `DataError`, surfacing as an unhandled 500 — a direct
  consequence of the `Uuid` column fix above (a `String` column tolerated
  any string; a native `uuid` column does not). Both services now validate
  the input format first and return "not found" (404 / empty result) for
  malformed input instead of a 500.
- **`get_top_teams` threshold made every result disappear.** `app/services/
  team_service.py::get_top_teams()` filtered out any team with fewer than
  10 matches played — a threshold calibrated for the old, superseded broad
  "all competitions" dataset. Once correctly scoped to the WC-only corpus
  (see the `loader.py` fix above), a team that has only ever played in one
  World Cup has 3-7 matches total, so the old threshold of 10 was
  unreachable for every team, making `GET /teams/top` always return an
  empty list. Lowered to 2.
- **`from_date`/`to_date` type mismatch on `GET /matches`.**
  `match_service.get_matches()` typed its `from_date`/`to_date` parameters
  as `Optional[str]` and compared them directly against a `Date` column;
  against the live database this either silently failed to filter as
  expected or raised on comparison, depending on the input. Retyped to
  `Optional[date]`.

### Data

- **Live historical-match backfill verified: 330 historical rows (was 13 in
  an earlier, much smaller pre-WC2026 seed) + 89 real 2026 rows = 419 total
  WC-only matches**, confirmed present in the live `matches` table with
  `data_source` set. Spot-checked two real results against known football
  history: **Brazil 2-0 Germany**, 2002 final, and **Brazil 1-7 Germany**,
  2014 semi-final — both present with the correct scoreline, date, and
  stage.
- **Team-name canonicalization confirmed live**: `Türkiye`, `Cabo Verde`,
  and `USA` all exist as the canonical rows in the live `teams` table,
  matching `teams_reference.csv`'s naming convention (not "Turkey" /
  "Cape Verde" / "United States").

### Backend / API — end-to-end live validation

- **The backend was booted directly against the live Supabase database**
  (not the processed CSVs) for the first time and verified working
  end-to-end: `/health`, the Swagger/OpenAPI docs at `/docs`, live
  `POST /predictions/predict` calls across 6 realistic matchups, and
  `POST /tournament/simulate` Monte Carlo runs at 100, 1000, and 5000
  iterations — all completed successfully.

### Code cleanup

- Removed unused imports and dead code surfaced while working through the
  above fixes: an unused `asyncio` import in `app/ml/data/loader.py`; unused
  `and_`/`pandas` imports and an unused `Match` import in
  `app/services/match_service.py` and `app/services/team_service.py`
  respectively; replaced the undeclared transitive `python-jose` dependency
  in `backend/requirements.txt` with a direct `PyJWT` pin (the actual
  library `app/core/security.py` imports).

### Open item (not fixed — flagged for a decision)

- **Public API endpoints are not WC-only scoped, unlike the ML pipeline.**
  `GET /api/v1/matches` and `/analytics/dashboard`'s
  `total_matches_analyzed` still query/count the full, unfiltered
  `matches` table (~49,389 rows, all competitions, 1872-2026) rather than
  the 419-row WC-only corpus the ML pipeline is now correctly scoped to.
  This is a genuine open product decision — WC-only-scope the public API to
  match the ML pipeline, or treat full-history browsing as an intentional,
  broader feature — not something resolved in this pass. See
  `KNOWN_ASSUMPTIONS.md` item (h) for the full writeup.

## 2026-07-04 — WC2026 data/model/schema upgrade

A multi-wave upgrade covering data engineering, database schema, feature
engineering, tournament-engine accuracy against the in-progress real
tournament, ML retraining, and backend/API additions. **At the time this
entry was written, nothing in it had been applied to the live Supabase
database** — the DB was unreachable from the sandbox this work was done in.
**That has since changed the same day: see the "Live database validation
pass" entry above** for the migration/seed actually being applied and
verified, and the real bugs (undetectable until the DB was reachable) found
and fixed as a result. Full technical detail lives in `DATA_PIPELINE.md`,
`DATABASE_SCHEMA.md`, `FEATURE_ENGINEERING.md`, `RANKINGS_INTEGRATION.md`,
`ELO_SYSTEM.md`, `TOURNAMENT_ENGINE.md`, and `MODEL_EVALUATION.md`.

### Data

- **New WC-only training corpus.** Seven raw source files (2002-2022 WC
  matches, 2026 live matches/stats/roster, tournament-stage lookup, fixture
  template) normalized and merged into
  `backend/app/data/processed/{matches_historical.csv, teams_reference.csv,
  match_team_stats.csv}` — 419 matches, 48 2026 teams, 132 team-stats rows.
  Mojibake encoding fixes (`Türkiye`, `Curaçao`, `Côte d'Ivoire`) and a
  79-entry team-name canonicalization table applied across all sources. See
  `backend/app/data/processed/DATA_QUALITY_REPORT.md` and `DATA_PIPELINE.md`.
  Documented, non-fabricated gaps: ~9 missing matches per 2002-2022
  tournament, 10 completed 2026 matches with no team-stats rows, `NULL`
  venue/city for all 2026 matches.

### Database

- **New tables/columns**: `team_statistics` (per-match box-score stats),
  `tournament_stages` (stage lookup), `teams.elo_rating`/`fifa_code`/
  `wc2026_group`/`ranking_updated_at`, `matches.stage_id`/`tournament_year`/
  `home_xg`/`away_xg`/`external_match_id`/`data_source`, and
  `matches.away_team_id` relaxed to nullable (for the one genuinely
  undetermined Round-of-16 opponent). New migration
  `database/migrations/002_wc2026_upgrade.sql`; seed data generated by
  `database/generate_seed_wc2026.py` into `database/seed_wc2026.sql` (419
  matches, 132 team_statistics rows, 48 teams with elo_rating/wc2026_group
  populated). At the time of this entry, not yet run against the live
  Supabase instance (unreachable from the build sandbox). **Applied and
  verified later the same day** — see the "Live database validation pass"
  entry above and `DATABASE_SCHEMA.md`'s "Open questions."

### ML / features

- **Elo-at-inference bug fixed.** `elo_difference` — the model's #3 most
  important feature by trained gain — silently evaluated to a constant
  `0.0` on every live prediction and tournament simulation, because
  `app/ml/data/loader.py::load_matches_dataframe()` never called
  `compute_dynamic_elo()` before caching, even though training always did.
  Fixed by computing Elo once per 6-hour cache refresh in `loader.py`. See
  `ELO_SYSTEM.md`.
- **FIFA rankings integrated as a complement to Elo, not a replacement**:
  new `home_fifa_rank`/`away_fifa_rank`/`fifa_rank_diff`/`same_confederation`
  features sourced from `teams_reference.csv`, kept as separate columns from
  Elo deliberately (different update dynamics, no empirical basis yet to
  blend them). See `RANKINGS_INTEGRATION.md`.
- **New knockout-experience features** (`home_knockout_experience`,
  `away_knockout_experience`, `knockout_experience_diff`), from a
  previously-unselected `matches.stage` column. Feature count: 156 → 163
  columns. See `FEATURE_ENGINEERING.md`.
- **Model retrained on the new WC-only corpus** (376 training rows after
  CV, replacing the old broad "all competitions 1872-2017" dataset).
  Old bundle preserved for rollback (`xgboost_model.pkl.bak`,
  `scaler.pkl.bak`). Walk-forward CV by tournament edition: mean accuracy
  0.436 ± 0.037 across 6 folds.
- **Empirical feature pruning completed** (follow-up pass, same day): SHAP,
  permutation importance, correlation, mutual information, and variance
  analysis run against the actual trained 163-feature model. 29 features
  removed (163 → 134) — 21 exact algebraic duplicates (e.g.
  `attack_momentum_w` ≡ `avg_goals_scored_w`), 2 true zero-variance
  constants (`neutral_venue`, `tournament_weight` — always constant in a
  WC-only corpus), and 6 near-zero-variance/zero-importance features. Net
  effect on CV mean accuracy/MAE: flat (noise-level); fold-to-fold accuracy
  std improved (0.037 → 0.029). Pre-pruning model preserved for rollback
  (`xgboost_model.pkl.prepruning.bak`, distinct from the older
  `xgboost_model.pkl.bak`). Full evidence per feature in
  `FEATURE_ENGINEERING.md` §5 and `MODEL_EVALUATION.md`.
- `train.py::load_data()` now reads `matches_historical.csv` directly by
  default (DB unreachable from the build sandbox at the time this was
  written); a DB-backed `load_data_from_db()` path is kept for
  parity/reconciliation now that Postgres is reachable (see the "Live
  database validation pass" entry above). See `DATA_PIPELINE.md` §2.

### Tournament engine

- **Simulator now uses real, in-progress 2026 results** instead of blindly
  re-simulating already-played matches: completed matches are read from
  `matches_historical.csv` and substituted directly; only genuinely
  unplayed fixtures are still Monte Carlo simulated. Fixed a knockout-draw
  edge case (a level regulation score in a real knockout match no longer
  crashes or fabricates a winner — extra time/penalties are still
  genuinely simulated from the real scoreline). Fixed a Round-of-32
  bracket-pairing bug where the heuristic Pot1/Pot2 pairing didn't reliably
  reproduce FIFA's actual seeded bracket even when qualified teams matched
  reality (real bracket now sourced from `schedule.json` when possible).
- **Team-strength-aware fallback**: the last-resort prediction fallback
  (used only when the batched model call itself errors) now uses
  `teams_reference.csv`'s Elo ratings instead of a flat neutral guess —
  most relevant for first-time-qualified nations with thin history
  (Curaçao, Jordan, Iraq, Uzbekistan, Cabo Verde, Congo DR, Haiti).
  See `TOURNAMENT_ENGINE.md`.

### Backend / API

- **New endpoint**: `GET /api/v1/matches/{match_id}` — match detail
  including per-team box-score stats from `team_statistics` when available.
  Registered last among the router's GET routes so it doesn't shadow
  `/tournaments`, `/tournaments/{tournament}/stats`, or `/analytics/*`.

### Performance

- Vectorized rolling-stats computation (`build_team_index` via
  `groupby().indices`, per-team stats memoization in
  `build_feature_vector`) — carried forward from the 2026-07-02 audit,
  still the basis for this pass's feature additions.

### Test coverage

- Backend test suite grew from 52 to **80 collected tests** (new files
  `test_train_pipeline_smoke.py`, `test_wc2026_api.py`; expanded
  `test_tournament.py`), with regression coverage for the real-2026-results
  tournament substitution, the knockout-draw edge case, the real
  Round-of-32 bracket override, the new `GET /matches/{match_id}` endpoint,
  and the CSV-based training data path.

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
