"""
FIFA AI — Professional Training Pipeline
=========================================

Models trained
--------------
1. home_model   : XGBRegressor  → predicted home goals
2. away_model   : XGBRegressor  → predicted away goals
3. result_model : XGBClassifier → Home Win (2) / Draw (1) / Away Win (0)

Data source (WC-only retrain)
------------------------------
Trains from ``app/data/processed/matches_historical.csv`` (419 rows: 330
real WC matches 2002-2022 + 89 real 2026 matches, 13 of which are still
`status == "Scheduled"` and are excluded, leaving 406 completed matches) —
**not** the live Postgres `matches` table. The live Supabase DB is
unreachable from this environment (confirmed: `asyncpg` connection to
`DATABASE_URL` raises `ENOTFOUND` on the pooler host), and the Database
Engineering wave's `database/seed_wc2026.sql` loads this exact same CSV
content into Postgres — so CSV-based training and DB-based training are
expected to produce the same feature matrix once the DB is reachable.
``load_data()`` reads the CSV directly; a DB-backed path is kept available
via ``load_data_from_db()`` for environments where Postgres *is* reachable,
but is not used by default. See `MODEL_PIPELINE.md` for the full writeup.

Split strategy
--------------
419 rows (406 completed) is small for XGBoost, and football has real
temporal drift (team strength changes year to year), so a single random
split would leak information and a single arbitrary chronological split
risks an unreliable, noisy test set. The data has a natural structure: 6
complete, equal-sized World Cups (55 matches each, 2002-2022) plus a
partial, in-progress 2026 tournament (76 completed matches so far).

This module therefore supports two complementary schemes, both built on
the *same* chronological ordering (no shuffling, ever):

1. ``chronological_split()`` — single split used for the final
   train/val/test bundle that gets saved to disk. Train = all of
   2002-2022 (330 rows minus MIN_HISTORY warmup), validation = a
   held-out tail slice of that same historical range, test = the 2026
   completed matches (76 rows) — i.e. the model is validated on the
   *actual target tournament*, which is exactly how it will be used in
   production.
2. ``expanding_window_splits()`` — walk-forward CV by tournament: fold k
   trains on WCs up to and including year Y and validates on the very
   next WC. This yields 6 folds (train on {2002}→validate on 2006,
   train on {2002,2006}→validate on 2010, ... , train on
   {2002..2022}→validate on 2026-completed) and is used for
   hyperparameter search and for the cross-validation section of
   `MODEL_EVALUATION.md`, since a single small held-out slice is too
   noisy to trust as the sole evidence of generalization.

Usage
-----
    python -m app.ml.train
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.preprocessing import StandardScaler

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import get_settings
from app.ml.features.feature_engineering import (
    ROLLING_WINDOWS,
    build_feature_vector,
    build_team_index,
    compute_dynamic_elo,
)
from app.ml.draw_optimizer import compute_sample_weights, optimize_draw_threshold
from app.ml.calibration import fit_calibrators

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ─── Hyper-parameters ─────────────────────────────────────────────────────────

_REGRESSOR_PARAMS: dict = {
    "n_estimators":       1000,
    "max_depth":          8,
    "learning_rate":      0.03,
    "subsample":          0.85,
    "colsample_bytree":   0.85,
    "min_child_weight":   3,
    "gamma":              0.20,
    "reg_alpha":          0.20,
    "reg_lambda":         1.50,
    "objective":          "count:poisson",
    "eval_metric":        "rmse",
    "random_state":       42,
    "n_jobs":             -1,
    "early_stopping_rounds": 100,
}

_CLASSIFIER_PARAMS: dict = {
    "n_estimators":       1000,
    "max_depth":          7,
    "learning_rate":      0.03,
    "subsample":          0.85,
    "colsample_bytree":   0.85,
    "min_child_weight":   3,
    "gamma":              0.10,
    "reg_alpha":          0.20,
    "reg_lambda":         1.50,
    "objective":          "multi:softprob",
    "num_class":          3,
    "eval_metric":        "mlogloss",
    "random_state":       42,
    "n_jobs":             -1,
    "early_stopping_rounds": 100,
}

# ─── Load optimised hyperparameters (if available) ────────────────────────────

def _load_optimised_params() -> tuple[dict, dict, float]:
    """
    Load hyperparameters from ``best_params.json`` (produced by Optuna search).

    Returns (regressor_params, classifier_params, draw_weight_mult).
    Falls back to the hand-tuned defaults above if the file doesn't exist.
    """
    params_path = Path(settings.MODEL_PATH).parent / "best_params.json"
    if params_path.exists():
        try:
            with open(params_path) as f:
                data = json.load(f)
            reg = data.get("regressor_params", _REGRESSOR_PARAMS)
            clf = data.get("classifier_params", _CLASSIFIER_PARAMS)
            dwm = data.get("draw_weight_mult", 1.0)
            logger.info(
                "Loaded optimised hyperparameters from %s (draw_weight_mult=%.2f)",
                params_path, dwm,
            )
            return reg, clf, dwm
        except Exception as exc:
            logger.warning("Failed to load %s, using defaults: %s", params_path, exc)
    return _REGRESSOR_PARAMS.copy(), _CLASSIFIER_PARAMS.copy(), 1.0


# ─── Result label encoding ────────────────────────────────────────────────────
# Home Win → 2 | Draw → 1 | Away Win → 0
def _encode_result(home_score: float, away_score: float) -> int:
    if home_score > away_score:
        return 2
    if home_score == away_score:
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load data
# ═══════════════════════════════════════════════════════════════════════════════

# Path to the merged, WC-only training corpus produced by the Data Engineering
# wave. Resolved relative to this file (same convention as
# feature_engineering.py's _TEAMS_REFERENCE_PATH) so it doesn't depend on the
# process's current working directory.
_MATCHES_HISTORICAL_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "matches_historical.csv"
)


def load_data() -> pd.DataFrame:
    """
    Load completed WC matches directly from ``matches_historical.csv``.

    This is the primary/default data source for training (see module
    docstring for why: the live Supabase Postgres DB is unreachable from
    this environment, and the Database Engineering wave's
    ``database/seed_wc2026.sql`` loads this exact CSV content into
    Postgres, so this is not a lesser substitute — it's the same data,
    read directly instead of through a DB round-trip).

    Has a UTF-8 BOM (Excel-exported) — must be read with 'utf-8-sig' or
    the first column name comes back mangled (same gotcha documented in
    feature_engineering.py for teams_reference.csv).

    Filters to ``status == "Completed"`` with non-null scores — matches
    the same "completed matches only" contract the old DB-backed
    ``load_data()`` enforced via ``WHERE m.status = 'completed'``.
    """
    if not _MATCHES_HISTORICAL_PATH.exists():
        raise FileNotFoundError(
            f"matches_historical.csv not found at {_MATCHES_HISTORICAL_PATH}. "
            "This is the merged WC-only training corpus produced by the Data "
            "Engineering wave — see DATA_QUALITY_REPORT.md."
        )

    raw = pd.read_csv(_MATCHES_HISTORICAL_PATH, encoding="utf-8-sig")

    df = pd.DataFrame({
        "date":          pd.to_datetime(raw["date"]),
        "home_team":     raw["home_team"],
        "away_team":     raw["away_team"],
        "home_score":    pd.to_numeric(raw["home_score"], errors="coerce"),
        "away_score":    pd.to_numeric(raw["away_score"], errors="coerce"),
        # matches_historical.csv has no "tournament"/"neutral_venue" column —
        # every row is a FIFA World Cup match by construction (WC-only corpus,
        # per the explicit user decision to replace the old broad "all
        # competitions" dataset), and neutral_venue defaults to True since
        # essentially all WC matches (including every 2026 US/CA/MX match for
        # non-hosts) are played at a neutral site for at least one side. This
        # mirrors get_match_weight()'s "FIFA World Cup" = 1.00 weight exactly,
        # since every row is that tournament.
        "tournament":    "FIFA World Cup",
        "neutral_venue": True,
        "stage":         raw["stage"],
    })

    df = df[raw["status"].astype(str).str.strip().str.lower() == "completed"]
    df = df.dropna(subset=["home_score", "away_score"])
    df = df.sort_values("date").reset_index(drop=True)
    logger.info(
        "Loaded %d completed matches from %s",
        len(df), _MATCHES_HISTORICAL_PATH,
    )
    return df


def load_data_from_db() -> pd.DataFrame:
    """
    Load completed matches from the database via SQLAlchemy async.

    Kept available for environments where Postgres *is* reachable (this
    sandbox's Supabase instance is not — see module docstring), and for
    parity/reconciliation checks against ``load_data()``'s CSV path once a
    live DB is accessible. Not called by ``main()`` by default.
    """
    import asyncio
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = settings.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def _fetch() -> list:
        engine = create_async_engine(db_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT
                        m.date,
                        ht.name  AS home_team,
                        at.name  AS away_team,
                        m.home_score,
                        m.away_score,
                        m.tournament,
                        m.neutral_venue,
                        m.stage
                    FROM matches m
                    JOIN teams ht ON m.home_team_id = ht.id
                    JOIN teams at ON m.away_team_id = at.id
                    WHERE m.status = 'completed'
                      AND m.home_score IS NOT NULL
                      AND m.away_score IS NOT NULL
                    ORDER BY m.date ASC
                """)
            )
            rows = result.fetchall()
        await engine.dispose()
        return rows

    rows = asyncio.run(_fetch())
    df = pd.DataFrame(
        rows,
        columns=[
            "date", "home_team", "away_team",
            "home_score", "away_score",
            "tournament", "neutral_venue", "stage",
        ],
    )
    df["date"]       = pd.to_datetime(df["date"])
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"])
    df = df.sort_values("date").reset_index(drop=True)
    logger.info("Loaded %d completed matches from database", len(df))
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Build feature matrix
# ═══════════════════════════════════════════════════════════════════════════════

