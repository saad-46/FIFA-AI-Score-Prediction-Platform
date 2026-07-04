# Training Guide

How to run the training pipeline, what it needs, what it produces, and how
to validate a newly trained model bundle before deploying it. See
`MODEL_PIPELINE.md` for a deeper explanation of what each step does and why.

## Prerequisites

- Python 3.12+, backend dependencies installed (`pip install -r
  backend/requirements.txt`).
- **As of the 2026-07-03/04 WC2026 retrain, `train.py::load_data()` reads
  training data directly from
  `backend/app/data/processed/matches_historical.csv`** — no reachable
  Postgres database is required to run training today. This was a
  deliberate change made at a time when the live Supabase DB was
  unreachable from the dev sandbox; see `DATA_PIPELINE.md` §2 and
  `MODEL_PIPELINE.md`. **Update, later on 2026-07-04:** the live database
  became reachable this same day and has since been verified (seeded,
  booted against, and used to serve live predictions — see
  `DATA_PIPELINE.md`'s top-of-file update note). `train.py::load_data()`
  still defaults to the CSV path — that default has not been changed — but
  `load_data_from_db()` is now a genuinely usable, verified alternative,
  not just a placeholder for a hypothetical future environment; swap it in
  manually if you want the live DB as the training source instead of the
  CSV.
- Optuna installed if you intend to run hyperparameter search
  (`pip install optuna`) — `hyperparameter_search.py` raises `ImportError`
  with an install hint if it's missing; it is not a hard dependency of
  `train.py` itself.

## Data requirements

- Training uses **only** matches with `status == "Completed"` and both
  scores present — scheduled/unplayed matches are excluded at load time
  (13 such rows in the current `matches_historical.csv`), not just filtered
  later. The DB-backed `load_data_from_db()` path enforces the equivalent
  filter at the SQL level (`WHERE m.status = 'completed' AND ... IS NOT
  NULL`).
- `build_training_dataset()` skips the first `MIN_HISTORY` rows of the
  (date-sorted) history because rolling-window features need prior matches
  to compute anything meaningful — the very first matches in the dataset
  have no history to draw on. **`MIN_HISTORY` is now `30`** (reduced from
  the old broad-dataset default of 100) specifically because the WC-only
  corpus (`matches_historical.csv`, 419 rows, starting at 2002 with no prior
  history at all) is small enough that skipping 100 rows would silently
  discard almost two entire World Cups (36% of the historical data) before
  a single feature row is built.
- No explicit minimum total row count is enforced. With the current
  WC-only corpus (406 completed matches) this is a genuinely small dataset
  for a 134-feature XGBoost model (163 before the empirical feature-pruning
  pass — see `FEATURE_ENGINEERING.md` §5) — see `MODEL_EVALUATION.md`'s stated
  caveat about wide standard errors on every reported metric. Training
  also supports `expanding_window_splits()` (walk-forward CV by tournament
  edition) alongside the single `chronological_split()`, specifically
  because a single held-out slice of this size is too noisy to trust as
  the sole evidence of generalization — see `MODEL_EVALUATION.md`'s
  cross-validation table.

## Running training

From `backend/`:

```bash
python -m app.ml.train
```

This runs, in order:

1. **Load** — `load_data()` pulls completed matches from Postgres.
2. **Feature engineering** — `build_training_dataset()`: pre-computes Elo
   over the full sorted history, builds the team index, then engineers a
   feature row per match (skipping the first 100).
3. **Chronological split** — 70% train / 15% validation / 15% test, in date
   order, no shuffling.
4. **Train** — fits `home_model`, `away_model` (both `XGBRegressor`,
   `count:poisson` objective, early stopping on the validation set), then
   `result_model` (`XGBClassifier`, `multi:softprob`, class-weighted +
   optionally draw-boosted sample weights). Optimizes the draw probability
   threshold and fits probability calibrators (isotonic vs. Platt, best
   picked by Brier score) on the validation split.
5. **Evaluate** — logs regression MAE/RMSE, raw and draw-adjusted
   classifier accuracy, full classification reports, and averaged feature
   importance across all three models.
6. **Save** — writes the model bundle + scaler + JSON reports (see below).
7. **Demo** — runs one sample prediction between two well-known teams from
   the dataset and logs the full structured output, as a sanity check that
   the freshly trained bundle produces sane end-to-end results.

Expect this to take anywhere from a few minutes to significantly longer
depending on dataset size — `n_estimators: 1000` with early stopping for
both regressors and the classifier, each fit independently.

### Hyperparameter search (optional, before training)

```bash
python -m app.ml.hyperparameter_search --trials 100
```

Runs an Optuna study (default 100 trials, minimum enforced 10) over
regressor/classifier hyperparameters and the draw-class weight multiplier,
re-validates the best trial on the held-out test set, and writes
`app/ml/models/best_params.json`. If this file exists, the **next** run of
`python -m app.ml.train` automatically picks it up in place of the
hand-tuned defaults in `_REGRESSOR_PARAMS`/`_CLASSIFIER_PARAMS` — no code
change needed, just run training again afterward.

This is a separate, optional step — `train.py` runs fine without ever
having run hyperparameter search; it just uses the hand-tuned defaults.

### Draw diagnostic audit (optional, diagnostic only)

```bash
python -m app.ml.draw_optimizer
```

Not part of the main training path — a standalone diagnostic that benchmarks
four classifier variants (baseline, class-weighted, threshold-tuned,
combined) to explain *why* draw recall tends to be low and confirm which
combination of weighting + threshold tuning helps most. Writes
`app/ml/models/model_audit_report.json`. `train.py` imports
`compute_sample_weights` and `optimize_draw_threshold` from this module
directly (both are cheap, always-on), independent of whether you've run the
full diagnostic.

## Expected outputs

All written to the directory containing `MODEL_PATH` (default
`backend/app/ml/models/`):

| File | Produced by | Purpose |
|---|---|---|
| `xgboost_model.pkl` | `train.py` | Bundle: 3 models + feature columns + version + draw_config + calibration_bundle + metadata |
| `scaler.pkl` | `train.py` | Fitted `StandardScaler` — **required** alongside the model bundle; see below |
| `feature_importance.json` | `train.py` | Averaged, sorted feature importance — served by `/analytics/feature-importance` |
| `metrics.json` | `train.py` | MAE/RMSE, raw + draw-adjusted accuracy, draw recall/F1 — served by `/analytics/model-metrics` |
| `calibration_report.json` | `train.py` | Brier/ECE for isotonic, Platt, raw — which method was selected |
| `training_report.json` | `train.py` | Full training metadata, incl. sample/feature counts and `trained_at` timestamp |
| `best_params.json` | `hyperparameter_search.py` (optional) | Optuna-tuned hyperparameters, picked up automatically by the next `train.py` run |
| `model_audit_report.json` | `draw_optimizer.py` (optional) | Draw-prediction diagnostic report |

## Validating a newly trained model before deploying it

1. **Check the console output / `training_report.json`** for the headline
   numbers: `classifier_adjusted_accuracy`, `home_mae`/`away_mae`,
   `draw_recall_adjusted`. Compare against the previous bundle's
   `metrics.json` (back it up before overwriting) — a large regression in
   any of these is a red flag before you ship.
2. **Check `calibration_report.json`** — confirm `mean_brier` for the
   selected method is lower than `raw`'s, and ECE is reasonably small
   (target mentioned in `calibration.py`'s docstring: < 0.05). If
   calibration made things worse, something upstream (e.g. a data issue)
   likely needs investigation before trusting probabilities.
3. **Sanity-check the demo prediction** printed at the end of the training
   run — implausible expected goals (e.g. negative, or >9) or probabilities
   that don't sum to ~1.0 indicate something broke in the pipeline (they're
   clipped/renormalized by design, so this would point at a real bug, not
   just an extreme prediction).
4. **Confirm both files are present and paired.** `xgboost_model.pkl` and
   `scaler.pkl` must come from the **same training run** — `MatchPredictor.
   load()` will refuse to serve model predictions (falls back to historical
   averages) if the scaler is missing, and mixing a scaler from one run with
   a model bundle from another will silently produce nonsense (the model
   was trained on a different feature distribution than the mismatched
   scaler assumes). Deploy them as a pair, always overwrite both together.
5. **Run the test suite** (`cd backend && pytest`) against the new bundle,
   particularly `test_predictor.py`, before deploying — it exercises the
   predictor's fallback paths and basic prediction sanity checks.
6. **Restart the API process** after swapping model files — `MatchPredictor`
   loads the bundle once at startup (`get_predictor()` singleton via
   `app/main.py`'s lifespan); it does not hot-reload a changed file on disk.
7. Be aware of the known Elo-not-populated-at-inference gap (see
   `MODEL_PIPELINE.md`) — it affects *every* served prediction today,
   independent of which model bundle is loaded, since it's a request-time
   DataFrame issue, not a training-time one. A newly trained model won't fix
   it on its own.

## Common pitfalls

- Running `train.py` against a database with very few completed matches
  will silently produce a tiny/degenerate validation and test split (no
  explicit minimum-row check exists) — check the logged split sizes
  (`Split → train: X | val: Y | test: Z`) before trusting the reported
  metrics.
- `MODEL_VERSION` (in `backend/.env` / `Settings`) is not automatically
  bumped by `train.py` — it's a static setting. If you want
  `/analytics/model-metrics` and prediction responses to reflect a new
  version string, update `MODEL_VERSION` yourself before or after training.
- `best_params.json` silently changes what `train.py` does on its next run
  (uses Optuna params instead of hand-tuned defaults) — delete or rename it
  if you want to force a run with the original hand-tuned hyperparameters.
