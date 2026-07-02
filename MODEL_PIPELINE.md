# Model Pipeline

Covers the offline training pipeline (`backend/app/ml/train.py`), feature
engineering, calibration, hyperparameter search, explainability, and how the
trained bundle is loaded and versioned at inference time. Grounded in the
current source, not the design intent — see the "Known limitation" section
for a gap found by reading the actual request-time code path.

## Models trained

Three XGBoost models, trained together in `train_models()`:

1. **`home_model`** — `XGBRegressor`, objective `count:poisson`, predicts
   home expected goals.
2. **`away_model`** — `XGBRegressor`, objective `count:poisson`, predicts
   away expected goals.
3. **`result_model`** — `XGBClassifier`, objective `multi:softprob`,
   3-class: `0 = Away Win`, `1 = Draw`, `2 = Home Win`.

All three share the same feature matrix and the same `StandardScaler`
(fit on the training split only).

## Data loading

`train.py::load_data()` pulls **completed** matches directly from Postgres
via a fresh async SQLAlchemy engine (independent of the app's request-time
engine), joining `matches` to `teams` twice for home/away names:

```sql
SELECT m.date, ht.name AS home_team, at.name AS away_team,
       m.home_score, m.away_score, m.tournament, m.neutral_venue
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
JOIN teams at ON m.away_team_id = at.id
WHERE m.status = 'completed'
  AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
ORDER BY m.date ASC
```

Rows with null scores are dropped and the frame is sorted ascending by date
— this ordering matters for every downstream step (Elo, rolling windows,
chronological split).

## Feature engineering

`app/ml/features/feature_engineering.py`, invoked once per training row via
`build_feature_vector()` (and once per prediction at inference time — same
function, same code path):

- **Elo ratings** (`compute_dynamic_elo`) — pre-computed once over the full
  sorted history before feature engineering starts; tournament-weighted
  K-factor (`TOURNAMENT_WEIGHTS`, World Cup = 1.0 down to Friendly = 0.35).
  Adds `home_elo`, `away_elo`, `elo_difference` columns to the DataFrame.
- **Rolling form** at 5/10/20-match windows (`ROLLING_WINDOWS`) — weighted
  points, avg goals scored/conceded, attack/defense strength (Dixon-Coles
  style), momentum, clean-sheet rate, goal volatility, win/unbeaten streaks,
  average opponent Elo, tournament experience, upset score, high-scoring
  rate. Weight = tournament importance × recency-within-window × exponential
  time decay (3-year half-life).
- **Rest days** — days since each team's last match before the reference
  date.
- **Head-to-head** — win rate and average combined goals over the last 10
  meetings between the two specific teams, before the reference date.
- **Derived/interaction features** — goal-diff differential, attack/defense
  differential, momentum differential, Elo closeness (`1/(1+|elo_diff|)`),
  "both defensive" / "both low-scoring" products, form convergence, expected
  total goals — one set per rolling window, explicitly engineered to help
  the draw class (historically the hardest to predict).
- **Leakage safety**: every per-team/per-pair computation filters to matches
  strictly before the reference date (`as_of_date`), and rows with missing
  scores are dropped *before* windowing/aggregation (fixed during this audit
  — see `CHANGELOG.md`) so unplayed/incomplete matches can't dilute or NaN
  the rolling stats.
- **Performance**: `build_team_index()` vectorizes team→row lookups via
  `groupby().indices` instead of `iterrows()` (~50-100x faster on ~45k rows);
  `build_feature_vector()` accepts an optional `team_stats_cache` dict to
  memoize each team's own stats across a batch of calls sharing the same
  reference date (used by the tournament matchup precompute step).

## Chronological split

**No random shuffling.** `chronological_split()`: 70% train / 15% validation
/ 15% test, in date order — the model is always validated/tested on strictly
later matches than it trained on, matching how it will actually be used.

## Training

