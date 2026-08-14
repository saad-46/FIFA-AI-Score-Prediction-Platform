"""
Final model selection, recalibration, and freeze (Phase 14-16).

Builds the Phase-15 comparison table from everything logged in the
registry, selects the best configuration by walk-forward generalization
(never WC2026), recalibrates it FRESH — explicitly not assuming the T=2.472
found for the original backtest model still applies, since a different
feature/hyperparameter configuration changes the model's own confidence
distribution — and freezes the result under a new version identifier.

If nothing in the registry beats the baseline by the accept threshold, this
freezes the ORIGINAL baseline configuration under the new version label
rather than inventing an improvement. That is a legitimate, expected outcome
per the task's own success criterion ("If it does not improve, keep the
current V2 model").

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.finalize_historical
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

from app.ml.v2.calibrators import CALIBRATORS
from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.features import build_dataset, feature_columns, load_canonical
from app.ml.v2.historical import (HISTORICAL_YEARS, composite_objective, full_metrics,
                                  _train, expected_calibration_error)
from app.ml.v2.registry import list_experiments, log_experiment

ART = Path(__file__).resolve().parent / "artifacts"
BASELINE_GROUPS = ("strength", "form", "history", "context")
FINAL_VERSION = "v2.1.0-historical-optimized"


def build_comparison_table() -> tuple[list[dict], dict]:
    """Phase 15 table: every accepted candidate plus the baseline."""
    entries = list_experiments()
    baseline = next(e for e in entries if e["category"] == "baseline")
    accepted = [e for e in entries if e["accepted"] and e["category"] != "baseline"]

    rows = [{
        "label": "Current V2 (baseline)", "id": baseline["id"],
        "accuracy": baseline["aggregate_metrics"]["accuracy"],
        "log_loss": baseline["aggregate_metrics"]["log_loss"],
        "brier": baseline["aggregate_metrics"]["brier_multiclass"],
        "ece": baseline["aggregate_metrics"]["ece"],
        "draw_recall": baseline["aggregate_metrics"]["draw_recall"],
        "score_mae": round((baseline["aggregate_metrics"]["home_goals_mae"]
                           + baseline["aggregate_metrics"]["away_goals_mae"]) / 2, 4),
        "composite": baseline["composite_objective"],
    }]
    for e in accepted:
        rows.append({
            "label": f"{e['id']} ({e['category']})", "id": e["id"],
            "accuracy": e["aggregate_metrics"].get("accuracy"),
            "log_loss": e["aggregate_metrics"].get("log_loss"),
            "brier": e["aggregate_metrics"].get("brier_multiclass"),
            "ece": e["aggregate_metrics"].get("ece"),
            "draw_recall": e["aggregate_metrics"].get("draw_recall"),
            "score_mae": round((e["aggregate_metrics"].get("home_goals_mae", 0)
                               + e["aggregate_metrics"].get("away_goals_mae", 0)) / 2, 4)
                       if e["aggregate_metrics"].get("home_goals_mae") is not None else None,
            "composite": e["composite_objective"],
        })

    best = min(rows, key=lambda r: r["composite"])
    return rows, {"baseline": baseline, "accepted_experiments": accepted, "best_row": best}


def out_of_fold_1998_2022(groups: tuple[str, ...], clf_params: dict, reg_params: dict) -> pd.DataFrame:
    """Same walk-forward OOF construction as calibrate.py/calibrate_production.py,
    extended down to 1998 (the earliest fold with enough training data) so the
    freshly-calibrated final model has as much genuine out-of-sample evidence
    as the earlier calibration passes did. WC2026 is never included."""
    matches, teams, stats = load_canonical()
    years = [1998] + HISTORICAL_YEARS
    frames = []
    for year in years:
        df, _ = build_dataset(matches, teams, stats, groups=groups,
                              freeze_after_year=year - 1, return_builder=True)
        cols = feature_columns(df)
        train = df[(df["year"] < year) & df["target_result"].notna()]
        test = df[(df["year"] == year) & df["target_result"].notna()]
        if len(train) < 60 or test.empty:
            continue
        clf, _, _ = _train(train, cols, clf_params, reg_params)
        proba = clf.predict_proba(test[cols].to_numpy(np.float32))
        frames.append(pd.DataFrame({"year": year, "y": test["target_result"].to_numpy(int),
                                    "p0": proba[:, 0], "p1": proba[:, 1], "p2": proba[:, 2]}))
    return pd.concat(frames, ignore_index=True)


def recalibrate(groups: tuple[str, ...], clf_params: dict, reg_params: dict) -> dict:
    """Fresh calibration comparison — none/platt/isotonic/temperature — for
    whatever the final selected configuration is. T=2.472 is NOT assumed;
    it is only one candidate among equals here, tested like any other."""
    oof = out_of_fold_1998_2022(groups, clf_params, reg_params)
    oof_proba = oof[["p0", "p1", "p2"]].to_numpy()
    oof_y = oof["y"].to_numpy(int)
    fold_years = sorted(oof["year"].unique())

    chrono = {}
    for name, ctor in CALIBRATORS.items():
        per_fold = []
        for i, year in enumerate(fold_years):
            if i == 0:
                continue
            prior = oof[oof["year"] < year]
            cur = oof[oof["year"] == year]
            cal = ctor().fit(prior[["p0", "p1", "p2"]].to_numpy(), prior["y"].to_numpy(int))
            p = cal.transform(cur[["p0", "p1", "p2"]].to_numpy())
            yy = cur["y"].to_numpy(int)
            onehot = np.eye(3)[yy]
            per_fold.append({
                "log_loss": float(log_loss(yy, p, labels=[0, 1, 2])),
                "brier": float(np.mean(np.sum((p - onehot) ** 2, axis=1))),
                "ece": expected_calibration_error(yy, p),
            })
        chrono[name] = {k: round(float(np.mean([f[k] for f in per_fold])), 4)
                        for k in ("log_loss", "brier", "ece")}

    selected = min(chrono, key=lambda n: (chrono[n]["log_loss"], chrono[n]["brier"], chrono[n]["ece"]))
    final_cal = CALIBRATORS[selected]().fit(oof_proba, oof_y)
    return {"chronological_comparison": chrono, "selected_method": selected,
           "selected_params": final_cal.params, "calibrator": final_cal,
           "oof_rows": len(oof), "oof_years": fold_years}


def main() -> None:
    rows, meta = build_comparison_table()
    print("=" * 100)
    print("PHASE 15 — FINAL COMPARISON TABLE (walk-forward generalization, WC2026 excluded)")
    print("=" * 100)
    print(f"{'Model':<32}{'Acc':>8}{'LogLoss':>10}{'Brier':>8}{'ECE':>8}{'DrawR':>8}{'ScoreMAE':>10}{'Composite':>11}")
    for r in rows:
        print(f"{r['label']:<32}{r['accuracy']:>8}{r['log_loss']:>10}{r['brier']:>8}"
             f"{r['ece']:>8}{r['draw_recall']:>8}{r['score_mae']:>10}{r['composite']:>11}")

    best = meta["best_row"]
    baseline = meta["baseline"]
    is_baseline_best = best["id"] == baseline["id"]

    print()
    if is_baseline_best:
        print("RESULT: no experiment beat the baseline by the acceptance threshold.")
        print("Per the success criterion — 'if it does not improve, keep the current "
             "V2 model' — the FINAL configuration is the ORIGINAL baseline features "
             "and hyperparameters. This is a legitimate outcome, not a failure to find one.")
        final_groups = BASELINE_GROUPS
        final_clf_params = dict(CLF_PARAMS)
        final_reg_params = dict(REG_PARAMS)
        selection_note = "No accepted experiment beat the baseline; baseline configuration frozen as-is."
    else:
        print(f"RESULT: best configuration is {best['id']} — freezing its configuration.")
        winning_exp = next(e for e in list_experiments() if e["id"] == best["id"])
        final_groups = tuple(winning_exp["change"].get("feature_groups", BASELINE_GROUPS))

        # IMPORTANT: best_params from a hyperparameter-search experiment only
        # contains the ~8 TUNED keys (max_depth, learning_rate, n_estimators,
        # min_child_weight, subsample, colsample_bytree, reg_alpha,
        # reg_lambda) — not the fixed base keys every trial during the search
        # also carried (gamma, objective, num_class, eval_metric, random_state,
        # n_jobs). Reconstructing from best_params ALONE would silently drop
        # those and let XGBoost guess objective/num_class, which is not what
        # was actually validated. Overlaying onto a full copy of the base
        # params reproduces EXACTLY what every trial during the search itself
        # trained with (see hyperparam_search.py's objective()).
        final_clf_params = dict(CLF_PARAMS)
        final_reg_params = dict(REG_PARAMS)
        if winning_exp["category"] == "hyperparameters":
            tuned = winning_exp["change"].get("best_params", {})
            final_clf_params.update(tuned)
            final_reg_params.update(tuned)
        selection_note = f"Selected {best['id']} — beat baseline by {baseline['composite_objective'] - best['composite']:.5f} composite."

    print()
    print("=" * 100)
    print("PHASE 14 — FRESH RECALIBRATION (T=2.472 not assumed)")
    print("=" * 100)
    cal = recalibrate(final_groups, final_clf_params, final_reg_params)
    for name, m in cal["chronological_comparison"].items():
        marker = "  <- selected" if name == cal["selected_method"] else ""
        print(f"  {name:<14} log_loss={m['log_loss']:.4f}  brier={m['brier']:.4f}  ece={m['ece']:.4f}{marker}")
    print(f"\nSelected: {cal['selected_method']}  params={cal['selected_params']}")

    # ---- freeze ----
    matches, teams, stats = load_canonical()
    full_df, builder = build_dataset(matches, teams, stats, groups=final_groups,
                                     freeze_after_year=None, return_builder=True)
    cols = feature_columns(full_df)
    train_all = full_df[full_df["target_result"].notna()]
    clf, hr, ar = _train(train_all, cols, final_clf_params, final_reg_params)

    bundle = {
        "model_version": FINAL_VERSION,
        "mode": "CURRENT_PRODUCTION",
        "classifier": clf, "home_regressor": hr, "away_regressor": ar,
        "calibrator": cal["calibrator"], "calibration_method": cal["selected_method"],
        "calibration_params": cal["selected_params"],
        "feature_columns": cols, "feature_groups": list(final_groups),
        "hyperparameters": {"classifier": final_clf_params, "regressor": final_reg_params},
        "training_rows": int(len(train_all)),
        "training_period": "1930-2026 (includes completed WC2026 — for future predictions)",
        "historical_selection": {
            "selection_note": selection_note,
            "comparison_table": rows,
            "accepted_experiment_ids": [e["id"] for e in meta["accepted_experiments"]],
        },
        "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "notes": ("Frozen per the historical-optimization phase. Feature list, "
                 "hyperparameters, and calibration are all fixed as of this freeze; "
                 "this bundle must not be silently retrained or re-tuned — a new "
                 "version identifier is required for any future change."),
    }
    path = ART / "model_v2_historical_optimized.pkl"
    joblib.dump(bundle, path, compress=3)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"\nFROZEN: {FINAL_VERSION}")
    print(f"  artifact: {path}")
    print(f"  sha256: {sha}")

    def _json_default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    (ART / "final_selection_report.json").write_text(json.dumps({
        "comparison_table": rows, "selection_note": selection_note,
        "final_version": FINAL_VERSION, "final_groups": list(final_groups),
        "final_clf_params": final_clf_params, "final_reg_params": final_reg_params,
        "calibration": {k: v for k, v in cal.items() if k != "calibrator"},
        "artifact_sha256": sha,
    }, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    print(f"  report: {ART / 'final_selection_report.json'}")


if __name__ == "__main__":
    main()
