"""
FIFA AI — Probability Calibration
===================================

Post-hoc calibration of classifier probabilities to produce well-calibrated
match outcome probabilities.

Methods
-------
1. **Isotonic Regression**  — non-parametric, per-class calibration via
   ``sklearn.isotonic.IsotonicRegression``.
2. **Platt Scaling** — logistic sigmoid calibration via
   ``sklearn.calibration.CalibratedClassifierCV`` (method="sigmoid").

Evaluation
----------
- **Brier Score** — measures the mean squared error of probability estimates.
  Lower is better.  Perfect = 0.0, no skill = 0.25 (for 3-class).
- **Expected Calibration Error (ECE)** — measures the gap between predicted
  probabilities and empirical frequencies across probability bins.
  Lower is better.  Target: < 0.05.

Usage
-----
    # As a standalone benchmark:
    python -m app.ml.calibration

    # Utility functions imported by train.py:
    from app.ml.calibration import fit_calibrators, apply_calibration
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

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

_CLASS_NAMES = ["Away Win", "Draw", "Home Win"]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CalibrationResult:
    """Holds calibrators and evaluation metrics for one method."""
    method: str
    calibrators: list[IsotonicRegression]  # one per class
    brier_scores: dict[str, float] = field(default_factory=dict)
    ece: float = 0.0
    mean_brier: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# EXPECTED CALIBRATION ERROR
# ═══════════════════════════════════════════════════════════════════════════════

def expected_calibration_error(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 15,
) -> float:
    """
    Compute Expected Calibration Error (ECE) for multi-class predictions.

    For each class, bins predictions by confidence level and measures the
    gap between average predicted probability and actual frequency.

    Parameters
    ----------
    y_true  : Ground-truth labels (0/1/2).
    y_proba : Predicted probabilities, shape (n, 3).
    n_bins  : Number of calibration bins.

    Returns
    -------
    ECE as a float in [0, 1].
    """
    n_classes = y_proba.shape[1]
    n_samples = len(y_true)
    ece = 0.0

    for c in range(n_classes):
        y_binary = (y_true == c).astype(float)
        probs = y_proba[:, c]

        bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
        for b in range(n_bins):
            mask = (probs > bin_edges[b]) & (probs <= bin_edges[b + 1])
            n_in_bin = mask.sum()
            if n_in_bin == 0:
                continue
            avg_pred = probs[mask].mean()
            avg_true = y_binary[mask].mean()
            ece += (n_in_bin / n_samples) * abs(avg_pred - avg_true)

    # Average across classes
    return ece / n_classes


# ═══════════════════════════════════════════════════════════════════════════════
# ISOTONIC CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════

def _fit_isotonic(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> list[IsotonicRegression]:
    """
    Fit one IsotonicRegression calibrator per class.

    Each calibrator maps the raw predicted probability for class c
    to a calibrated probability.
    """
    n_classes = y_proba.shape[1]
    calibrators: list[IsotonicRegression] = []

    for c in range(n_classes):
        y_binary = (y_true == c).astype(float)
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso.fit(y_proba[:, c], y_binary)
        calibrators.append(iso)

    return calibrators


def _apply_isotonic(
    calibrators: list[IsotonicRegression],
    y_proba: np.ndarray,
) -> np.ndarray:
    """Apply per-class isotonic calibrators and re-normalise."""
    n_classes = y_proba.shape[1]
    calibrated = np.zeros_like(y_proba)

    for c in range(n_classes):
        calibrated[:, c] = calibrators[c].predict(y_proba[:, c])

    # Re-normalise so probabilities sum to 1
    row_sums = calibrated.sum(axis=1, keepdims=True)
    row_sums = np.maximum(row_sums, 1e-9)
    calibrated /= row_sums

    return calibrated


# ═══════════════════════════════════════════════════════════════════════════════
# PLATT SCALING (SIGMOID)
# ═══════════════════════════════════════════════════════════════════════════════

def _fit_platt(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> list[IsotonicRegression]:
    """
    Fit Platt-style sigmoid calibration, implemented as isotonic for simplicity
    (sklearn's sigmoid calibrator requires the underlying estimator).

    We use a logistic regression per class on the raw probabilities.
    """
    from sklearn.linear_model import LogisticRegression

    n_classes = y_proba.shape[1]
    calibrators: list[Any] = []

    for c in range(n_classes):
        y_binary = (y_true == c).astype(int)
        lr = LogisticRegression(C=1.0, max_iter=1000)
        lr.fit(y_proba[:, c].reshape(-1, 1), y_binary)
        calibrators.append(lr)

    return calibrators


def _apply_platt(
    calibrators: list,
    y_proba: np.ndarray,
) -> np.ndarray:
    """Apply per-class Platt (logistic) calibrators and re-normalise."""
    n_classes = y_proba.shape[1]
    calibrated = np.zeros_like(y_proba)

    for c in range(n_classes):
        calibrated[:, c] = calibrators[c].predict_proba(
            y_proba[:, c].reshape(-1, 1)
        )[:, 1]

    row_sums = calibrated.sum(axis=1, keepdims=True)
    row_sums = np.maximum(row_sums, 1e-9)
    calibrated /= row_sums

    return calibrated


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — imported by train.py
# ═══════════════════════════════════════════════════════════════════════════════

def fit_calibrators(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> Tuple[dict, str]:
    """
    Fit both calibration methods and select the best one.

    Parameters
    ----------
    y_true  : Validation labels (0/1/2).
    y_proba : Raw classifier probabilities on validation set, shape (n, 3).

    Returns
    -------
    calibration_bundle : Dict containing calibrators, method, and metrics.
    best_method        : Name of the best method ("isotonic" or "platt").
    """
    results: dict[str, Any] = {}

    # ── Isotonic ──────────────────────────────────────────────────────────────
    iso_cals = _fit_isotonic(y_true, y_proba)
    iso_proba = _apply_isotonic(iso_cals, y_proba)
    iso_brier = {}
    for c in range(3):
        y_binary = (y_true == c).astype(float)
        iso_brier[_CLASS_NAMES[c]] = round(
            float(brier_score_loss(y_binary, iso_proba[:, c])), 5
        )
    iso_ece = round(expected_calibration_error(y_true, iso_proba), 5)
    iso_mean_brier = round(float(np.mean(list(iso_brier.values()))), 5)

    results["isotonic"] = {
        "calibrators":  iso_cals,
        "brier_scores": iso_brier,
        "ece":          iso_ece,
        "mean_brier":   iso_mean_brier,
    }

    logger.info("Isotonic  → Mean Brier: %.5f  |  ECE: %.5f", iso_mean_brier, iso_ece)

    # ── Platt scaling ─────────────────────────────────────────────────────────
    platt_cals = _fit_platt(y_true, y_proba)
    platt_proba = _apply_platt(platt_cals, y_proba)
    platt_brier = {}
    for c in range(3):
        y_binary = (y_true == c).astype(float)
        platt_brier[_CLASS_NAMES[c]] = round(
            float(brier_score_loss(y_binary, platt_proba[:, c])), 5
        )
    platt_ece = round(expected_calibration_error(y_true, platt_proba), 5)
    platt_mean_brier = round(float(np.mean(list(platt_brier.values()))), 5)

    results["platt"] = {
        "calibrators":  platt_cals,
        "brier_scores": platt_brier,
        "ece":          platt_ece,
        "mean_brier":   platt_mean_brier,
    }

    logger.info("Platt     → Mean Brier: %.5f  |  ECE: %.5f", platt_mean_brier, platt_ece)

    # ── Raw (uncalibrated) baseline ───────────────────────────────────────────
    raw_brier = {}
    for c in range(3):
        y_binary = (y_true == c).astype(float)
        raw_brier[_CLASS_NAMES[c]] = round(
            float(brier_score_loss(y_binary, y_proba[:, c])), 5
        )
    raw_ece = round(expected_calibration_error(y_true, y_proba), 5)
    raw_mean_brier = round(float(np.mean(list(raw_brier.values()))), 5)

    results["raw"] = {
        "brier_scores": raw_brier,
        "ece":          raw_ece,
        "mean_brier":   raw_mean_brier,
    }

    logger.info("Raw       → Mean Brier: %.5f  |  ECE: %.5f", raw_mean_brier, raw_ece)

    # ── Select best ───────────────────────────────────────────────────────────
    # Best = lowest mean Brier score (with ECE as tiebreaker)
    candidates = {
        "isotonic": (iso_mean_brier, iso_ece),
        "platt":    (platt_mean_brier, platt_ece),
    }
    best_method = min(candidates, key=lambda k: candidates[k])
    logger.info("Selected calibration method: %s", best_method)

    calibration_bundle = {
        "method":       best_method,
        "calibrators":  results[best_method]["calibrators"],
        "metrics": {
            "isotonic": {
                "brier_scores": results["isotonic"]["brier_scores"],
                "ece":          results["isotonic"]["ece"],
                "mean_brier":   results["isotonic"]["mean_brier"],
            },
            "platt": {
                "brier_scores": results["platt"]["brier_scores"],
                "ece":          results["platt"]["ece"],
                "mean_brier":   results["platt"]["mean_brier"],
            },
            "raw": results["raw"],
        },
    }

    return calibration_bundle, best_method


def apply_calibration(
    calibration_bundle: dict,
    y_proba: np.ndarray,
) -> np.ndarray:
    """
    Apply the best calibration method to raw probabilities.

    Parameters
    ----------
    calibration_bundle : Dict from ``fit_calibrators()``.
    y_proba            : Raw classifier probabilities, shape (n, 3).

    Returns
    -------
    Calibrated probabilities, shape (n, 3), normalised to sum to 1.
    """
    method = calibration_bundle.get("method", "isotonic")
    calibrators = calibration_bundle.get("calibrators", [])

    if not calibrators:
        return y_proba

    if method == "isotonic":
        return _apply_isotonic(calibrators, y_proba)
    else:
        return _apply_platt(calibrators, y_proba)


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Run calibration benchmark as a standalone experiment."""
    from app.ml.train import (
        load_data,
        build_training_dataset,
        chronological_split,
    )
    from app.ml.draw_optimizer import compute_sample_weights

    logger.info("=" * 60)
    logger.info("FIFA AI — Probability Calibration Benchmark")
    logger.info("=" * 60)

    df = load_data()
    X, y_home, y_away, y_result = build_training_dataset(df)

    (
        X_train, X_val, X_test,
        (_, _, _),
        (_, _, _),
        (y_result_train, y_result_val, y_result_test),
    ) = chronological_split(X, y_home, y_away, y_result)

    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train.fillna(0.0))
    X_val_s   = scaler.transform(X_val.fillna(0.0))
    X_test_s  = scaler.transform(X_test.fillna(0.0))

    # Train classifier with class weighting
    from app.ml.train import _load_optimised_params

    _, clf_params, draw_weight_mult = _load_optimised_params()
    sample_weights = compute_sample_weights(y_result_train)
    if draw_weight_mult > 1.0:
        sample_weights[y_result_train == 1] *= draw_weight_mult

    clf = xgb.XGBClassifier(**clf_params)
    clf.fit(
        X_train_s, y_result_train,
        sample_weight=sample_weights,
        eval_set=[(X_val_s, y_result_val)],
        verbose=0,
    )

    # Calibrate on validation set
    val_proba = clf.predict_proba(X_val_s)
    bundle, best_method = fit_calibrators(y_result_val.values, val_proba)

    # Evaluate on test set
    test_proba = clf.predict_proba(X_test_s)
    calibrated_proba = apply_calibration(bundle, test_proba)

    logger.info("\n" + "=" * 60)
    logger.info("TEST SET EVALUATION")
    logger.info("=" * 60)

    # Raw test metrics
    raw_ece = expected_calibration_error(y_result_test.values, test_proba)
    cal_ece = expected_calibration_error(y_result_test.values, calibrated_proba)

    logger.info("  Raw ECE:         %.5f", raw_ece)
    logger.info("  Calibrated ECE:  %.5f  (%s)", cal_ece, best_method)
    logger.info("  Improvement:     %.5f", raw_ece - cal_ece)

    for c in range(3):
        y_binary = (y_result_test.values == c).astype(float)
        raw_bs = brier_score_loss(y_binary, test_proba[:, c])
        cal_bs = brier_score_loss(y_binary, calibrated_proba[:, c])
        logger.info(
            "  %10s  Brier: %.5f → %.5f  (Δ %.5f)",
            _CLASS_NAMES[c], raw_bs, cal_bs, raw_bs - cal_bs,
        )


if __name__ == "__main__":
    main()
