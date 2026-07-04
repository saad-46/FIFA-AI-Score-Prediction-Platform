# Known Assumptions & Limitations

Documented gaps, deliberate omissions, and known technical debt in the
current codebase, as of the 2026-07-02 production audit. Nothing in this
file is invented — each item is grounded in the actual source/data files
cited.

## a. FIFA 2026 schedule data provenance

**Source:** the official FIFA World Cup 2026 Match Schedule wallchart PDF,
provided directly by the user (a single-page infographic, all kickoff times
printed as Eastern Time). Extracted **2026-07-02**.

- 104/104 matches extracted and verified against the source; stage-count
  breakdown confirmed correct (72 group stage + 16 R32 + 8 R16 + 4 QF + 2 SF
  + 1 third-place + 1 final = 104).
- Zero uncertain reads — every fixture in `schedule.json` has
  `"uncertain": false`, meaning every field (date, kickoff time, venue city,
  stage, teams/placeholders) was read directly off the chart, not inferred.
- One documented exception to "read directly": the Bronze Final (match 103)
  and Final (match 104) print literal "BRONZE FINAL" / "FINAL" text on the
  chart rather than `W##`/`L##` codes; the specific `L101`/`L102` and
  `W101`/`W102` participant codes used in `schedule.json` for those two
  matches are inferred from tournament structure (semi-final losers play the
  bronze final; semi-final winners play the final), not read as literal text
  off the chart. This is the one documented inference in an otherwise
  zero-uncertain-read dataset.
- Full provenance notes live in `backend/app/data/fifa_2026/README.md` —
  treat that file as the authoritative source for any question about what
  was read verbatim vs. inferred.
- Match 6 (Vancouver, AUS v TUR, 2026-06-13) is genuinely listed as a 00:00
  ET kickoff on the source chart — this looks like a data-entry error at
  first glance but is documented as-printed, not a bug in the extraction.

## b. No stadium names

The wallchart labels every match by **host city only** (e.g. "New York New
Jersey"), never by a specific stadium (e.g. MetLife Stadium). Stadium names
are **intentionally not included anywhere** in `venues.json`,
`schedule.json`, or the `teams` table seed data — the source PDF simply
doesn't contain that information, and no stadium name has been guessed or
backfilled from general knowledge. If stadium-level detail is ever needed,
it must come from a separate, explicitly-sourced dataset, not by inference
from city name.

## c. NULL confederation / FIFA ranking / founding year / stadium for seeded 2026 teams

**Partially superseded 2026-07-03/04 — see update below.** Originally:
`database/seed_fifa_2026_teams.sql` inserts all 48 official 2026 teams with
**only `name` and `country` populated**. The `teams` table also has
`confederation`, `fifa_ranking`, `logo_url`, `founded_year`, and
`home_stadium` columns (see `database/schema.sql`), but none of that data
was present in the source wallchart, so all five columns are left `NULL` for
every 2026-seed team rather than filled with plausible-looking guesses. The
seed script's own header comment states this explicitly.

**Update:** the Database Engineering wave's `database/seed_wc2026.sql` (see
`DATABASE_SCHEMA.md`, generated from `teams_reference.csv` by
`database/generate_seed_wc2026.py`) now supersedes
`seed_fifa_2026_teams.sql` for this purpose and **does** populate
`confederation`, `fifa_ranking`, `elo_rating` (new column), `fifa_code` (new
column), and `wc2026_group` (new column) for all 48 2026 teams via an
`ON CONFLICT (name) DO UPDATE` upsert. `logo_url`, `founded_year`, and
`home_stadium` remain `NULL` for every team (2026 or historical) — none of
that data exists in any source file used by either seed script.
`seed_fifa_2026_teams.sql` itself is unchanged and still only populates
name/country if run standalone; run order matters (see `DATABASE_SCHEMA.md`).
**Not yet applied to the live Supabase database** — see `DATA_PIPELINE.md`
§5 and `DATABASE_SCHEMA.md`'s "Open questions."

## d. Elo not populated at inference time — FIXED 2026-07-03/04

**Status: fixed, kept here as historical record.** `app/ml/features/
feature_engineering.py::compute_dynamic_elo()` — which populates the
`home_elo`/`away_elo` columns that `build_feature_vector()`'s Elo lookup
depends on — was called during offline training
(`train.py::build_training_dataset`) but was **never called** in the
request-time data path (`app/ml/data/loader.py::load_matches_dataframe`,
used by every live prediction and by the tournament simulator). Without
those columns present, every live Elo lookup fell back to the constant
`BASE_ELO = 1500.0` for both teams, so `elo_difference` evaluated to `0.0`
on every served prediction regardless of the real rating gap between the
two teams — even though the model was trained on genuine Elo signal and
weighted it meaningfully.