- Hyperparameters: hand-tuned defaults in `train.py` (`_REGRESSOR_PARAMS`,
  `_CLASSIFIER_PARAMS`), overridden by `best_params.json` if present (see
  Hyperparameter search below).
- Regressors and classifier both use early stopping (100 rounds) against the
  validation split.
- Class imbalance handled via `compute_sample_weights` (`draw_optimizer.py`)
  plus an optional Optuna-tuned `draw_weight_mult` that further upweights
  draw-class samples.
- **Draw threshold optimization** (`optimize_draw_threshold`, also in
  `draw_optimizer.py`): after training, a `draw_boost` multiplier is fit on
  the validation set's predicted probabilities to counter the classifier's
  natural under-prediction of draws, and stored in `draw_config`.

## Probability calibration

`app/ml/calibration.py`, run at the end of `train_models()`:

- Fits **both** isotonic regression (`sklearn.isotonic.IsotonicRegression`,
  one per class) and Platt-style scaling (per-class logistic regression on
  raw probabilities) on the validation split's raw classifier output.
- Scores both by mean Brier score (tiebreak: Expected Calibration Error,
  15 bins) and picks the better one (`min` over `(mean_brier, ece)`).
- The winning method + fitted calibrators are stored in `calibration_bundle`
  inside the model bundle; `apply_calibration()` is called at inference
  time (`predictor.py`) whenever `calibration_bundle` is non-empty.
- Can be run standalone for a calibration-only benchmark: `python -m
  app.ml.calibration`.

## Hyperparameter search (Optuna)

`app/ml/hyperparameter_search.py` — `python -m app.ml.hyperparameter_search
[--trials N]` (default 100, minimum enforced 10).

- Jointly tunes regressor params, classifier params, and `draw_weight_mult`
  in a single Optuna study (`TPESampler`, seed 42; `MedianPruner`).
- Search space: learning rate, max depth, gamma, reg_alpha/lambda,
  subsample, colsample_bytree, n_estimators, min_child_weight for both
  regressor and classifier types; `draw_weight_mult` in [1.0, 5.0].
- Composite objective (maximize): `0.55*accuracy + 0.10*draw_recall +
  0.10*draw_f1 + 0.15*home_mae_score + 0.10*away_mae_score - draw_penalty`
  (penalty applied if draw recall is suspiciously high while overall
  accuracy is low — guards against a degenerate "always predict draw"
  optimum).
- Best trial is re-validated on the held-out test set, and results
  (including `regressor_params`, `classifier_params`, `draw_weight_mult`,
  and `test_set_metrics`) are written to `best_params.json` next to the
  model bundle. `train.py` picks this up automatically on the next run if
  present.

## Explainability (SHAP)

`app/ml/explainability.py::PredictionExplainer`:

- Wraps `result_model` (the classifier) in a `shap.TreeExplainer` at load
  time — fast, exact SHAP values for tree ensembles.