# MIN_HISTORY: rows skipped from the start of the (date-sorted) history
# because there isn't enough prior data for rolling-window features to mean
# anything yet. The old "all competitions" dataset (tens of thousands of
# rows spanning 1872-2017) used 100 as a small, cheap-to-discard warmup.
# matches_historical.csv is WC-only and starts at 2002 with *no* prior
# history at all (330 historical + 89 2026 rows, 406 completed) — a single
# World Cup is only 55 matches, so skipping 100 rows would silently discard
# almost two entire tournaments (36% of all historical data) before a
# single feature row is built. Rolling-window features already degrade
# gracefully to neutral defaults when a team has no history
# (`_empty_team_stats`), so a much smaller warmup is enough to avoid
# training on rows where literally every rolling feature is a hardcoded
# default; 30 (roughly half of one World Cup) was chosen to keep some
# real warm-up while not sacrificing a scarce, small dataset unnecessarily.
MIN_HISTORY: int = 30


def build_training_dataset(
    df: pd.DataFrame,
    min_history: int = MIN_HISTORY,
) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Build feature matrix X and three target vectors.

    Parameters
    ----------
    df          : Date-sorted match history (see ``load_data()``).
    min_history : Rows to skip from the start (not enough rolling history
        yet). Exposed as a parameter (rather than only the module-level
        constant) so ``expanding_window_splits()`` can rebuild feature rows
        per-fold without re-skipping the fold's own warmup twice.

    Returns
    -------
    X        : Feature DataFrame
    y_home   : Home goals (regression target)
    y_away   : Away goals (regression target)
    y_result : Encoded result 0/1/2 (classification target)
    match_dates : Series of match dates aligned 1:1 with X's rows — used
        downstream for tournament-boundary-aware CV splitting and for
        labeling which rows fall in which World Cup for reporting.
    """
    logger.info("Pre-computing Elo ratings …")
    df = compute_dynamic_elo(df)

    logger.info("Building team index …")
    team_index = build_team_index(df)

    logger.info("Engineering features for %d matches …", len(df))

    features_list: list[pd.DataFrame] = []
    y_home_list:   list[float] = []
    y_away_list:   list[float] = []
    y_result_list: list[int]   = []
    date_list:     list = []

    skipped = 0

    for idx in range(min_history, len(df)):
        row = df.iloc[idx]
        try:
            X_row = build_feature_vector(
                df=df,
                home_team=row["home_team"],
                away_team=row["away_team"],
                match_date=row["date"],
                tournament=row.get("tournament"),
                neutral_venue=bool(row.get("neutral_venue", False)),
                team_index=team_index,
            )
            features_list.append(X_row)
            y_home_list.append(float(row["home_score"]))
            y_away_list.append(float(row["away_score"]))
            y_result_list.append(
                _encode_result(row["home_score"], row["away_score"])
            )
            date_list.append(row["date"])
        except Exception as exc:
            logger.debug("Skipping match %d: %s", idx, exc)
            skipped += 1
            continue

        if idx % 2000 == 0:
            logger.info("  … %d / %d processed", idx, len(df))

    if skipped:
        logger.warning("Skipped %d matches during feature engineering", skipped)

    X = pd.concat(features_list, ignore_index=True)
    y_home   = pd.Series(y_home_list,   name="home_score",  dtype=float)
    y_away   = pd.Series(y_away_list,   name="away_score",  dtype=float)
    y_result = pd.Series(y_result_list, name="result",      dtype=int)
    match_dates = pd.Series(date_list, name="date")

    logger.info(
        "Feature matrix: %d rows × %d columns",
        X.shape[0], X.shape[1],
    )
    return X, y_home, y_away, y_result, match_dates


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Chronological split
# ═══════════════════════════════════════════════════════════════════════════════

def chronological_split(
    X: pd.DataFrame,
    *targets: pd.Series,
    train_frac: float = 0.70,
    val_frac:   float = 0.15,
) -> tuple:
    """
    Split data chronologically (no shuffling).

    Returns (X_train, X_val, X_test, *target_splits)
    where each target_split is (y_train, y_val, y_test).
    """
    n = len(X)
    train_end = int(n * train_frac)
    val_end   = int(n * (train_frac + val_frac))

    logger.info(
        "Split → train: %d | val: %d | test: %d",
        train_end,
        val_end - train_end,
        n - val_end,
    )

    X_train = X.iloc[:train_end]
    X_val   = X.iloc[train_end:val_end]
    X_test  = X.iloc[val_end:]

    split_targets = []
    for y in targets:
        split_targets.append((
            y.iloc[:train_end],
            y.iloc[train_end:val_end],
            y.iloc[val_end:],
        ))

    return (X_train, X_val, X_test, *split_targets)


def chronological_split_by_date(
    X: pd.DataFrame,
    match_dates: pd.Series,
    *targets: pd.Series,
    test_cutoff_year: int = 2026,
    val_frac: float = 0.15,
) -> tuple:
    """
    Split chronologically using calendar-year tournament boundaries instead
    of arbitrary row-count fractions.

    Test set  = every row whose match year is >= ``test_cutoff_year`` (i.e.
                the 2026 World Cup's completed matches) — this is the
                *actual target tournament* the model will be deployed on,
                which is a more realistic and more honestly-labeled test
                set than an arbitrary tail slice of mixed tournaments.
    Train/val = the remaining (pre-2026) rows, split by the tail
                ``val_frac`` fraction (still chronological, no shuffling)
                so validation immediately precedes the 2026 test rows.

    Returns (X_train, X_val, X_test, *target_splits), same shape as
    ``chronological_split()``.
    """
    years = pd.DatetimeIndex(match_dates).year
    test_mask = years >= test_cutoff_year
    pretest_idx = np.where(~test_mask)[0]
    test_idx = np.where(test_mask)[0]

    n_pretest = len(pretest_idx)
    val_start = int(n_pretest * (1.0 - val_frac))

    train_pos = pretest_idx[:val_start]
    val_pos = pretest_idx[val_start:]
    test_pos = test_idx

    logger.info(
        "Date-boundary split → train: %d | val: %d | test (year>=%d): %d",
        len(train_pos), len(val_pos), test_cutoff_year, len(test_pos),
    )

    X_train = X.iloc[train_pos]
    X_val   = X.iloc[val_pos]
    X_test  = X.iloc[test_pos]

    split_targets = []
    for y in targets:
        split_targets.append((
            y.iloc[train_pos],
            y.iloc[val_pos],
            y.iloc[test_pos],
        ))

    return (X_train, X_val, X_test, *split_targets)


def expanding_window_splits(
    X: pd.DataFrame,
    match_dates: pd.Series,
    *targets: pd.Series,
    fold_years: Optional[list[int]] = None,
) -> list[dict]:
    """
    Walk-forward (expanding-window) CV folds, one per World Cup boundary.

    matches_historical.csv has a clean natural structure: 6 complete,
    equal-sized World Cups (55 matches each, 2002/2006/2010/2014/2018/2022)
    plus a partial, in-progress 2026 tournament (76 completed matches as of
    this training run). Rather than force an arbitrary row-count K-fold
    (which would slice tournaments in half and mix future/past matches
    within a "fold"), each fold's boundary is a real tournament edge:

        Fold 1: train on {2002}                    → validate on 2006
        Fold 2: train on {2002,2006}                → validate on 2010
        Fold 3: train on {2002,2006,2010}           → validate on 2014
        Fold 4: train on {2002,2006,2010,2014}      → validate on 2018
        Fold 5: train on {2002,...,2018}            → validate on 2022
        Fold 6: train on {2002,...,2022} (330 rows) → validate on 2026
                (76 completed matches so far)

    This is standard walk-forward validation for time-series-structured
    data: the training window *expands* each fold (never shrinks, never
    looks backward), which matches how the model will actually be
    retrained over time as new tournaments complete, and every fold's
    validation set is drawn from a tournament the model has never seen —
    a materially stronger generalization check than a single holdout slice
    on a dataset this small.

    Returns a list of dicts, one per fold: ``{"fold": int, "train_years":
    list[int], "val_year": int, "train_idx": np.ndarray, "val_idx":
    np.ndarray, "n_train": int, "n_val": int}``. Caller is responsible for
    actually slicing X/targets by the returned positional indices (kept as
    indices, not pre-sliced frames, so the same fold plan can be reused
    across X, y_home, y_away, y_result without recomputation).
    """
    years_available = sorted(pd.DatetimeIndex(match_dates).year.unique().tolist())
    if fold_years is None:
        fold_years = years_available

    year_arr = pd.DatetimeIndex(match_dates).year.values
    folds: list[dict] = []

    for i in range(1, len(fold_years)):
        train_years = fold_years[:i]
        val_year = fold_years[i]

        train_idx = np.where(np.isin(year_arr, train_years))[0]
        val_idx = np.where(year_arr == val_year)[0]

        if len(train_idx) == 0 or len(val_idx) == 0:
            continue

        folds.append({
            "fold": len(folds) + 1,
            "train_years": train_years,
            "val_year": val_year,
            "train_idx": train_idx,
            "val_idx": val_idx,
            "n_train": int(len(train_idx)),
            "n_val": int(len(val_idx)),
        })

    return folds


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Train models
# ═══════════════════════════════════════════════════════════════════════════════

def train_models(
    X: pd.DataFrame,
    y_home: pd.Series,
    y_away: pd.Series,
    y_result: pd.Series,
    match_dates: Optional[pd.Series] = None,
) -> tuple[
    xgb.XGBRegressor,
    xgb.XGBRegressor,
    xgb.XGBClassifier,
    StandardScaler,
    list[str],
    dict,
    dict,
]:
    """
    Train all three models with a chronological split and early stopping.

    Returns
    -------
    home_model, away_model, result_model, scaler, feature_columns
    """
    feature_columns = X.columns.tolist()
    X = X.fillna(0.0)

    # ── Chronological split ───────────────────────────────────────────────────
    # Test = the 2026 World Cup's completed matches (the actual target
    # tournament), train/val = everything before it, when match_dates is
    # available (always true from build_training_dataset()). Falls back to
    # the old row-fraction chronological_split() only if a caller doesn't
    # have per-row dates (e.g. an older test fixture).
    if match_dates is not None:
        (
            X_train, X_val, X_test,
            (y_home_train,   y_home_val,   y_home_test),
            (y_away_train,   y_away_val,   y_away_test),
            (y_result_train, y_result_val, y_result_test),
        ) = chronological_split_by_date(X, match_dates, y_home, y_away, y_result)
    else:
        (
            X_train, X_val, X_test,
            (y_home_train,   y_home_val,   y_home_test),
            (y_away_train,   y_away_val,   y_away_test),
            (y_result_train, y_result_val, y_result_test),
        ) = chronological_split(X, y_home, y_away, y_result)

    # ── Scaling ───────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s   = scaler.transform(X_val)
    X_test_s  = scaler.transform(X_test)

    # ── Load hyperparameters (Optuna-optimised or hand-tuned defaults) ────────
    reg_params, clf_params, draw_weight_mult = _load_optimised_params()

    # ── Home goals regressor ──────────────────────────────────────────────────
    logger.info("Training HOME goals regressor …")
    home_model = xgb.XGBRegressor(**reg_params)
    home_model.fit(
        X_train_s, y_home_train,
        eval_set=[(X_val_s, y_home_val)],
        verbose=200,
    )

    # ── Away goals regressor ──────────────────────────────────────────────────
    logger.info("Training AWAY goals regressor …")
    away_model = xgb.XGBRegressor(**reg_params)
    away_model.fit(
        X_train_s, y_away_train,
        eval_set=[(X_val_s, y_away_val)],
        verbose=200,
    )

    # ── Result classifier (with class weighting) ──────────────────────────────
    logger.info("Training RESULT classifier (Home Win / Draw / Away Win) …")
    sample_weights = compute_sample_weights(y_result_train)
    # Apply Optuna-tuned draw weight multiplier (if > 1.0)
    if draw_weight_mult > 1.0:
        draw_mask = (y_result_train == 1)
        sample_weights[draw_mask] *= draw_weight_mult
        logger.info("  draw_weight_mult from Optuna: %.2f", draw_weight_mult)
    logger.info(
        "Class weight ratios → Away Win: %.2f | Draw: %.2f | Home Win: %.2f",
        sample_weights[y_result_train == 0].mean(),
        sample_weights[y_result_train == 1].mean(),
        sample_weights[y_result_train == 2].mean(),
    )
    result_model = xgb.XGBClassifier(**clf_params)
    result_model.fit(
        X_train_s, y_result_train,
        sample_weight=sample_weights,
        eval_set=[(X_val_s, y_result_val)],
        verbose=200,
    )

    # ── Optimize draw threshold on validation set ─────────────────────────────
    logger.info("Optimizing draw probability threshold on validation set …")
    val_proba = result_model.predict_proba(X_val_s)
    draw_boost, threshold_metrics = optimize_draw_threshold(
        y_result_val.values, val_proba
    )
    draw_config = {
        "draw_boost": float(draw_boost),
        "threshold_metrics": threshold_metrics,
        "class_weights": {
            str(c): float(sample_weights[y_result_train == c].mean())
            for c in [0, 1, 2]
        },
    }
    logger.info("Optimal draw_boost: %.3f", draw_boost)
    logger.info("Threshold metrics: %s", json.dumps(threshold_metrics, indent=2))

    # ── Probability calibration ───────────────────────────────────────────────
    logger.info("Fitting probability calibrators on validation set …")
    calibration_bundle, cal_method = fit_calibrators(
        y_result_val.values, val_proba
    )
    draw_config["calibration_method"] = cal_method
    draw_config["calibration_metrics"] = calibration_bundle.get("metrics", {})

    # ── Evaluation ────────────────────────────────────────────────────────────
    collected_metrics = _evaluate_models(
        home_model, away_model, result_model,
        X_test_s,
        y_home_test, y_away_test, y_result_test,
        feature_columns,
        draw_config,
    )

    return home_model, away_model, result_model, scaler, feature_columns, draw_config, calibration_bundle, collected_metrics


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Evaluate
# ═══════════════════════════════════════════════════════════════════════════════

def _evaluate_models(
    home_model:   xgb.XGBRegressor,
    away_model:   xgb.XGBRegressor,
    result_model: xgb.XGBClassifier,
    X_test_s:     np.ndarray,
    y_home_test:  pd.Series,
    y_away_test:  pd.Series,
    y_result_test: pd.Series,
    feature_columns: list[str],
    draw_config: dict | None = None,
) -> dict:
    """Log evaluation metrics, feature importance, and return collected metrics dict."""

    # ── Regression metrics ────────────────────────────────────────────────────
    home_preds = np.clip(home_model.predict(X_test_s), 0, 10)
    away_preds = np.clip(away_model.predict(X_test_s), 0, 10)

    home_mae  = mean_absolute_error(y_home_test, home_preds)
    away_mae  = mean_absolute_error(y_away_test, away_preds)
    home_rmse = float(np.sqrt(mean_squared_error(y_home_test, home_preds)))
    away_rmse = float(np.sqrt(mean_squared_error(y_away_test, away_preds)))

    logger.info("─" * 60)
    logger.info("REGRESSION METRICS (test set)")
    logger.info("  Home goals  →  MAE: %.4f  |  RMSE: %.4f", home_mae, home_rmse)
    logger.info("  Away goals  →  MAE: %.4f  |  RMSE: %.4f", away_mae, away_rmse)

    # ── Result accuracy from regressors ───────────────────────────────────────
    pred_result_from_reg = np.sign(np.round(home_preds) - np.round(away_preds))
    actual_result_sign   = np.sign(y_home_test.values - y_away_test.values)
    reg_result_acc = float((pred_result_from_reg == actual_result_sign).mean())
    logger.info("  Result accuracy (from regressors): %.4f", reg_result_acc)

    # ── Classifier metrics (raw) ──────────────────────────────────────────────
    clf_preds = result_model.predict(X_test_s)
    clf_acc   = accuracy_score(y_result_test, clf_preds)
    logger.info("─" * 60)
    logger.info("CLASSIFIER METRICS — RAW (test set)")
    logger.info("  Result accuracy (classifier, raw): %.4f", clf_acc)
    logger.info(
        "\n%s",
        classification_report(
            y_result_test, clf_preds,
            target_names=["Away Win", "Draw", "Home Win"],
            zero_division=0,
        ),
    )

    # ── Classifier metrics (draw-threshold adjusted) ──────────────────────────
    if draw_config and draw_config.get("draw_boost", 1.0) > 1.0:
        clf_proba = result_model.predict_proba(X_test_s)
        adjusted = clf_proba.copy()
        adjusted[:, 1] *= draw_config["draw_boost"]
        adjusted_preds = adjusted.argmax(axis=1)
        adj_acc = accuracy_score(y_result_test, adjusted_preds)
        logger.info("─" * 60)
        logger.info("CLASSIFIER METRICS — DRAW-ADJUSTED (test set)")
        logger.info("  draw_boost: %.3f", draw_config["draw_boost"])
        logger.info("  Result accuracy (adjusted): %.4f", adj_acc)
        logger.info(
            "\n%s",
            classification_report(
                y_result_test, adjusted_preds,
                target_names=["Away Win", "Draw", "Home Win"],
                zero_division=0,
            ),
        )

    # ── Feature importance ────────────────────────────────────────────────────
    _log_and_save_feature_importance(
        home_model, away_model, result_model, feature_columns
    )
    logger.info("─" * 60)

    # ── Collect all metrics ───────────────────────────────────────────────────
    collected_metrics = {
        "regression": {
            "home_mae": round(float(home_mae), 5),
            "home_rmse": round(float(home_rmse), 5),
            "away_mae": round(float(away_mae), 5),
            "away_rmse": round(float(away_rmse), 5),
            "regressor_result_accuracy": round(float(reg_result_acc), 5),
        },
        "classifier": {
            "raw_accuracy": round(float(clf_acc), 5),
            "raw_classification_report": classification_report(
                y_result_test, clf_preds,
                target_names=["Away Win", "Draw", "Home Win"],
                output_dict=True,
                zero_division=0,
            ),
        },
    }

    if draw_config and draw_config.get("draw_boost", 1.0) > 1.0:
        collected_metrics["classifier"]["adjusted_accuracy"] = round(float(adj_acc), 5)
        collected_metrics["classifier"]["draw_boost"] = draw_config["draw_boost"]
        collected_metrics["classifier"]["adjusted_classification_report"] = classification_report(
            y_result_test, adjusted_preds,
            target_names=["Away Win", "Draw", "Home Win"],
            output_dict=True,
            zero_division=0,
        )

    return collected_metrics


def _log_and_save_feature_importance(
    home_model:      xgb.XGBRegressor,
    away_model:      xgb.XGBRegressor,
    result_model:    xgb.XGBClassifier,
    feature_columns: list[str],
) -> None:
    """Average feature importance across all three models and save to JSON."""

    def _importance(model: xgb.XGBModel) -> np.ndarray:
        scores = model.feature_importances_
        total  = scores.sum()
        return scores / total if total > 0 else scores

    avg_importance = (
        _importance(home_model)
        + _importance(away_model)
        + _importance(result_model)
    ) / 3.0

    importance_pairs = sorted(
        zip(feature_columns, avg_importance.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    logger.info("TOP 20 FEATURES (averaged across all models):")
    for rank, (feat, score) in enumerate(importance_pairs[:20], 1):
        logger.info("  %2d. %-55s %.5f", rank, feat, score)

    # Save full list
    output_path = Path(settings.MODEL_PATH).parent / "feature_importance.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as fh:
        json.dump(
            [{"feature": f, "importance": round(s, 6)} for f, s in importance_pairs],
            fh,
            indent=2,
        )
    logger.info("Feature importance saved → %s", output_path)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Save model bundle
# ═══════════════════════════════════════════════════════════════════════════════

def save_models(
    home_model:      xgb.XGBRegressor,
    away_model:      xgb.XGBRegressor,
    result_model:    xgb.XGBClassifier,
    scaler:          StandardScaler,
    feature_columns: list[str],
    draw_config:     dict | None = None,
    calibration_bundle: dict | None = None,
) -> None:
    """Persist all models, scaler, and metadata to disk."""
    model_dir = Path(settings.MODEL_PATH).parent
    model_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "home_model":       home_model,
        "away_model":       away_model,
        "result_model":     result_model,
        "feature_columns":  feature_columns,
        "model_version":    settings.MODEL_VERSION,
        "trained_at":       datetime.now(tz=timezone.utc).isoformat(),
        "rolling_windows":  ROLLING_WINDOWS,
        "draw_config":      draw_config or {},
        "calibration_bundle": calibration_bundle or {},
        "metadata": {
            "home_model_type":   type(home_model).__name__,
            "away_model_type":   type(away_model).__name__,
            "result_model_type": type(result_model).__name__,
            "n_features":        len(feature_columns),
            "result_encoding":   {"Away Win": 0, "Draw": 1, "Home Win": 2},
        },
    }

    joblib.dump(bundle, settings.MODEL_PATH, compress=3)
    joblib.dump(scaler, settings.SCALER_PATH, compress=3)

    logger.info("Model bundle saved → %s", settings.MODEL_PATH)
    logger.info("Scaler saved       → %s", settings.SCALER_PATH)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Sample prediction demo
# ═══════════════════════════════════════════════════════════════════════════════

def _demo_prediction(
    df: pd.DataFrame,
    home_model:      xgb.XGBRegressor,
    away_model:      xgb.XGBRegressor,
    result_model:    xgb.XGBClassifier,
    scaler:          StandardScaler,
    feature_columns: list[str],
) -> None:
    """Run a sample prediction and print the full output."""
    from app.ml.poisson import PoissonEngine

    # Pick two well-known teams that exist in the dataset
    known_teams = df["home_team"].value_counts().head(10).index.tolist()
    if len(known_teams) < 2:
        return

    home_team = known_teams[0]
    away_team = known_teams[1]
    match_date = pd.Timestamp.now()

    team_index = build_team_index(df)
    X_demo = build_feature_vector(
        df=df,
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        team_index=team_index,
    )

    # Align columns
    for col in feature_columns:
        if col not in X_demo.columns:
            X_demo[col] = 0.0
    X_demo = X_demo[feature_columns].fillna(0.0)
    X_demo_s = scaler.transform(X_demo)

    home_xg = float(np.clip(home_model.predict(X_demo_s)[0], 0.05, 9.0))
    away_xg = float(np.clip(away_model.predict(X_demo_s)[0], 0.05, 9.0))

    # Classifier probabilities
    clf_proba = result_model.predict_proba(X_demo_s)[0]  # [away_win, draw, home_win]
    clf_away_win, clf_draw, clf_home_win = clf_proba

    # Poisson probabilities
    engine = PoissonEngine()
    poisson_result = engine.predict(home_xg, away_xg)

    # Blend: 60% Poisson + 40% classifier
    blend_home_win = 0.60 * poisson_result.home_win_probability + 0.40 * clf_home_win
    blend_draw     = 0.60 * poisson_result.draw_probability     + 0.40 * clf_draw
    blend_away_win = 0.60 * poisson_result.away_win_probability + 0.40 * clf_away_win
    total = blend_home_win + blend_draw + blend_away_win
    blend_home_win /= total
    blend_draw     /= total
    blend_away_win /= total

    output = {
        "home_team":             home_team,
        "away_team":             away_team,
        "expected_home_goals":   round(home_xg, 3),
        "expected_away_goals":   round(away_xg, 3),
        "home_win_probability":  round(blend_home_win, 4),
        "draw_probability":      round(blend_draw, 4),
        "away_win_probability":  round(blend_away_win, 4),
        "most_likely_score":     poisson_result.most_likely_score,
        "top_scorelines": [
            {"score": s.score, "probability": s.probability}
            for s in poisson_result.top_scorelines[:5]
        ],
    }

    logger.info("─" * 60)
    logger.info("SAMPLE PREDICTION: %s vs %s", home_team, away_team)
    logger.info(
        json.dumps(
            output,
            indent=2,
            default=float
        )
    )    
    logger.info("─" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3b — Walk-forward cross-validation (expanding window, by tournament)
# ═══════════════════════════════════════════════════════════════════════════════

def run_cv_evaluation(
    X: pd.DataFrame,
    y_home: pd.Series,
    y_away: pd.Series,
    y_result: pd.Series,
    match_dates: pd.Series,
    reg_params: Optional[dict] = None,
    clf_params: Optional[dict] = None,
) -> dict:
    """
    Run expanding-window walk-forward CV (see ``expanding_window_splits()``)
    and report per-fold + averaged metrics. This is the primary evidence of
    generalization for this retrain, given how small/noisy a single holdout
    slice would be (see `MODEL_EVALUATION.md`).

    Uses the same hyperparameters that will be used for the final model
    (Optuna-optimised if available), so these numbers are directly
    comparable to the final held-out test metrics.
    """
    X_filled = X.fillna(0.0)
    if reg_params is None or clf_params is None:
        loaded_reg, loaded_clf, _ = _load_optimised_params()
        reg_params = reg_params or loaded_reg
        clf_params = clf_params or loaded_clf

    folds = expanding_window_splits(X_filled, match_dates)
    fold_reports = []

    for fold in folds:
        train_idx, val_idx = fold["train_idx"], fold["val_idx"]

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_filled.iloc[train_idx])
        X_va_s = scaler.transform(X_filled.iloc[val_idx])

        y_home_tr, y_home_va = y_home.iloc[train_idx], y_home.iloc[val_idx]
        y_away_tr, y_away_va = y_away.iloc[train_idx], y_away.iloc[val_idx]
        y_res_tr, y_res_va = y_result.iloc[train_idx], y_result.iloc[val_idx]

        reg_fold_params = {**reg_params, "early_stopping_rounds": None}
        reg_fold_params.pop("early_stopping_rounds", None)
        clf_fold_params = {**clf_params}
        clf_fold_params.pop("early_stopping_rounds", None)

        home_m = xgb.XGBRegressor(**reg_fold_params)
        home_m.fit(X_tr_s, y_home_tr, verbose=0)
        away_m = xgb.XGBRegressor(**reg_fold_params)
        away_m.fit(X_tr_s, y_away_tr, verbose=0)

        sw = compute_sample_weights(y_res_tr)
        clf_m = xgb.XGBClassifier(**clf_fold_params)
        clf_m.fit(X_tr_s, y_res_tr, sample_weight=sw, verbose=0)

        home_pred = np.clip(home_m.predict(X_va_s), 0, 10)
        away_pred = np.clip(away_m.predict(X_va_s), 0, 10)
        clf_pred = clf_m.predict(X_va_s)

        home_mae = float(mean_absolute_error(y_home_va, home_pred))
        away_mae = float(mean_absolute_error(y_away_va, away_pred))
        clf_acc = float(accuracy_score(y_res_va, clf_pred))

        report = classification_report(
            y_res_va, clf_pred, output_dict=True, zero_division=0,
        )
        draw_recall = report.get("1", {}).get("recall", 0.0)
        draw_f1 = report.get("1", {}).get("f1-score", 0.0)

        fold_report = {
            "fold": fold["fold"],
            "train_years": fold["train_years"],
            "val_year": fold["val_year"],
            "n_train": fold["n_train"],
            "n_val": fold["n_val"],
            "home_mae": round(home_mae, 4),
            "away_mae": round(away_mae, 4),
            "accuracy": round(clf_acc, 4),
            "draw_recall": round(draw_recall, 4),
            "draw_f1": round(draw_f1, 4),
        }
        fold_reports.append(fold_report)
        logger.info(
            "  CV fold %d  train=%s val=%d (n_train=%d, n_val=%d)  "
            "acc=%.4f  home_mae=%.4f  away_mae=%.4f  draw_recall=%.4f",
            fold_report["fold"], fold["train_years"], fold["val_year"],
            fold["n_train"], fold["n_val"],
            clf_acc, home_mae, away_mae, draw_recall,
        )

    def _mean(key: str) -> float:
        vals = [f[key] for f in fold_reports]
        return round(float(np.mean(vals)), 4) if vals else 0.0

    def _std(key: str) -> float:
        vals = [f[key] for f in fold_reports]
        return round(float(np.std(vals)), 4) if vals else 0.0

    summary = {
        "n_folds": len(fold_reports),
        "folds": fold_reports,
        "mean_accuracy": _mean("accuracy"),
        "std_accuracy": _std("accuracy"),
        "mean_home_mae": _mean("home_mae"),
        "std_home_mae": _std("home_mae"),
        "mean_away_mae": _mean("away_mae"),
        "std_away_mae": _std("away_mae"),
        "mean_draw_recall": _mean("draw_recall"),
        "mean_draw_f1": _mean("draw_f1"),
    }

    logger.info("─" * 60)
    logger.info("WALK-FORWARD CV SUMMARY (%d folds)", summary["n_folds"])
    logger.info(
        "  Accuracy: %.4f ± %.4f", summary["mean_accuracy"], summary["std_accuracy"]
    )
    logger.info(
        "  Home MAE: %.4f ± %.4f", summary["mean_home_mae"], summary["std_home_mae"]
    )
    logger.info(
        "  Away MAE: %.4f ± %.4f", summary["mean_away_mae"], summary["std_away_mae"]
    )
    logger.info("  Draw recall (mean): %.4f", summary["mean_draw_recall"])
    logger.info("─" * 60)

    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("=" * 60)
    logger.info("FIFA AI — Training Pipeline  v%s", settings.MODEL_VERSION)
    logger.info("=" * 60)

    # 1. Load
    df = load_data()

    # 2. Features
    X, y_home, y_away, y_result, match_dates = build_training_dataset(df)

    # 3. Walk-forward CV (evaluation only — informs confidence in step 4's
    #    single final split; does not affect what gets saved to disk)
    logger.info("Running walk-forward cross-validation …")
    cv_summary = run_cv_evaluation(X, y_home, y_away, y_result, match_dates)

    # 4. Train (final model on the date-boundary chronological split)
    home_model, away_model, result_model, scaler, feature_columns, draw_config, cal_bundle, collected_metrics = train_models(
        X, y_home, y_away, y_result, match_dates
    )

    # 5. Save
    save_models(home_model, away_model, result_model, scaler, feature_columns, draw_config, cal_bundle)

    # 6. Generate reports
    _generate_reports(collected_metrics, draw_config, cal_bundle, len(X), len(feature_columns), cv_summary)

    # 7. Demo
    _demo_prediction(df, home_model, away_model, result_model, scaler, feature_columns)

    logger.info("Training complete ✓")


def _generate_reports(
    metrics: dict,
    draw_config: dict,
    cal_bundle: dict,
    n_samples: int,
    n_features: int,
    cv_summary: Optional[dict] = None,
) -> None:
    """Generate metrics.json, calibration_report.json, and training_report.json."""
    model_dir = Path(settings.MODEL_PATH).parent
    model_dir.mkdir(parents=True, exist_ok=True)

    # ── metrics.json ──────────────────────────────────────────────────────────
    metrics_out = {
        "home_mae": metrics["regression"]["home_mae"],
        "home_rmse": metrics["regression"]["home_rmse"],
        "away_mae": metrics["regression"]["away_mae"],
        "away_rmse": metrics["regression"]["away_rmse"],
        "regressor_result_accuracy": metrics["regression"]["regressor_result_accuracy"],
        "classifier_raw_accuracy": metrics["classifier"]["raw_accuracy"],
        "classifier_adjusted_accuracy": metrics["classifier"].get("adjusted_accuracy", metrics["classifier"]["raw_accuracy"]),
        "draw_boost": metrics["classifier"].get("draw_boost", 1.0),
        "draw_recall_raw": metrics["classifier"]["raw_classification_report"].get("Draw", {}).get("recall", 0.0),
        "draw_f1_raw": metrics["classifier"]["raw_classification_report"].get("Draw", {}).get("f1-score", 0.0),
    }

    adj_report = metrics["classifier"].get("adjusted_classification_report")
    if adj_report:
        metrics_out["draw_recall_adjusted"] = adj_report.get("Draw", {}).get("recall", 0.0)
        metrics_out["draw_f1_adjusted"] = adj_report.get("Draw", {}).get("f1-score", 0.0)

    with open(model_dir / "metrics.json", "w") as f:
        json.dump(metrics_out, f, indent=2, default=float)
    logger.info("Saved → %s", model_dir / "metrics.json")

    # ── calibration_report.json ───────────────────────────────────────────────
    cal_metrics = cal_bundle.get("metrics", {})
    cal_report = {
        "selected_method": cal_bundle.get("method", "none"),
        "isotonic": cal_metrics.get("isotonic", {}),
        "platt": cal_metrics.get("platt", {}),
        "raw": cal_metrics.get("raw", {}),
    }
    with open(model_dir / "calibration_report.json", "w") as f:
        json.dump(cal_report, f, indent=2, default=float)
    logger.info("Saved → %s", model_dir / "calibration_report.json")

    # ── training_report.json ──────────────────────────────────────────────────
    training_report = {
        "model_version": settings.MODEL_VERSION,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "n_training_samples": n_samples,
        "n_features": n_features,
        "regressor_objective": "count:poisson",
        "classifier_objective": "multi:softprob",
        "draw_config": {
            "draw_boost": draw_config.get("draw_boost", 1.0),
            "threshold_metrics": draw_config.get("threshold_metrics", {}),
            "class_weights": draw_config.get("class_weights", {}),
        },
        "calibration_method": cal_bundle.get("method", "none"),
        "metrics": metrics_out,
        "cross_validation": cv_summary or {},
    }
    with open(model_dir / "training_report.json", "w") as f:
        json.dump(training_report, f, indent=2, default=float)
    logger.info("Saved → %s", model_dir / "training_report.json")

    # ── cv_report.json ────────────────────────────────────────────────────────
    if cv_summary:
        with open(model_dir / "cv_report.json", "w") as f:
            json.dump(cv_summary, f, indent=2, default=float)
        logger.info("Saved → %s", model_dir / "cv_report.json")


if __name__ == "__main__":
    main()
