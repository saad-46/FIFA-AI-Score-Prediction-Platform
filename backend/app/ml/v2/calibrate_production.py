"""
CURRENT_PRODUCTION model: training + independent calibration + validation.

Two distinct artifacts exist and must never be conflated:

    v2_backtest_calibrated    trained 1930-2022, accumulators frozen at 2022,
                              T = 2.472. Answers "what would the model have
                              predicted for WC2026?" NOT TOUCHED by this module.

    v2_production_calibrated  trained on the full canonical corpus through
                              2026, accumulators running normally. Answers
                              "predict a future match using everything known
                              today." Built here, with its own calibration
                              fitted from scratch.

WHY THE TEMPERATURE IS REFIT RATHER THAN COPIED
-----------------------------------------------
T = 2.472 was fitted to the *backtest* model's out-of-fold predictions. The
production model sees 104 extra matches and, more importantly, runs its feature
accumulators through 2026 rather than freezing them — so its logit distribution
is not the same object. Reusing 2.472 would be an assumption dressed up as a
result. It is instead included as an explicit candidate (``temperature_frozen``)
so the report can show whether refitting actually mattered.

FEATURE ACCUMULATOR SEMANTICS
-----------------------------
The backtest freezes accumulators at 2022 so that no 2026 match learns from an
earlier 2026 match — that is what "predicting the tournament in advance" means.
Production has the opposite requirement: when predicting tomorrow's match you
legitimately know yesterday's result. So production builds features with normal
chronological accumulation (``freeze_after_year=None``). This is not a
loosening of leakage discipline: ``features.py`` emits a match's row from
accumulator state *before* folding that match in, so a match still never sees
itself or its own future.

LEAKAGE DISCIPLINE FOR CALIBRATION
----------------------------------
Calibrators are fitted only on walk-forward out-of-fold predictions: for each
tournament year Y, a model trained strictly on matches before Y predicts Y.
Method selection uses the chronological mean across folds, where each fold's
calibrator is fitted only on *earlier* folds. WC2026 is one fold among eight
and never the selector — selecting on it would be tuning toward a known result.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.calibrate_production
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, recall_score

from app.ml.v2.calibrate import (
    CLASS_NAMES, expected_calibration_error, full_metrics, out_of_fold, train_base,
)
from app.ml.v2.calibrators import CALIBRATORS, FrozenTemperature
from app.ml.v2.experiments import CV_TEST_YEARS, CLF_PARAMS, EXPERIMENTS, REG_PARAMS
from app.ml.v2.features import build_dataset, feature_columns, load_canonical

ART = Path(__file__).resolve().parent / "artifacts"
MODEL_VERSION = "v2-production-calibrated"
FEATURE_SET = "E4_plus_context"
SEED = 42

# 2026 joins the walk-forward folds for the production model. It is the most
# recent tournament and a legitimate out-of-fold observation; it is NOT the
# selection criterion (see module docstring).
PRODUCTION_CV_YEARS = CV_TEST_YEARS + [2026]

BACKTEST_TEMPERATURE = FrozenTemperature.DEFAULT_T

# FrozenTemperature (the backtest model's T applied without refitting) is a
# control: it lets the report state whether refitting actually changed
# anything, rather than assuming either way. It is defined in
# app.ml.v2.calibrators, not here, so the saved bundle pickles it with a
# resolvable module path.
PRODUCTION_CALIBRATORS = dict(CALIBRATORS)
PRODUCTION_CALIBRATORS["temperature_frozen"] = FrozenTemperature


def chronological_evaluation(oof: pd.DataFrame) -> dict:
    """Fold Y scored with a calibrator fitted only on folds earlier than Y."""
    results: dict[str, dict] = {}
    fold_years = sorted(oof["year"].unique())

    for name, ctor in PRODUCTION_CALIBRATORS.items():
        per_fold = []
        for idx, year in enumerate(fold_years):
            if idx == 0:
                continue                       # no earlier data to fit on
            prior = oof[oof["year"] < year]
            cur = oof[oof["year"] == year]
            cal = ctor().fit(prior[["p0", "p1", "p2"]].to_numpy(), prior["y"].to_numpy(int))
            p = cal.transform(cur[["p0", "p1", "p2"]].to_numpy())
            yy = cur["y"].to_numpy(int)
            per_fold.append({
                "year": int(year),
                "n": int(len(cur)),
                "accuracy": round(float(accuracy_score(yy, p.argmax(axis=1))), 4),
                "log_loss": round(float(log_loss(yy, p, labels=[0, 1, 2])), 4),
                "brier": round(float(np.mean(np.sum((p - np.eye(3)[yy]) ** 2, axis=1))), 4),
                "ece": round(expected_calibration_error(yy, p), 4),
                "draw_recall": round(float(recall_score(yy, p.argmax(axis=1), labels=[1],
                                                        average="macro", zero_division=0)), 4),
            })
        keys = ("accuracy", "log_loss", "brier", "ece", "draw_recall")
        results[name] = {
            "folds": per_fold,
            "mean": {k: round(float(np.mean([f[k] for f in per_fold])), 4) for k in keys},
            # Stability: a method that wins on average but swings wildly between
            # tournaments is worse for production than a slightly worse, steadier one.
            "std": {k: round(float(np.std([f[k] for f in per_fold])), 4)
                    for k in ("log_loss", "ece")},
        }
    return results


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    matches, teams, stats = load_canonical()
    groups = EXPERIMENTS[FEATURE_SET]

    # ---- production feature frame: accumulators run through 2026 -----------
    prod_df, builder = build_dataset(matches, teams, stats, groups=groups,
                                     freeze_after_year=None, return_builder=True)
    cols = feature_columns(prod_df)
    labelled = prod_df[prod_df["target_result"].notna()]

    print("=" * 78)
    print("1. PRODUCTION MODEL")
    print("=" * 78)
    print(f"feature set  {FEATURE_SET} ({len(cols)} features)")
    print(f"training     {len(labelled)} matches, "
          f"{int(labelled['year'].min())}-{int(labelled['year'].max())}")
    print("accumulators running (not frozen) — production semantics")

    # ---- out-of-fold predictions for calibration ---------------------------
    print()
    print("=" * 78)
    print("2. OUT-OF-FOLD CALIBRATION DATA (walk-forward, 2026 included as a fold)")
    print("=" * 78)
    oof = out_of_fold(prod_df, cols, PRODUCTION_CV_YEARS)
    oof_proba = oof[["p0", "p1", "p2"]].to_numpy()
    oof_y = oof["y"].to_numpy(int)
    print(f"OOF rows {len(oof)} from years {sorted(oof['year'].unique().tolist())}")
    print(f"OOF uncalibrated: log_loss {log_loss(oof_y, oof_proba, labels=[0,1,2]):.4f}  "
          f"ECE {expected_calibration_error(oof_y, oof_proba):.4f}")

    # ---- chronological method comparison -----------------------------------
    print()
    print("=" * 78)
    print("3. CHRONOLOGICAL CALIBRATION COMPARISON (fit on earlier folds only)")
    print("=" * 78)
    chrono = chronological_evaluation(oof)
    for name, res in chrono.items():
        m, s = res["mean"], res["std"]
        print(f"{name:<20} acc={m['accuracy']:.4f}  logloss={m['log_loss']:.4f}"
              f" (sd {s['log_loss']:.4f})  brier={m['brier']:.4f}"
              f"  ECE={m['ece']:.4f} (sd {s['ece']:.4f})  drawR={m['draw_recall']:.4f}")

    ranked = sorted(chrono, key=lambda n: (chrono[n]["mean"]["log_loss"],
                                           chrono[n]["mean"]["brier"],
                                           chrono[n]["mean"]["ece"]))
    selected = ranked[0]
    if chrono[selected]["mean"]["log_loss"] >= chrono["none"]["mean"]["log_loss"] - 1e-6:
        selected = "none"
    print(f"\nranking: {ranked}")
    print(f"SELECTED: {selected}")

    # ---- fit the production calibrator on all OOF --------------------------
    cal_final = PRODUCTION_CALIBRATORS[selected]().fit(oof_proba, oof_y)
    print(f"production calibrator params: {cal_final.params}")

    # ---- train the final production model on everything --------------------
    clf, hr, ar = train_base(labelled, cols)

    # ---- validation on genuinely unseen chronological holdouts -------------
    # Each fold below was predicted by a model that never saw it, with a
    # calibrator fitted only on earlier folds — so these are honest numbers
    # for the production *configuration*, not for the final all-data fit
    # (which by definition has no unseen data left).
    print()
    print("=" * 78)
    print("4. PRODUCTION VALIDATION — per-fold, unseen")
    print("=" * 78)
    validation = {}
    fold_years = sorted(oof["year"].unique())
    for idx, year in enumerate(fold_years):
        if idx == 0:
            continue
        prior = oof[oof["year"] < year]
        cur = oof[oof["year"] == year]
        cal = PRODUCTION_CALIBRATORS[selected]().fit(
            prior[["p0", "p1", "p2"]].to_numpy(), prior["y"].to_numpy(int))
        p = cal.transform(cur[["p0", "p1", "p2"]].to_numpy())
        yy = cur["y"].to_numpy(int)
        year_rows = labelled[labelled["year"] == year]
        Xy = year_rows[cols].to_numpy(np.float32)
        tr = labelled[labelled["year"] < year]
        _, hr_f, ar_f = train_base(tr, cols) if len(tr) > 120 else (None, hr, ar)
        hp, ap = hr_f.predict(Xy), ar_f.predict(Xy)
        validation[str(year)] = full_metrics(
            yy, p, year_rows["home_goals"].to_numpy(), year_rows["away_goals"].to_numpy(), hp, ap)
        v = validation[str(year)]
        print(f"  {year}  n={v['n']:>3}  acc={v['accuracy']:.4f}  bal={v['balanced_accuracy']:.4f}"
              f"  ll={v['log_loss']:.4f}  brier={v['brier_multiclass']:.4f}  ECE={v['ece']:.4f}"
              f"  drawR={v['draw_recall']:.4f}  MAE={v['home_goals_mae']:.3f}/{v['away_goals_mae']:.3f}")

    agg_keys = ("accuracy", "balanced_accuracy", "log_loss", "brier_multiclass", "ece",
                "precision_macro", "recall_macro", "f1_macro", "draw_recall",
                "home_goals_mae", "away_goals_mae", "home_goals_rmse", "away_goals_rmse")
    aggregate = {f"mean_{k}": round(float(np.mean([v[k] for v in validation.values()])), 4)
                 for k in agg_keys}
    print("\n  AGGREGATE across unseen folds:")
    for k, v in aggregate.items():
        print(f"     {k:<28}{v}")

    # ---- save --------------------------------------------------------------
    bundle = {
        "model_version": MODEL_VERSION,
        "mode": "CURRENT_PRODUCTION",
        "classifier": clf,
        "home_regressor": hr,
        "away_regressor": ar,
        "calibrator": cal_final,
        "calibration_method": selected,
        "calibration_params": cal_final.params,
        "feature_columns": cols,
        "feature_groups": list(groups),
        "scaler": None,
        "notes": (
            "Trained on the full canonical corpus through 2026 with feature "
            "accumulators running (not frozen). For predicting FUTURE matches. "
            "Its 2026 predictions are in-sample and must never be quoted as "
            "accuracy — use v2_backtest_calibrated for that. Calibrator fitted "
            "on walk-forward out-of-fold predictions only."
        ),
    }
    joblib.dump(bundle, ART / "model_v2_production_calibrated.pkl", compress=3)

    report = {
        "model_version": MODEL_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reproducibility": {
            "feature_set": FEATURE_SET,
            "n_features": len(cols),
            "feature_list_in_order": cols,
            "preprocessing": "none — XGBoost tree splits are scale-invariant",
            "accumulators_frozen_after": None,
            "classifier_params": CLF_PARAMS,
            "regressor_params": REG_PARAMS,
            "random_seed": SEED,
            "training_period": f"{int(labelled['year'].min())}-{int(labelled['year'].max())}",
            "training_rows": int(len(labelled)),
            "calibration_period": f"out-of-fold {min(fold_years)}-{max(fold_years)}",
            "calibration_rows": int(len(oof)),
        },
        "calibration": {
            "selected_method": selected,
            "selected_params": cal_final.params,
            "selection_rule": "lowest chronological mean log loss, then Brier, then ECE",
            "ranking": ranked,
            "backtest_temperature_for_reference": BACKTEST_TEMPERATURE,
            "refit_changed_temperature": (
                cal_final.params.get("temperature") != BACKTEST_TEMPERATURE
                if "temperature" in cal_final.params else None
            ),
        },
        "chronological_comparison": chrono,
        "validation_per_fold": validation,
        "validation_aggregate": aggregate,
        "leakage_assertions": {
            "calibrators_fitted_on_out_of_fold_only": True,
            "selection_used_chronological_mean_not_wc2026": True,
            "features_emitted_before_match_folded_into_accumulators": True,
        },
    }
    (ART / "production_calibration_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nartifacts -> {ART}")
    print("  model_v2_production_calibrated.pkl")
    print("  production_calibration_report.json")


if __name__ == "__main__":
    main()
