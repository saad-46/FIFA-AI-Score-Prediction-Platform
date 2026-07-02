"""
FIFA AI — Optuna Hyperparameter Search
========================================

Jointly optimises three XGBoost models (home goals, away goals, result
classifier) using a shared feature pipeline and chronological validation.

Objective
---------
Maximise a composite score that balances:
  - Result accuracy (from classifier)
  - Draw recall (critical weakness)
  - Home goals MAE (regressor quality)
  - Away goals MAE (regressor quality)

Search space
------------
  learning_rate        : [0.005, 0.10]  (log-uniform)
  max_depth            : [3, 10]
  gamma                : [0.0, 1.0]
  reg_alpha            : [0.01, 2.0]   (log-uniform)
  reg_lambda           : [0.5, 5.0]
  subsample            : [0.6, 1.0]
  colsample_bytree     : [0.5, 1.0]
  n_estimators         : [200, 2000]
  min_child_weight     : [1, 10]
  draw_weight_mult     : [1.0, 5.0]   (draw-class weight multiplier)

Output
------
  best_params.json — best hyperparameters for each model type.

Usage
-----
    python -m app.ml.hyperparameter_search            # 100 trials (default)
    python -m app.ml.hyperparameter_search --trials 200
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error
from sklearn.preprocessing import StandardScaler

try:
    import optuna
    from optuna.pruners import MedianPruner
    from optuna.samplers import TPESampler
except ImportError:
    raise ImportError(
        "Optuna is required for hyperparameter search. "
        "Install it with:  pip install optuna"
    )

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import get_settings
from app.ml.draw_optimizer import compute_sample_weights, optimize_draw_threshold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress optuna's verbose logging
optuna.logging.set_verbosity(optuna.logging.WARNING)

settings = get_settings()


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH SPACE
# ═══════════════════════════════════════════════════════════════════════════════

def _suggest_regressor_params(trial: optuna.Trial) -> dict:
    """Sample regressor hyperparameters from the search space."""
    return {
        "n_estimators":       trial.suggest_int("reg_n_estimators", 200, 2000, step=100),
        "max_depth":          trial.suggest_int("reg_max_depth", 3, 10),
        "learning_rate":      trial.suggest_float("reg_learning_rate", 0.005, 0.10, log=True),
        "subsample":          trial.suggest_float("reg_subsample", 0.6, 1.0),
        "colsample_bytree":   trial.suggest_float("reg_colsample_bytree", 0.5, 1.0),
        "min_child_weight":   trial.suggest_int("reg_min_child_weight", 1, 10),
        "gamma":              trial.suggest_float("reg_gamma", 0.0, 1.0),
        "reg_alpha":          trial.suggest_float("reg_alpha", 0.01, 2.0, log=True),
        "reg_lambda":         trial.suggest_float("reg_lambda", 0.5, 5.0),
        "objective":          "count:poisson",
        "eval_metric":        "rmse",
        "random_state":       42,
        "n_jobs":             -1,
        "early_stopping_rounds": 80,
    }


def _suggest_classifier_params(trial: optuna.Trial) -> dict:
    """Sample classifier hyperparameters from the search space."""
    return {
        "n_estimators":       trial.suggest_int("clf_n_estimators", 200, 2000, step=100),
        "max_depth":          trial.suggest_int("clf_max_depth", 3, 10),
        "learning_rate":      trial.suggest_float("clf_learning_rate", 0.005, 0.10, log=True),
        "subsample":          trial.suggest_float("clf_subsample", 0.6, 1.0),
        "colsample_bytree":   trial.suggest_float("clf_colsample_bytree", 0.5, 1.0),
        "min_child_weight":   trial.suggest_int("clf_min_child_weight", 1, 10),
        "gamma":              trial.suggest_float("clf_gamma", 0.0, 1.0),
        "reg_alpha":          trial.suggest_float("clf_alpha", 0.01, 2.0, log=True),
        "reg_lambda":         trial.suggest_float("clf_lambda", 0.5, 5.0),
        "objective":          "multi:softprob",
        "num_class":          3,
        "eval_metric":        "mlogloss",
        "random_state":       42,
        "n_jobs":             -1,
        "early_stopping_rounds": 80,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OBJECTIVE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

class HyperparamObjective:
    """
    Optuna objective that trains all three models with trial-suggested
    hyperparameters and returns a composite score.

    The data splits are computed once and reused across all trials.
    """

    def __init__(
        self,
        X_train_s: np.ndarray,
        X_val_s: np.ndarray,
        y_home_train: np.ndarray,
        y_home_val: np.ndarray,
        y_away_train: np.ndarray,
        y_away_val: np.ndarray,
        y_result_train: np.ndarray,
        y_result_val: np.ndarray,
    ) -> None:
        self.X_train_s = X_train_s
        self.X_val_s = X_val_s
        self.y_home_train = y_home_train
        self.y_home_val = y_home_val
        self.y_away_train = y_away_train
        self.y_away_val = y_away_val
        self.y_result_train = y_result_train
        self.y_result_val = y_result_val

        # Pre-compute base sample weights (class-balanced)
        self._base_weights = compute_sample_weights(y_result_train)

    def __call__(self, trial: optuna.Trial) -> float:
        # ── Regressor params ──────────────────────────────────────────────────
        reg_params = _suggest_regressor_params(trial)

        # ── Home regressor ────────────────────────────────────────────────────
        home_model = xgb.XGBRegressor(**reg_params)
        home_model.fit(
            self.X_train_s, self.y_home_train,
            eval_set=[(self.X_val_s, self.y_home_val)],
            verbose=0,
        )
        home_preds = np.clip(home_model.predict(self.X_val_s), 0, 10)
        home_mae = mean_absolute_error(self.y_home_val, home_preds)

        # ── Away regressor ────────────────────────────────────────────────────
        away_model = xgb.XGBRegressor(**reg_params)
        away_model.fit(
            self.X_train_s, self.y_away_train,
            eval_set=[(self.X_val_s, self.y_away_val)],
            verbose=0,
        )
        away_preds = np.clip(away_model.predict(self.X_val_s), 0, 10)
        away_mae = mean_absolute_error(self.y_away_val, away_preds)

        # Prune early if regressors are very poor
        trial.report(home_mae + away_mae, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned()

        # ── Classifier params ─────────────────────────────────────────────────
        clf_params = _suggest_classifier_params(trial)

        # Draw weight multiplier — boosts draw-class samples further
        draw_weight_mult = trial.suggest_float("draw_weight_mult", 1.0, 5.0)
        sample_weights = self._base_weights.copy()
        draw_mask = self.y_result_train == 1
        sample_weights[draw_mask] *= draw_weight_mult

        # ── Classifier ────────────────────────────────────────────────────────
        clf_model = xgb.XGBClassifier(**clf_params)
        clf_model.fit(
            self.X_train_s, self.y_result_train,
            sample_weight=sample_weights,
            eval_set=[(self.X_val_s, self.y_result_val)],
            verbose=0,
        )

        clf_proba = clf_model.predict_proba(self.X_val_s)
        clf_preds = clf_proba.argmax(axis=1)
        clf_acc = accuracy_score(self.y_result_val, clf_preds)

        report = classification_report(
            self.y_result_val, clf_preds, output_dict=True, zero_division=0,
        )
        draw_recall = report.get("1", {}).get("recall", 0.0)
        draw_f1 = report.get("1", {}).get("f1-score", 0.0)

        # Prune if classifier is poor
        trial.report(clf_acc, step=1)
        if trial.should_prune():
            raise optuna.TrialPruned()

        # ── Composite objective (MAXIMISE) ────────────────────────────────────
        # Components (all in [0, 1] or scaled to be):
        #   accuracy     : higher is better, target 0.65+
        #   draw_recall  : higher is better, target 0.20+
        #   home_mae_inv : (2 - home_mae) / 2, higher is better
        #   away_mae_inv : (2 - away_mae) / 2, higher is better
        home_mae_score = max(0.0, (2.0 - home_mae) / 2.0)
        away_mae_score = max(0.0, (2.0 - away_mae) / 2.0)

        draw_penalty = 0.0

        if draw_recall > 0.75 and clf_acc < 0.50:
            draw_penalty = 0.10

        composite = (
            0.55 * clf_acc
            + 0.10 * draw_recall
            + 0.10 * draw_f1
            + 0.15 * home_mae_score
            + 0.10 * away_mae_score
            - draw_penalty
        )

        # Log progress
        trial.set_user_attr("accuracy", round(clf_acc, 4))
        trial.set_user_attr("draw_recall", round(draw_recall, 4))
        trial.set_user_attr("draw_f1", round(draw_f1, 4))
        trial.set_user_attr("home_mae", round(home_mae, 4))
        trial.set_user_attr("away_mae", round(away_mae, 4))

        return composite


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_search(n_trials: int = 100) -> dict:
    """
    Run the full Optuna hyperparameter search.

    Parameters
    ----------
    n_trials : Number of optimisation trials to run (minimum 100).

    Returns
    -------
    Dict with best parameters and metrics.
    """
    # ── Import data pipeline (local to avoid circular import) ─────────────────
    from app.ml.train import (
        load_data,
        build_training_dataset,
        chronological_split,
    )

    logger.info("=" * 60)
    logger.info("FIFA AI — Optuna Hyperparameter Search (%d trials)", n_trials)
    logger.info("=" * 60)

    # ── Load & prepare data ───────────────────────────────────────────────────
    df = load_data()
    X, y_home, y_away, y_result = build_training_dataset(df)

    (
        X_train, X_val, X_test,
        (y_home_train, y_home_val, y_home_test),
        (y_away_train, y_away_val, y_away_test),
        (y_result_train, y_result_val, y_result_test),
    ) = chronological_split(X, y_home, y_away, y_result)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train.fillna(0.0))
    X_val_s   = scaler.transform(X_val.fillna(0.0))
    X_test_s  = scaler.transform(X_test.fillna(0.0))

    # ── Create objective ──────────────────────────────────────────────────────
    objective = HyperparamObjective(
        X_train_s, X_val_s,
        y_home_train.values, y_home_val.values,
        y_away_train.values, y_away_val.values,
        y_result_train.values, y_result_val.values,
    )

    # ── Run Optuna study ──────────────────────────────────────────────────────
    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=1),
        study_name="fifa_ai_hpo",
    )

    logger.info("Starting optimisation …")
    study.optimize(
        objective,
        n_trials=n_trials,
        show_progress_bar=True,
        gc_after_trial=True,
    )

    best = study.best_trial
    logger.info("=" * 60)
    logger.info("BEST TRIAL: #%d", best.number)
    logger.info("  Composite score: %.4f", best.value)
    logger.info("  Accuracy:        %.4f", best.user_attrs.get("accuracy", 0))
    logger.info("  Draw Recall:     %.4f", best.user_attrs.get("draw_recall", 0))
    logger.info("  Draw F1:         %.4f", best.user_attrs.get("draw_f1", 0))
    logger.info("  Home MAE:        %.4f", best.user_attrs.get("home_mae", 0))
    logger.info("  Away MAE:        %.4f", best.user_attrs.get("away_mae", 0))
    logger.info("=" * 60)

    # ── Extract best params by model type ─────────────────────────────────────
    best_regressor_params = {
        k.replace("reg_", ""): v
        for k, v in best.params.items()
        if k.startswith("reg_")
    }
    best_regressor_params.update({
        "objective": "count:poisson",
        "eval_metric": "rmse",
        "random_state": 42,
        "n_jobs": -1,
        "early_stopping_rounds": 100,
    })

    best_classifier_params = {
        k.replace("clf_", ""): v
        for k, v in best.params.items()
        if k.startswith("clf_")
    }
    best_classifier_params.update({
        "objective": "multi:softprob",
        "num_class": 3,
        "eval_metric": "mlogloss",
        "random_state": 42,
        "n_jobs": -1,
        "early_stopping_rounds": 100,
    })

    draw_weight_mult = best.params.get("draw_weight_mult", 1.0)

    result = {
        "regressor_params":   best_regressor_params,
        "classifier_params":  best_classifier_params,
        "draw_weight_mult":   round(draw_weight_mult, 3),
        "best_trial_number":  best.number,
        "best_composite":     round(best.value, 4),
        "best_metrics":       best.user_attrs,
        "n_trials":           n_trials,
        "n_completed":        len(study.trials),
    }

    # ── Validate on held-out test set ─────────────────────────────────────────
    logger.info("Validating best params on TEST set …")
    test_metrics = _validate_on_test(
        best_regressor_params, best_classifier_params, draw_weight_mult,
        X_train_s, X_test_s,
        y_home_train.values, y_home_test.values,
        y_away_train.values, y_away_test.values,
        y_result_train.values, y_result_test.values,
        X_val_s, y_home_val.values, y_away_val.values, y_result_val.values,
    )
    result["test_set_metrics"] = test_metrics

    # ── Save ──────────────────────────────────────────────────────────────────
    output_path = Path(settings.MODEL_PATH).parent / "best_params.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info("Best parameters saved → %s", output_path)

    return result


def _validate_on_test(
    reg_params: dict,
    clf_params: dict,
    draw_weight_mult: float,
    X_train_s: np.ndarray,
    X_test_s: np.ndarray,
    y_home_train: np.ndarray,
    y_home_test: np.ndarray,
    y_away_train: np.ndarray,
    y_away_test: np.ndarray,
    y_result_train: np.ndarray,
    y_result_test: np.ndarray,
    X_val_s: np.ndarray,
    y_home_val: np.ndarray,
    y_away_val: np.ndarray,
    y_result_val: np.ndarray,
) -> dict:
    """Train with best params on full train set and evaluate on test."""
    # Home regressor
    home_model = xgb.XGBRegressor(**reg_params)
    home_model.fit(
        X_train_s, y_home_train,
        eval_set=[(X_val_s, y_home_val)],
        verbose=0,
    )
    home_preds = np.clip(home_model.predict(X_test_s), 0, 10)
    home_mae = float(mean_absolute_error(y_home_test, home_preds))

    # Away regressor
    away_model = xgb.XGBRegressor(**reg_params)
    away_model.fit(
        X_train_s, y_away_train,
        eval_set=[(X_val_s, y_away_val)],
        verbose=0,
    )
    away_preds = np.clip(away_model.predict(X_test_s), 0, 10)
    away_mae = float(mean_absolute_error(y_away_test, away_preds))

    # Classifier
    base_weights = compute_sample_weights(y_result_train)
    sample_weights = base_weights.copy()
    sample_weights[y_result_train == 1] *= draw_weight_mult

    clf_model = xgb.XGBClassifier(**clf_params)
    clf_model.fit(
        X_train_s, y_result_train,
        sample_weight=sample_weights,
        eval_set=[(X_val_s, y_result_val)],
        verbose=0,
    )

    clf_preds = clf_model.predict(X_test_s)
    clf_acc = float(accuracy_score(y_result_test, clf_preds))
    report = classification_report(
        y_result_test, clf_preds, output_dict=True, zero_division=0,
    )

    draw_recall = report.get("1", {}).get("recall", 0.0)
    draw_f1 = report.get("1", {}).get("f1-score", 0.0)

    metrics = {
        "accuracy":     round(clf_acc, 4),
        "draw_recall":  round(draw_recall, 4),
        "draw_f1":      round(draw_f1, 4),
        "home_mae":     round(home_mae, 4),
        "away_mae":     round(away_mae, 4),
    }

    logger.info("TEST SET METRICS:")
    for k, v in metrics.items():
        logger.info("  %-15s %.4f", k, v)

    return metrics


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FIFA AI — Optuna Hyperparameter Search",
    )
    parser.add_argument(
        "--trials", type=int, default=100,
        help="Number of optimisation trials (default: 100).",
    )
    args = parser.parse_args()
    run_search(n_trials=max(args.trials, 10))


if __name__ == "__main__":
    main()
