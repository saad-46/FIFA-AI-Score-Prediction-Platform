"""
V2 probability calibration — fitting, chronological evaluation, and selection.

THE PROBLEM
-----------
The uncalibrated V2 model is overconfident: predictions issued at ~0.95
confidence were correct about 67% of the time, ECE 0.135. Accuracy is fine;
the probabilities are not trustworthy. This module fixes the probabilities
without touching the feature set, the dataset, or the model architecture.

LEAKAGE DISCIPLINE
------------------
A calibrator fitted on predictions the base model was trained on will learn
that the model is *under*-confident, because training-set probabilities are
inflated. So calibrators here are fitted exclusively on OUT-OF-FOLD
predictions produced by walk-forward validation: for each tournament year Y,
a model trained only on matches before Y predicts Y. Every probability the
calibrator sees is therefore a genuine out-of-sample prediction.

WC2026 never enters calibration fitting under any path. It is the untouched
evaluation set, exactly as in the backtest.

METHODS
-------
    none         baseline passthrough
    platt        per-class logistic (sigmoid) then renormalise
    isotonic     per-class isotonic regression then renormalise
    temperature  single scalar T dividing the logits before softmax

Platt and isotonic follow the conventions already used by
``app/ml/calibration.py`` so V2 stays consistent with the project. Temperature
scaling is included because it is the canonical remedy for the specific failure
observed — uniform overconfidence — and it is the simplest method available:
one parameter, monotonic, and it cannot reorder predictions, so accuracy is
mathematically unchanged while probabilities are pulled toward reality.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.calibrate
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss,
                             classification_report, confusion_matrix, f1_score,
                             log_loss, mean_absolute_error, mean_squared_error,
                             precision_score, recall_score)
from xgboost import XGBClassifier, XGBRegressor

from app.ml.v2.calibrators import CALIBRATORS
from app.ml.v2.experiments import CLF_PARAMS, CV_TEST_YEARS, EXPERIMENTS, REG_PARAMS
from app.ml.v2.features import build_dataset, feature_columns, load_canonical

ART = Path(__file__).resolve().parent / "artifacts"
MODEL_VERSION = "v2-calibrated"
BASELINE_FEATURE_SET = "E4_plus_context"
BASE_TRAIN_MAX_YEAR = 2022
TEST_YEAR = 2026
SEED = 42
EPS = 1e-12
CLASS_NAMES = {0: "away_win", 1: "draw", 2: "home_win"}


# Calibrator implementations live in app.ml.v2.calibrators so that a saved
# bundle pickles them with a resolvable module path (a class defined in the
# module run as __main__ pickles as __main__.ClassName and fails to load
# from any other entry point).

# ------------------------------------------------------------------- metrics
def expected_calibration_error(y, proba, bins=10) -> float:
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def reliability_buckets(y, proba) -> list[dict]:
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    out = []
    for lo, hi in [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7),
                   (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]:
        m = (conf > lo) & (conf <= hi)
        if not m.sum():
            continue
        out.append({
            "bucket": f"{int(lo * 100)}-{int(hi * 100)}%",
            "n": int(m.sum()),
            "mean_confidence": round(float(conf[m].mean()), 4),
            "empirical_accuracy": round(float(correct[m].mean()), 4),
            "gap": round(float(conf[m].mean() - correct[m].mean()), 4),
        })
    return out


def full_metrics(y, proba, home_true=None, away_true=None,
                 home_pred=None, away_pred=None) -> dict:
    pred = proba.argmax(axis=1)
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y)), y] = 1.0
    m = {
        "n": int(len(y)),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y, pred)), 4),
        "precision_macro": round(float(precision_score(y, pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y, pred, average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y, pred, average="macro", zero_division=0)), 4),
        "log_loss": round(float(log_loss(y, proba, labels=[0, 1, 2])), 4),
        "brier_multiclass": round(float(np.mean(np.sum((proba - onehot) ** 2, axis=1))), 4),
        "ece": round(expected_calibration_error(y, proba), 4),
        "draw_recall": round(float(recall_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "draw_precision": round(float(precision_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "draw_f1": round(float(f1_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        "reliability": reliability_buckets(y, proba),
    }
    for c, name in CLASS_NAMES.items():
        m[f"brier_{name}"] = round(float(brier_score_loss((y == c).astype(int), proba[:, c])), 4)
    rep = classification_report(y, pred, labels=[0, 1, 2],
                                target_names=list(CLASS_NAMES.values()),
                                zero_division=0, output_dict=True)
    m["per_class"] = {k: {kk: round(float(vv), 4) for kk, vv in v.items()}
                      for k, v in rep.items() if k in CLASS_NAMES.values()}
    if home_pred is not None:
        m["home_goals_mae"] = round(float(mean_absolute_error(home_true, home_pred)), 4)
        m["away_goals_mae"] = round(float(mean_absolute_error(away_true, away_pred)), 4)
        m["home_goals_rmse"] = round(float(np.sqrt(mean_squared_error(home_true, home_pred))), 4)
        m["away_goals_rmse"] = round(float(np.sqrt(mean_squared_error(away_true, away_pred))), 4)
        m["exact_score_accuracy"] = round(float(np.mean(
            (np.round(home_pred) == home_true) & (np.round(away_pred) == away_true))), 4)
    # probability contract
    sums = proba.sum(axis=1)
    m["probability_contract"] = {
        "max_abs_deviation_from_1": float(np.max(np.abs(sums - 1.0))),
        "all_sum_to_one": bool(np.allclose(sums, 1.0, atol=1e-6)),
        "all_in_unit_interval": bool((proba >= 0).all() and (proba <= 1).all()),
    }
    return m


# --------------------------------------------------------------------- core
def train_base(train: pd.DataFrame, cols: list[str]):
    X = train[cols].to_numpy(np.float32)
    y = train["target_result"].to_numpy(int)
    clf = XGBClassifier(**CLF_PARAMS).fit(X, y)
    hr = XGBRegressor(**REG_PARAMS).fit(X, train["home_goals"].to_numpy(np.float32))
    ar = XGBRegressor(**REG_PARAMS).fit(X, train["away_goals"].to_numpy(np.float32))
    return clf, hr, ar


def out_of_fold(df: pd.DataFrame, cols: list[str], years: list[int],
                min_train: int = 120) -> pd.DataFrame:
    """Walk-forward OOF predictions. Every row was predicted by a model that
    had never seen it — the only honest basis for fitting a calibrator."""
    frames = []
    for year in years:
        tr = df[(df["year"] < year) & df["target_result"].notna()]
        te = df[(df["year"] == year) & df["target_result"].notna()]
        if len(tr) < min_train or te.empty:
            continue
        clf, _, _ = train_base(tr, cols)
        proba = clf.predict_proba(te[cols].to_numpy(np.float32))
        frames.append(pd.DataFrame({
            "year": year,
            "y": te["target_result"].to_numpy(int),
            "p0": proba[:, 0], "p1": proba[:, 1], "p2": proba[:, 2],
        }))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    matches, teams, stats = load_canonical()
    groups = EXPERIMENTS[BASELINE_FEATURE_SET]

    # ---- 1. FROZEN BASELINE ------------------------------------------------
    bt_df, _ = build_dataset(matches, teams, stats, groups=groups,
                             freeze_after_year=BASE_TRAIN_MAX_YEAR,
                             return_builder=True)
    cols = feature_columns(bt_df)
    train = bt_df[(bt_df["year"] <= BASE_TRAIN_MAX_YEAR) & bt_df["target_result"].notna()]
    test = bt_df[(bt_df["year"] == TEST_YEAR) & bt_df["target_result"].notna()]

    print("=" * 78)
    print("1. FROZEN V2 BASELINE")
    print("=" * 78)
    print(f"feature set   {BASELINE_FEATURE_SET}  ({len(cols)} features)")
    print(f"train         {len(train)} matches, {int(train['year'].min())}-{int(train['year'].max())}")
    print(f"test          {len(test)} matches, {TEST_YEAR}")

    clf, hr, ar = train_base(train, cols)
    Xte = test[cols].to_numpy(np.float32)
    raw_test_proba = clf.predict_proba(Xte)
    y_test = test["target_result"].to_numpy(int)
    hp, ap = hr.predict(Xte), ar.predict(Xte)

    baseline = full_metrics(y_test, raw_test_proba, test["home_goals"].to_numpy(),
                            test["away_goals"].to_numpy(), hp, ap)
    print(f"accuracy {baseline['accuracy']}  log_loss {baseline['log_loss']}  "
          f"brier {baseline['brier_multiclass']}  ECE {baseline['ece']}  "
          f"draw_recall {baseline['draw_recall']}")

    # ---- 2. OUT-OF-FOLD CALIBRATION DATA -----------------------------------
    print()
    print("=" * 78)
    print("2. OUT-OF-FOLD CALIBRATION SET (WC2026 excluded by construction)")
    print("=" * 78)
    oof = out_of_fold(bt_df, cols, CV_TEST_YEARS)
    assert TEST_YEAR not in set(oof["year"]), "WC2026 leaked into the calibration set"
    oof_proba = oof[["p0", "p1", "p2"]].to_numpy()
    oof_y = oof["y"].to_numpy(int)
    print(f"OOF rows {len(oof)} from years {sorted(oof['year'].unique().tolist())}")
    print(f"OOF uncalibrated: log_loss {log_loss(oof_y, oof_proba, labels=[0,1,2]):.4f}  "
          f"ECE {expected_calibration_error(oof_y, oof_proba):.4f}")

    # ---- 3. CHRONOLOGICAL EVALUATION ---------------------------------------
    # For fold Y the calibrator is fitted only on OOF rows from years < Y, so
    # calibration is never informed by the fold it is scored on.
    print()
    print("=" * 78)
    print("3. CHRONOLOGICAL CALIBRATION EVALUATION (fit on earlier folds only)")
    print("=" * 78)
    chrono: dict[str, dict] = {}
    fold_years = sorted(oof["year"].unique())
    for name, ctor in CALIBRATORS.items():
        per_fold = []
        for y_idx, year in enumerate(fold_years):
            if y_idx == 0:
                continue                       # nothing earlier to fit on
            prior = oof[oof["year"] < year]
            cur = oof[oof["year"] == year]
            cal = ctor().fit(prior[["p0", "p1", "p2"]].to_numpy(), prior["y"].to_numpy(int))
            p = cal.transform(cur[["p0", "p1", "p2"]].to_numpy())
            yy = cur["y"].to_numpy(int)
            per_fold.append({
                "year": int(year),
                "accuracy": float(accuracy_score(yy, p.argmax(axis=1))),
                "log_loss": float(log_loss(yy, p, labels=[0, 1, 2])),
                "brier": float(np.mean(np.sum((p - np.eye(3)[yy]) ** 2, axis=1))),
                "ece": expected_calibration_error(yy, p),
                "draw_recall": float(recall_score(yy, p.argmax(axis=1), labels=[1],
                                                  average="macro", zero_division=0)),
            })
        chrono[name] = {
            "folds": per_fold,
            "mean": {k: round(float(np.mean([f[k] for f in per_fold])), 4)
                     for k in ("accuracy", "log_loss", "brier", "ece", "draw_recall")},
        }
        m = chrono[name]["mean"]
        print(f"{name:<12} acc={m['accuracy']:.4f}  logloss={m['log_loss']:.4f}  "
              f"brier={m['brier']:.4f}  ECE={m['ece']:.4f}  drawR={m['draw_recall']:.4f}")

    # ---- 4. WC2026 BACKTEST PER METHOD -------------------------------------
    print()
    print("=" * 78)
    print("4. WC2026 BACKTEST — calibrators fitted on 1998-2022 OOF only")
    print("=" * 78)
    fitted: dict[str, object] = {}
    backtests: dict[str, dict] = {}
    for name, ctor in CALIBRATORS.items():
        cal = ctor().fit(oof_proba, oof_y)
        fitted[name] = cal
        p = cal.transform(raw_test_proba)
        backtests[name] = full_metrics(y_test, p, test["home_goals"].to_numpy(),
                                       test["away_goals"].to_numpy(), hp, ap)
        b = backtests[name]
        print(f"{name:<12} acc={b['accuracy']:.4f}  logloss={b['log_loss']:.4f}  "
              f"brier={b['brier_multiclass']:.4f}  ECE={b['ece']:.4f}  "
              f"drawR={b['draw_recall']:.4f}  params={cal.params}")

    # ---- 5. SELECTION ------------------------------------------------------
    # Ranked on chronological evidence (log loss, then Brier, then ECE) so the
    # choice is not made on the evaluation set itself. The WC2026 backtest is
    # then reported for the winner as a confirmation, not as the selector.
    ranked = sorted(chrono, key=lambda n: (chrono[n]["mean"]["log_loss"],
                                           chrono[n]["mean"]["brier"],
                                           chrono[n]["mean"]["ece"]))
    selected = ranked[0]
    base_ll = chrono["none"]["mean"]["log_loss"]
    sel_ll = chrono[selected]["mean"]["log_loss"]
    improved = sel_ll < base_ll - 1e-6
    if not improved:
        selected = "none"

    print()
    print("=" * 78)
    print(f"SELECTED: {selected}")
    print("=" * 78)
    print(f"chronological ranking: {ranked}")
    print(f"chronological log loss  none={base_ll:.4f}  selected={sel_ll:.4f}")

    # ---- 6. SAVE -----------------------------------------------------------
    cal_final = fitted[selected]
    bundle = {
        "model_version": MODEL_VERSION,
        "mode": "WC2026_BACKTEST",
        "classifier": clf,
        "home_regressor": hr,
        "away_regressor": ar,
        "calibrator": cal_final,
        "calibration_method": selected,
        "calibration_params": cal_final.params,
        "feature_columns": cols,
        "feature_groups": list(groups),
        "scaler": None,
        "notes": ("Feature values are fed to XGBoost unscaled — tree splits are "
                  "scale-invariant, so no scaler is fitted or required. "
                  "Calibrator fitted on 1998-2022 out-of-fold predictions only; "
                  "WC2026 never used for fitting."),
    }
    joblib.dump(bundle, ART / "model_v2_calibrated.pkl", compress=3)

    manifest = {
        "model_version": MODEL_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reproducibility": {
            "feature_set": BASELINE_FEATURE_SET,
            "feature_groups": list(groups),
            "n_features": len(cols),
            "feature_list_in_order": cols,
            "preprocessing": "none — no scaling; XGBoost tree splits are scale-invariant",
            "scaler": None,
            "missing_values": "left as NaN; XGBoost learns default split directions",
            "classifier_params": CLF_PARAMS,
            "regressor_params": REG_PARAMS,
            "random_seed": SEED,
            "training_period": f"1930-{BASE_TRAIN_MAX_YEAR}",
            "calibration_period": f"out-of-fold {min(fold_years)}-{max(fold_years)}",
            "test_period": str(TEST_YEAR),
            "accumulators_frozen_after": BASE_TRAIN_MAX_YEAR,
            "n_train": int(len(train)),
            "n_calibration_oof": int(len(oof)),
            "n_test": int(len(test)),
        },
        "calibration": {
            "selected_method": selected,
            "selection_rule": "lowest chronological mean log loss, then Brier, then ECE",
            "selected_params": cal_final.params,
            "chronological_ranking": ranked,
            "improved_over_baseline": bool(improved),
        },
        "baseline_metrics_wc2026": baseline,
        "chronological_evaluation": chrono,
        "wc2026_backtest_by_method": backtests,
        "previously_reported": {
            "wc2026_result_accuracy": 0.6058,
            "walk_forward_cv_mean_accuracy": 0.4978,
            "note": "preserved from the pre-calibration phase; not overwritten",
        },
        "leakage_assertions": {
            "wc2026_in_calibration_set": False,
            "calibrators_fitted_on_out_of_fold_only": True,
            "chronological_folds_fit_on_earlier_years_only": True,
        },
    }
    (ART / "calibration_report.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # side-by-side prediction file for the selected method
    p_sel = cal_final.transform(raw_test_proba)
    out = test[["match_id", "date", "stage", "home_team", "away_team",
                "home_goals", "away_goals"]].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    for i, nm in CLASS_NAMES.items():
        out[f"raw_p_{nm}"] = raw_test_proba[:, i].round(4)
        out[f"cal_p_{nm}"] = p_sel[:, i].round(4)
    out["predicted_home_score"] = np.round(hp, 3)
    out["predicted_away_score"] = np.round(ap, 3)
    out["confidence"] = p_sel.max(axis=1).round(4)
    out["predicted_result"] = [CLASS_NAMES[c] for c in p_sel.argmax(axis=1)]
    out["actual_result"] = [CLASS_NAMES[c] for c in y_test]
    out["correct"] = out["predicted_result"] == out["actual_result"]
    out.to_csv(ART / "wc2026_calibrated_predictions.csv", index=False)

    print(f"\nartifacts -> {ART}")
    print("  model_v2_calibrated.pkl")
    print("  calibration_report.json")
    print("  wc2026_calibrated_predictions.csv")


if __name__ == "__main__":
    main()
