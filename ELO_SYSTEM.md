# Elo Rating System

Documents the dynamic Elo system used by the FIFA AI prediction pipeline: how
it's computed, the inference-time bug that made `elo_difference` a constant
`0.0` for every live prediction, the exact fix applied, and the verification
that proves it now works.

Related: `MODEL_PIPELINE.md` (existing architecture doc, already described
this bug pre-fix as a known limitation), `KNOWN_ASSUMPTIONS.md` item (d),
`FEATURE_ENGINEERING.md` (full feature list).

---

## 1. How Elo is computed

`backend/app/ml/features/feature_engineering.py::compute_dynamic_elo(df)`:

- Every team starts at `BASE_ELO = 1500.0`.
- Processes matches **in chronological order** (`df.sort_values("date")`).
- For each match, records the **pre-match** rating of both teams into
  `home_elo` / `away_elo` columns, then updates each team's rating using a
  standard logistic Elo update (`_elo_update`) scaled by a **tournament
  importance weight** (`get_match_weight` — World Cup = 1.00, friendlies =
  0.35, etc.) instead of a flat K-factor. This means a World Cup win moves a
  team's rating roughly 3x more than an equivalent friendly win.
- `elo_difference = home_elo - away_elo` is derived once both columns exist.
- Because ratings are carried forward match-by-match in a single pass, this
  must be run **once over the full ordered history** — it cannot be computed
  correctly "per request" for an arbitrary team without replaying that
  team's entire history, which is why it's treated as a pre-computation
  step rather than something `build_feature_vector()` derives on its own.

At the single-match level, `_latest_elo_for_team(df, team_index, team_name,
as_of_date)` (also in `feature_engineering.py`) looks up a team's Elo as of
the most recent match **strictly before** `as_of_date`, scanning backwards
through the team's pre-built index (`build_team_index`) rather than
re-filtering the whole DataFrame. This is what `build_feature_vector()`
calls to populate `home_elo` / `away_elo` for a specific matchup.

## 2. The bug: Elo never populated at inference time

**Symptom:** `elo_difference` — the model's #3 globally most important
feature by trained SHAP/gain importance (`feature_importance.json`, index 2,
importance 0.0295) — evaluated to exactly `0.0` on every live prediction
request, regardless of which two teams were being compared.

**Root cause:**

- `_latest_elo_for_team()` and the non-indexed Elo fallback path in
  `build_feature_vector()` both read `home_elo` / `away_elo` **columns**
  off the `df` they're given. If those columns don't exist, every lookup
  silently falls back to `BASE_ELO` (1500.0) for both teams, so
  `elo_difference = 1500.0 - 1500.0 = 0.0` unconditionally. There's no
  exception, no warning — a perfectly quiet failure mode.
- Those columns only exist if `compute_dynamic_elo(df)` has been run on
  `df` first.
- **Training** (`backend/app/ml/train.py::build_training_dataset`) does
  this correctly: `df = compute_dynamic_elo(df)` runs before any feature
  vectors are built (`train.py` line ~217), so the model is trained on
  real, varying Elo signal.