**Fix:** `load_matches_dataframe()` now calls `compute_dynamic_elo()` once
per 6-hour cache refresh, immediately before caching the result — a single
full-history pass, not a per-request cost. Verified via SHAP that
`elo_difference` now varies meaningfully per matchup instead of being a
constant `0.0`. Full detail, including before/after verification: see
`ELO_SYSTEM.md` and `MODEL_PIPELINE.md`.

## e. Synthetic goal-distribution endpoint

`GET /api/v1/matches/analytics/goal-distribution` returns goal counts
**by minute**, but the database schema has no goal-minute-level event data
— `matches` stores only final scores (`home_score`/`away_score`), not
individual goal events with timestamps. Rather than silently fabricating
realistic-looking minute-by-minute numbers, the response schema
(`GoalDistributionPoint` in `app/schemas/match.py`) carries an explicit
`is_synthetic: bool = True` field, currently always `true`. Any consumer of
this endpoint (frontend or otherwise) should surface that flag rather than
presenting the distribution as real historical data. This becomes real the
day per-goal-minute events are captured in the schema and
`match_service.get_goal_distribution()` is rewritten to query them.

## f. `ON DELETE CASCADE` from teams to matches

`database/schema.sql` declares both `matches.home_team_id` and
`matches.away_team_id` as `REFERENCES teams(id) ON DELETE CASCADE` (mirrored
in the SQLAlchemy `Match` model in `app/models/match.py`). This means
deleting a row from `teams` would silently cascade-delete **every match**
that team ever played, including historical results with no relationship to
whatever prompted the team deletion.

- **No team-delete endpoint exists today** in `app/api/v1/endpoints/`, so
  this is latent risk, not an active bug — there is currently no code path
  in this application that can trigger it.
  Flagged by the Database Engineer as a footgun for **if** such an endpoint
  is ever added; recommendation was `ON DELETE RESTRICT` instead (forcing an
  explicit decision about what happens to historical matches before a team
  can be removed), left as a product decision rather than changed
  unilaterally in this audit.
- If a team-management/admin feature is ever built, revisit this constraint
  before shipping a delete path.

## g. Other assumptions found while reading the code

- **`predict_batch()` skips SHAP and confidence scoring by design** —
  `MatchPredictor.predict_batch()` (used by the tournament simulator's
  matchup precompute) intentionally omits `prediction_explanation` and
  `confidence_score`, since those are the two most expensive per-call steps
  in `predict()` and aren't consumed by the tournament simulator. Any new
  caller of `predict_batch()` that *does* need those fields will get neither
  — this is a deliberate scope limit of the batch API, not an oversight, but
  it's easy to miss if reusing `predict_batch()` for a new purpose.
- **In-process caches don't survive process restarts or scale across
  workers.** The `async_ttl_cache` (`app/core/cache.py`), the 6-hour match
  DataFrame cache (`app/ml/data/loader.py`), the prediction result cache
  (`prediction_service.py`'s `_PredictionCache`, 1-hour TTL / 500 entries),
  and the tournament simulator's module-level predictor/DataFrame cache
  (`tournament.py`'s `_predictor_cache`/`_df_cache`) are all per-process,
  in-memory state. Render runs this service with `--workers 2`, so each
  worker has its own independent copy of every cache — a prediction saved
  via `POST /predictions/{id}/save` will 404 with "Prediction not found or
  expired" if the save request happens to land on a different worker
  process than the one that generated it. There's no shared cache/session
  affinity in front of this today.
- **Connection pool sizing is tuned for exactly 2 Render workers.**
  `app/db/database.py` sets `pool_size=5, max_overflow=5` with a comment
  explaining the math: `(5+5) * 2 workers = 20` concurrent connections,
  chosen to fit under Supabase's default connection caps. If the worker
  count in `render.yaml`/deployment config ever changes, this pool sizing
  should be revisited — it is not derived dynamically from worker count.
- **`GET /analytics/model-metrics` and `/analytics/feature-importance`
  degrade quietly, not identically.** If training has never been run,
  `model-metrics` returns zeros / `"unknown"` (200 OK, looks like a
  real-but-empty result), while `feature-importance` returns an explicit
  **404** with an actionable message. A frontend consuming both should not
  assume the same "not trained yet" signal shape from each.
- **`saved_predictions.user_id` has no SQLAlchemy `ForeignKey`/relationship**
  even though the DB-level foreign key to `auth.users(id)` exists (declared
  in `database/schema.sql`). This is deliberate — `auth.users` lives in
  Supabase's own `auth` schema, managed by Supabase Auth, and isn't modeled
  as an ORM entity in this codebase — but it means SQLAlchemy-level
  cascade/relationship behavior for that FK isn't visible to the ORM, only
  to the database.