- `explain()` returns the top 5 positive and top 5 negative feature
  attributions (by SHAP value) for the predicted class, with human-readable
  names (`_format_feature_name`, e.g. `home_momentum_20` → "Home Team's
  Momentum (Past 20 Matches)").
- Feature-name handling: both `elo_difference` (the real feature name
  produced by feature engineering) and the legacy alias `elo_diff` map to
  "Elo Rating Difference" — this alias was added during the audit to fix a
  mismatch that previously caused Elo's SHAP attribution to be silently
  dropped from explanations.
- Gracefully degrades to empty attribution lists if `shap` isn't installed
  or `TreeExplainer` initialization fails — never blocks a prediction.
- Not used in `predict_batch()` (tournament matchup precompute) — SHAP is
  the single most expensive per-call step and isn't consumed by that caller.

## Model bundle: contents, versioning, loading

`save_models()` writes two files via `joblib.dump(..., compress=3)`:

- **`MODEL_PATH`** (default `app/ml/models/xgboost_model.pkl`) — a dict:
  `home_model`, `away_model`, `result_model`, `feature_columns` (ordered
  list, critical for correct inference), `model_version`
  (`settings.MODEL_VERSION`, default `"2.0.0"`), `trained_at` (ISO-8601 UTC),
  `rolling_windows`, `draw_config`, `calibration_bundle`, `metadata`
  (model type names, feature count, result encoding).
- **`SCALER_PATH`** (default `app/ml/models/scaler.pkl`) — the fitted
  `StandardScaler`, saved separately.

Side-effect JSON reports, all in the same directory as `MODEL_PATH`:

- `feature_importance.json` — averaged feature importance across all three
  models, sorted descending. Served by `GET /analytics/feature-importance`.
- `metrics.json` — MAE/RMSE, raw and draw-adjusted classifier accuracy,
  draw recall/F1. Served by `GET /analytics/model-metrics`.
- `calibration_report.json` — Brier/ECE for isotonic, Platt, and raw, plus
  which method was selected.
- `training_report.json` — training metadata (sample count, feature count,
  objectives, `draw_config`, calibration method, `metrics`).
- `best_params.json` — only written by `hyperparameter_search.py`, consumed
  by `train.py` on the next run if present.

**Loading** (`MatchPredictor.load()`, called once at app startup via
`get_predictor()`):

- Missing model file → non-fatal; logs a warning, predictor falls back to
  a historical-average path (`_historical_fallback`) instead of crashing.
- Model file present but **scaler missing** → also falls back (does *not*
  attempt to predict with raw unscaled features against a model trained on
  standardized ones). This was a real silent-corruption bug fixed during
  the audit — previously a missing scaler with a present model file would
  feed unscaled features into the regressors/classifier and produce
  plausible-looking but meaningless predictions with no error. See
  `CHANGELOG.md`.
- Both present → both loaded, `SHAP` explainer initialized if `result_model`
  and `feature_columns` are both available, `is_loaded` becomes `True`.

## Known limitation — Elo not populated at inference time

**Status: confirmed present in current code, not yet fixed.**

`build_feature_vector()` computes `home_elo`/`away_elo` by calling
`_latest_elo_for_team()`, which reads the `home_elo`/`away_elo` **columns**
off the passed-in DataFrame (falling back to `BASE_ELO = 1500.0` if those
columns/rows aren't present). Those columns only exist if
`compute_dynamic_elo(df)` has been run on `df` first.

- **At training time** (`train.py::build_training_dataset`), `df =
  compute_dynamic_elo(df)` is called explicitly before feature engineering
  — Elo columns exist, real values are used, and `home_model`/`away_model`/
  `result_model` all learn genuine Elo-based signal.
- **At inference time** (`app/ml/data/loader.py::load_matches_dataframe`,
  the function every API request path uses via `get_predictor()` /
  `_get_simulator_dependencies()`), `compute_dynamic_elo()` is **never
  called**. The cached DataFrame has no `home_elo`/`away_elo` columns, so
  every live prediction's Elo lookup silently falls back to `BASE_ELO` for
  both teams, making `elo_difference` evaluate to `0.0` for every request
  regardless of the actual teams involved.

Practical effect: the model still uses ~150+ other features (rolling form,
head-to-head, rest days, etc.) so predictions aren't garbage, but a feature
the model was trained to weight meaningfully (Elo gap ranks highly in
`feature_importance.json` for most training runs) is a constant at serving
time. SHAP explanations will never show Elo as a driver of any live
prediction, even when the teams have a large real rating gap.

**Suggested fix direction:** run `compute_dynamic_elo()` once inside (or
immediately after) `load_matches_dataframe()`, before caching the result —
it's a single full-history pass already paid for by the 6-hour TTL, not a
per-request cost. Ensure the tournament simulator's `_df_cache` (module-level
in `tournament.py`) picks up the same enriched frame rather than re-fetching
a raw copy.

## Training pipeline usage

See `TRAINING_GUIDE.md` for step-by-step instructions on running `train.py`,
required environment/data, and how to validate a newly trained bundle before
deploying it.
