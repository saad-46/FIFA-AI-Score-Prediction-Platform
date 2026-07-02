"""
FIFA AI — Draw Prediction Optimization & Model Diagnostic Audit
================================================================

Phase 1 – Diagnostic audit:
  Identifies why draw recall is near zero, analyses feature importance,
  detects home-win over-prediction, and checks regressor bias.

Phase 2 – Draw optimization:
  Benchmarks four classifier variants:
    1. Baseline           — current params, no weighting
    2. Weighted           — inverse-frequency sample weights
    3. Baseline+Threshold — baseline + optimised draw_boost
    4. Combined           — weighted + optimised draw_boost

Exports (imported by train.py):
  compute_sample_weights()
  optimize_draw_threshold()

Generates:
  model_audit_report.json

Usage
-----
    python -m app.ml.draw_optimizer
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import StandardScaler

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

_LABEL_NAMES = {0: "Away Win", 1: "Draw", 2: "Home Win"}


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS — imported by train.py
# ═══════════════════════════════════════════════════════════════════════════════

def compute_sample_weights(y: pd.Series | np.ndarray) -> np.ndarray:
    """
    Inverse-frequency class weights for balanced training.

    Formula
    -------
    weight[c] = n_total / (n_classes × n_c)

    For typical football data (~46 % Home Win, ~27 % Draw, ~27 % Away Win)
    this yields weights ≈ [1.23, 1.23, 0.72] for [Away, Draw, Home].

    Parameters
    ----------
    y : Array of integer class labels (0 / 1 / 2).

    Returns
    -------
    np.ndarray of per-sample weights, same length as *y*.
    """
    y_arr = np.asarray(y, dtype=int)
    max_label = int(y_arr.max()) + 1
    counts = np.bincount(y_arr, minlength=max_label)
    n_classes = (counts > 0).sum()
    n_total = len(y_arr)
    class_weights = n_total / (n_classes * np.maximum(counts, 1))
    return class_weights[y_arr].astype(np.float64)


def optimize_draw_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    search_range: Tuple[float, float, float] = (1.0, 5.0, 0.05),
) -> Tuple[float, dict]:
    """
    Grid-search for the draw-probability multiplier that maximises a
    composite metric of accuracy + draw recall + draw F1.

    Instead of ``argmax(p)`` the adjusted decision rule is
    ``argmax([p_away, p_draw × boost, p_home])``.

    Parameters
    ----------
    y_true       : Ground-truth labels (0 = Away Win, 1 = Draw, 2 = Home Win).
    y_proba      : Predicted probabilities, shape ``(n, 3)``.
    search_range : ``(start, end, step)`` for the boost values to evaluate.

    Returns
    -------
    best_boost   : Optimal draw multiplier.
    best_metrics : Dict with accuracy, draw_recall, draw_precision, draw_f1,
                   and composite_score.
    """
    start, end, step = search_range
    best_score = -1.0
    best_boost = 1.0
    best_metrics: dict[str, Any] = {}

    for boost in np.arange(start, end + step, step):
        adjusted = y_proba.copy()
        adjusted[:, 1] *= boost
        preds = adjusted.argmax(axis=1)

        acc = accuracy_score(y_true, preds)
        report = classification_report(
            y_true, preds, output_dict=True, zero_division=0,
        )
        draw = report.get("1", {})
        dr = draw.get("recall", 0.0)
        dp = draw.get("precision", 0.0)
        df1 = draw.get("f1-score", 0.0)

        # Composite — rewards draw recall without tanking accuracy
        score = 0.50 * acc + 0.30 * dr + 0.20 * df1

        if score > best_score:
            best_score = score
            best_boost = float(round(boost, 3))
            best_metrics = {
                "accuracy":        round(acc, 4),
                "draw_recall":     round(dr, 4),
                "draw_precision":  round(dp, 4),
                "draw_f1":         round(df1, 4),
                "composite_score": round(score, 4),
            }

    return best_boost, best_metrics


# ═══════════════════════════════════════════════════════════════════════════════
# EXPERIMENT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _class_distribution(y: np.ndarray, label: str = "") -> dict:
    """Return class-count dict and log it."""
    counts = np.bincount(y, minlength=3)
    total = int(counts.sum())
    dist: dict[str, Any] = {}
    for c in range(3):
        dist[_LABEL_NAMES[c]] = {
            "count": int(counts[c]),
            "percentage": round(100.0 * counts[c] / max(total, 1), 2),
        }
    if label:
        logger.info("  %-6s class distribution: %s", label, dist)
    return dist


def _train_variant(
    name: str,
    params: dict,
    X_train_s: np.ndarray,
    y_train: np.ndarray,
    X_val_s: np.ndarray,
    y_val: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> xgb.XGBClassifier:
    """Train a single classifier variant."""
    logger.info("Training variant: %s …", name)
    model = xgb.XGBClassifier(**params)
    fit_kwargs: dict[str, Any] = {
        "eval_set": [(X_val_s, y_val)],
        "verbose": 0,
    }
    if sample_weight is not None:
        fit_kwargs["sample_weight"] = sample_weight
    model.fit(X_train_s, y_train, **fit_kwargs)
    return model


def _evaluate_variant(
    name: str,
    model: xgb.XGBClassifier,
    X_test_s: np.ndarray,
    y_test: np.ndarray,
    draw_boost: float = 1.0,
) -> dict:
    """Evaluate a classifier variant and return a metrics dict."""
    proba = model.predict_proba(X_test_s)
    adjusted = proba.copy()
    adjusted[:, 1] *= draw_boost
    preds = adjusted.argmax(axis=1)

    acc = accuracy_score(y_test, preds)
    report = classification_report(
        y_test, preds,
        target_names=["Away Win", "Draw", "Home Win"],
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(y_test, preds).tolist()

    draw_m = report.get("Draw", {})
    metrics: dict[str, Any] = {
        "name":             name,
        "accuracy":         round(acc, 4),
        "draw_recall":      round(draw_m.get("recall", 0.0), 4),
        "draw_precision":   round(draw_m.get("precision", 0.0), 4),
        "draw_f1":          round(draw_m.get("f1-score", 0.0), 4),
        "home_win_recall":  round(report.get("Home Win", {}).get("recall", 0.0), 4),
        "away_win_recall":  round(report.get("Away Win", {}).get("recall", 0.0), 4),
        "draw_boost":       round(draw_boost, 3),
        "confusion_matrix": cm,
    }

    logger.info(
        "  %-25s  Acc: %.4f  Draw-R: %.4f  Draw-F1: %.4f  Boost: %.2f",
        name, acc, metrics["draw_recall"], metrics["draw_f1"], draw_boost,
    )
    return metrics


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE IMPORTANCE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_features() -> dict:
    """Analyse saved feature importance from the last training run."""
    fi_path = Path(settings.FEATURE_IMPORTANCE_PATH)
    if not fi_path.exists():
        return {"error": "feature_importance.json not found"}

    with open(fi_path) as f:
        features: list[dict] = json.load(f)

    top_10 = features[:10]
    bottom_10 = features[-10:]
    total_importance = sum(f["importance"] for f in features)
    top_10_share = sum(f["importance"] for f in top_10) / max(total_importance, 1e-9)
    mid = len(features) // 2
    bottom_half = features[mid:]
    bottom_half_share = sum(f["importance"] for f in bottom_half) / max(total_importance, 1e-9)

    return {
        "total_features":                len(features),
        "top_10_features":               top_10,
        "bottom_10_features":            bottom_10,
        "top_10_importance_share":       round(top_10_share, 4),
        "bottom_50pct_importance_share": round(bottom_half_share, 4),
        "recommendation": (
            f"Consider removing features below 0.004 importance. "
            f"Bottom 50% of features contribute only {bottom_half_share:.1%} "
            f"of total importance — pruning them may reduce noise."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXPERIMENT
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Run the full diagnostic audit and draw-optimisation experiment.

    Steps
    -----
    1. Load data & build features  (reuses ``train.py`` functions).
    2. Phase 1 — Diagnostic audit  (class distribution, feature analysis,
       home-win over-prediction check).
    3. Phase 2 — Train & evaluate four classifier variants.
    4. Select the best variant and save ``model_audit_report.json``.
    """
    # Local imports to avoid circular dependency with train.py
    from app.ml.train import (
        load_data,
        build_training_dataset,
        chronological_split,
        _CLASSIFIER_PARAMS,
    )

    logger.info("=" * 60)
    logger.info("FIFA AI — Draw Prediction Diagnostic & Optimization")
    logger.info("=" * 60)

    # ── 1. Load data & features ───────────────────────────────────────────────
    df = load_data()
    X, y_home, y_away, y_result = build_training_dataset(df)

    # ── 2. Chronological split ────────────────────────────────────────────────
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

    y_tr = y_result_train.values
    y_va = y_result_val.values
    y_te = y_result_test.values

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1 — DIAGNOSTIC AUDIT
    # ══════════════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1 — DIAGNOSTIC AUDIT")
    logger.info("=" * 60)

    audit: dict[str, Any] = {
        "class_distribution": {
            "train": _class_distribution(y_tr, "Train"),
            "val":   _class_distribution(y_va, "Val"),
            "test":  _class_distribution(y_te, "Test"),
        },
        "feature_analysis": _analyze_features(),
    }

    # ── Regressor bias check ──────────────────────────────────────────────────
    from app.ml.train import _REGRESSOR_PARAMS

    logger.info("Checking regressor bias …")
    home_reg = xgb.XGBRegressor(**_REGRESSOR_PARAMS)
    home_reg.fit(
        X_train_s, y_home_train.values,
        eval_set=[(X_val_s, y_home_val.values)],
        verbose=0,
    )
    away_reg = xgb.XGBRegressor(**_REGRESSOR_PARAMS)
    away_reg.fit(
        X_train_s, y_away_train.values,
        eval_set=[(X_val_s, y_away_val.values)],
        verbose=0,
    )

    home_preds = np.clip(home_reg.predict(X_test_s), 0, 10)
    away_preds = np.clip(away_reg.predict(X_test_s), 0, 10)

    audit["regressor_bias"] = {
        "home_mean_predicted": round(float(home_preds.mean()), 4),
        "home_mean_actual":    round(float(y_home_test.mean()), 4),
        "home_bias":           round(float(home_preds.mean() - y_home_test.mean()), 4),
        "away_mean_predicted": round(float(away_preds.mean()), 4),
        "away_mean_actual":    round(float(y_away_test.mean()), 4),
        "away_bias":           round(float(away_preds.mean() - y_away_test.mean()), 4),
    }
    logger.info("  Home regressor bias: %.4f", audit["regressor_bias"]["home_bias"])
    logger.info("  Away regressor bias: %.4f", audit["regressor_bias"]["away_bias"])

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2 — DRAW OPTIMIZATION EXPERIMENTS
    # ══════════════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2 — DRAW OPTIMIZATION EXPERIMENTS")
    logger.info("=" * 60)

    experiments: list[dict] = []

    # ── Variant 1: Baseline (no weighting) ────────────────────────────────────
    baseline_model = _train_variant(
        "Baseline", _CLASSIFIER_PARAMS,
        X_train_s, y_tr, X_val_s, y_va,
    )
    experiments.append(
        _evaluate_variant("Baseline", baseline_model, X_test_s, y_te)
    )

    # ── Variant 2: Class-weighted ─────────────────────────────────────────────
    sw = compute_sample_weights(y_tr)
    weighted_model = _train_variant(
        "Weighted", _CLASSIFIER_PARAMS,
        X_train_s, y_tr, X_val_s, y_va,
        sample_weight=sw,
    )
    experiments.append(
        _evaluate_variant("Weighted", weighted_model, X_test_s, y_te)
    )

    # ── Variant 3: Baseline + threshold tuning ────────────────────────────────
    base_val_proba = baseline_model.predict_proba(X_val_s)
    base_boost, _ = optimize_draw_threshold(y_va, base_val_proba)
    logger.info("  Baseline optimal draw_boost: %.3f", base_boost)
    experiments.append(
        _evaluate_variant(
            "Baseline + Threshold", baseline_model,
            X_test_s, y_te, draw_boost=base_boost,
        )
    )

    # ── Variant 4: Weighted + threshold tuning (Combined) ─────────────────────
    weighted_val_proba = weighted_model.predict_proba(X_val_s)
    combined_boost, _ = optimize_draw_threshold(y_va, weighted_val_proba)
    logger.info("  Combined optimal draw_boost: %.3f", combined_boost)
    experiments.append(
        _evaluate_variant(
            "Weighted + Threshold", weighted_model,
            X_test_s, y_te, draw_boost=combined_boost,
        )
    )

    # ── Select best variant ───────────────────────────────────────────────────
    def _composite(m: dict) -> float:
        return 0.50 * m["accuracy"] + 0.30 * m["draw_recall"] + 0.20 * m["draw_f1"]

    best = max(experiments, key=_composite)

    logger.info("\n" + "=" * 60)
    logger.info("BEST VARIANT: %s", best["name"])
    logger.info("  Accuracy:       %.4f", best["accuracy"])
    logger.info("  Draw Recall:    %.4f", best["draw_recall"])
    logger.info("  Draw Precision: %.4f", best["draw_precision"])
    logger.info("  Draw F1:        %.4f", best["draw_f1"])
    logger.info("=" * 60)

    # ── Home-win over-prediction check ────────────────────────────────────────
    base_preds = baseline_model.predict(X_test_s)
    pred_dist  = np.bincount(base_preds, minlength=3)
    actual_dist = np.bincount(y_te, minlength=3)

    audit["home_win_overprediction"] = {
        "predicted_home_win_pct": round(100.0 * pred_dist[2] / len(y_te), 2),
        "actual_home_win_pct":    round(100.0 * actual_dist[2] / len(y_te), 2),
        "overpredicts":           bool(pred_dist[2] > actual_dist[2] * 1.05),
        "predicted_draw_pct":     round(100.0 * pred_dist[1] / len(y_te), 2),
        "actual_draw_pct":        round(100.0 * actual_dist[1] / len(y_te), 2),
    }

    # ── Draw-recall analysis narrative ────────────────────────────────────────
    audit["draw_recall_analysis"] = (
        f"Baseline draw recall: {experiments[0]['draw_recall']:.4f}. "
        f"Best variant '{best['name']}' achieves draw recall: "
        f"{best['draw_recall']:.4f} (improvement: "
        f"{best['draw_recall'] - experiments[0]['draw_recall']:+.4f}). "
        f"Draws are {audit['class_distribution']['train']['Draw']['percentage']:.1f}% "
        f"of training data but the baseline classifier predicts them only "
        f"{audit['home_win_overprediction']['predicted_draw_pct']:.1f}% of the time "
        f"on the test set."
    )

    # ── Assemble report ───────────────────────────────────────────────────────
    use_weights = "Weighted" in best["name"]
    use_threshold = "Threshold" in best["name"]

    audit["experiment_results"] = experiments
    audit["best_configuration"] = {
        "variant":       best["name"],
        "use_weights":   use_weights,
        "use_threshold": use_threshold,
        "draw_boost":    best["draw_boost"],
        "test_metrics":  best,
    }

    # ── Save report ───────────────────────────────────────────────────────────
    report_path = Path(settings.MODEL_PATH).parent / "model_audit_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(audit, f, indent=2, default=str)

    logger.info("\nAudit report saved → %s", report_path)
    logger.info("Run  python -m app.ml.train  to retrain with optimised settings.")


if __name__ == "__main__":
    main()