- **Inference** did not. Every live request path
  (`prediction_service.run_prediction` → `predictor.predict()`, and the
  tournament simulator's `_get_simulator_dependencies()`) obtained its `df`
  from `app/ml/data/loader.py::load_matches_dataframe()`, which loaded rows
  straight from the `matches` table and cached them **without ever calling
  `compute_dynamic_elo()`**. The cached DataFrame simply had no
  `home_elo`/`away_elo` columns.

This is a classic **train/serve skew** bug: the model learned to rely
heavily on a feature that was silently disabled in production.

## 3. The fix

**File changed:** `backend/app/ml/data/loader.py`.

```python
from app.ml.features.feature_engineering import compute_dynamic_elo
...
df = compute_dynamic_elo(df)   # added, immediately before caching

_cache = df
_cache_time = now
```

`compute_dynamic_elo(df)` is now called once inside
`load_matches_dataframe()`, right after the raw DB rows are assembled into a
DataFrame and right before the result is stored in the module-level cache
(`_cache`). Rationale for this exact location:

1. **Same function as training** — no second Elo implementation to drift
   out of sync. `elo_difference` is produced by the identical code path at
   train time and serve time, by construction.
2. **Amortized cost, not a per-request cost** — `load_matches_dataframe()`
   already has a 6-hour cache TTL (`CACHE_TTL_HOURS = 6`). Adding
   `compute_dynamic_elo()` here means the full-history Elo pass runs once
   per cache refresh (a few hundred/thousand rows, sub-second), not once
   per prediction request. This satisfies the "not recomputed from scratch
   per-request" requirement without needing a separate persisted
   lookup table — the *DataFrame itself* now carries the enriched columns
   for its whole 6-hour lifetime, and per-request lookups
   (`_latest_elo_for_team`) already use the pre-built `team_index` for an
   O(matches-per-team) backward scan rather than an O(full-history) scan.
3. **Both consumers fixed at once** — both `prediction_service.py`
   (single-match predictions) and `tournament.py`'s
   `_get_simulator_dependencies()` (tournament simulation) call
   `load_matches_dataframe()` and cache/reuse the *same* returned object, so
   fixing it in one place fixes both.

**Also changed (for a new feature, see `FEATURE_ENGINEERING.md`):**
`backend/app/ml/data/loader.py` and `backend/app/ml/train.py`'s `load_data()`
now additionally `SELECT m.stage` — required for the new knockout-experience
feature, unrelated to the Elo fix itself but touched in the same pass.

## 4. Persisted "latest Elo per team" — design note for the DB wave

The task called for a persisted latest-Elo-per-team lookup (a column, cache,
or small JSON/CSV) so Elo doesn't need recomputing from scratch per request.
In this codebase, the 6-hour-TTL in-memory DataFrame cache **already serves
this role** for the two consumers currently calling
`load_matches_dataframe()` (single prediction + tournament simulator) — the
enriched `home_elo`/`away_elo` columns exist for that DataFrame's whole
lifetime, and a fresh `_latest_elo_for_team()` lookup is O(team's own match
count), not O(full history).

That said, this is process-local memory: it doesn't survive a restart, isn't
shared across multiple app instances/workers, and isn't queryable by SQL for
other consumers (analytics, admin tooling, etc.). The Data Engineering /
Database wave has already added a `teams.elo_rating SMALLINT` column
(`database/migrations/002_wc2026_upgrade.sql`), currently seeded once from
`teams_reference.csv`'s pre-tournament snapshot. **Recommendation for the DB
wave:** after each `compute_dynamic_elo()` pass (e.g. on a schedule, or after
new match results are ingested), write each team's *latest* computed rating
back to `teams.elo_rating` (the trigger `teams_ranking_updated_at` already
bumps `ranking_updated_at` automatically on that column). That turns the
per-process cache into a durable, cross-instance, SQL-queryable source of
truth, while the in-memory Elo columns on the cached match DataFrame
continue to serve the per-request feature-engineering lookups. This document
does not implement that write-back (database schema/write paths are outside
this agent's scope — see repo-wide agent boundaries), but flags it
explicitly so it isn't lost.

## 5. Leakage safety

- `compute_dynamic_elo()` only ever uses a match's own result to update
  ratings *after* recording that match's *pre-match* ratings into
  `home_elo`/`away_elo` for that row — so a match's own outcome is never
  folded into the Elo value used as its own input feature.
- `_latest_elo_for_team(df, team_index, team_name, as_of_date)` explicitly
  filters for `row_date < as_of_date` (strictly before), never `<=`, so a
  team's Elo lookup for match *N* can never see match *N*'s own result.
- This also means **later** 2026-tournament matches correctly benefit from
  **earlier** 2026 matches' Elo updates once results are ingested (e.g. a
  round-of-16 prediction reflects group-stage Elo movement) — this is
  legitimate information available in real time, not leakage, since it
  only ever looks backward in the chronological order matches were played.

## 6. Verification (SHAP)

Ran the actual trained model bundle (`xgboost_model.pkl`,
`feature_columns` includes `elo_difference`) through the real
`MatchPredictor.predict()` code path, using `matches_historical.csv` as the
match history (with `compute_dynamic_elo()` applied exactly as the fixed
`loader.py` now does), for 5 different matchups at the same `match_date`:

| Matchup | `elo_difference` |
|---|---|
| Brazil vs Germany | -13.62 |
| Argentina vs France | -24.49 |
| Spain vs Japan | +59.35 |
| Mexico vs South Korea | +46.21 |
| England vs Croatia | +3.77 |

- **Before the fix** (simulated by feeding a DataFrame without Elo columns,
  i.e. the exact old `loader.py` behaviour): all 5 matchups produced
  `elo_difference = 0.0000`, confirming the bug.
- **After the fix**: values range from -24.49 to +59.35 — clearly varying
  per matchup, not a constant, and consistent with which team is actually
  rated higher (e.g. Spain, ranked/rated well above Japan, gets the largest
  positive gap).
- Pulled the full per-feature SHAP vector (via `shap.TreeExplainer` on
  `predictor.result_model`, same explainer class used in production by
  `PredictionExplainer`) for the Home-Win class on the Brazil vs Germany
  matchup: `elo_difference` ranks **23rd of 141** features by `|SHAP|`
  for that specific match (impact +0.0249) — a real, non-zero, non-trivial
  contribution. For the Mexico vs South Korea matchup (the largest Elo gap
  among rated teams for that pairing), `elo_difference` appears directly in
  the model's **top-5** SHAP drivers with impact +0.141.
- Cross-checked against the model's **global** feature importance
  (`backend/app/ml/models/feature_importance.json`): `elo_difference` is the
  **#3 most important feature overall** (importance 0.0295, behind only two
  other features), confirming the task's characterization of it as a
  top-3 SHAP feature and underscoring how costly the pre-fix bug was — the
  model's third-most-trusted signal was silently zeroed out on every real
  request.

Per-match SHAP rank varies (as expected — SHAP attributions are
match-specific, and when both teams happen to be closely rated the raw Elo
gap contributes less to that particular prediction than form/momentum
features do), but it is never constant/zero anymore, and its *global*
importance is unchanged from what training learned.
