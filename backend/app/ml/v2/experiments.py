"""
Chronological ablation, dataset-configuration comparison, and the WC2026 backtest.

Everything here is evaluated on data the model has never seen, in strict time
order. Random splits are never used — a random split of football matches lets
the model learn from the future, which inflates every metric.

Runs, in order:

  1. ABLATION       five nested feature sets, each scored by walk-forward
                    validation over the modern tournaments.
  2. DATASET CONFIG the winning feature set trained on different eras, to test
                    whether pre-2002 football helps or hurts generalisation.
  3. WC2026_BACKTEST the winning configuration, trained on everything up to and
                    including 2022, predicting all 104 matches of 2026 with
                    accumulators frozen at the end of 2022.
  4. CURRENT_PRODUCTION the same configuration refit on the full corpus,
                    including 2026, for predicting future tournaments.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.experiments
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss,
                             classification_report, confusion_matrix, f1_score,
                             log_loss, mean_absolute_error, mean_squared_error,
                             precision_score, recall_score)
from xgboost import XGBClassifier, XGBRegressor

from app.ml.v2.features import (FEATURE_GROUPS, build_dataset, feature_columns,
                                load_canonical)

warnings.filterwarnings("ignore")

OUT_DIR = Path(__file__).resolve().parent / "artifacts"
CLASS_NAMES = {0: "away_win", 1: "draw", 2: "home_win"}

# Nested feature sets — each a strict superset of the previous, so any change in
# score is attributable to the group that was added.
EXPERIMENTS = {
    "E1_strength":            ("strength",),
    "E2_plus_form":           ("strength", "form"),
    "E3_plus_history":        ("strength", "form", "history"),
    "E4_plus_context":        ("strength", "form", "history", "context"),
    "E5_plus_rolling_stats":  ("strength", "form", "history", "context", "rolling_stats"),
}

# Walk-forward folds. Each entry is a tournament used as the unseen test set,
# with every earlier tournament as training data.
CV_TEST_YEARS = [1998, 2002, 2006, 2010, 2014, 2018, 2022]

CLF_PARAMS = dict(n_estimators=400, max_depth=4, learning_rate=0.05,
                  subsample=0.85, colsample_bytree=0.85, min_child_weight=4,
                  gamma=0.3, reg_alpha=0.05, reg_lambda=1.5,
                  objective="multi:softprob", num_class=3, eval_metric="mlogloss",
                  random_state=42, n_jobs=-1)
REG_PARAMS = dict(n_estimators=400, max_depth=4, learning_rate=0.05,
                  subsample=0.85, colsample_bytree=0.85, min_child_weight=4,
                  gamma=0.3, reg_alpha=0.05, reg_lambda=1.5,
                  objective="count:poisson", eval_metric="rmse",
                  random_state=42, n_jobs=-1)


# ---------------------------------------------------------------------------
def evaluate(y_true, proba, home_true, away_true, home_pred, away_pred) -> dict:
    y_pred = proba.argmax(axis=1)
    present = sorted(set(y_true) | set(y_pred))
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y_true)), y_true] = 1.0

    metrics = {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "log_loss": float(log_loss(y_true, proba, labels=[0, 1, 2])),
        "brier_multiclass": float(np.mean(np.sum((proba - onehot) ** 2, axis=1))),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "draw_recall": float(recall_score(y_true, y_pred, labels=[1], average="macro", zero_division=0)),
        "draw_precision": float(precision_score(y_true, y_pred, labels=[1], average="macro", zero_division=0)),
        "draw_f1": float(f1_score(y_true, y_pred, labels=[1], average="macro", zero_division=0)),
        "home_goals_mae": float(mean_absolute_error(home_true, home_pred)),
        "away_goals_mae": float(mean_absolute_error(away_true, away_pred)),
        "home_goals_rmse": float(np.sqrt(mean_squared_error(home_true, home_pred))),
        "away_goals_rmse": float(np.sqrt(mean_squared_error(away_true, away_pred))),
        "exact_score_accuracy": float(np.mean(
            (np.round(home_pred) == home_true) & (np.round(away_pred) == away_true))),
    }
    for cls, name in CLASS_NAMES.items():
        metrics[f"brier_{name}"] = float(brier_score_loss((y_true == cls).astype(int), proba[:, cls]))
    metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()
    return metrics


def calibration_table(y_true, proba, bins: int = 10) -> dict:
    """Reliability of the predicted-class probability, plus ECE."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y_true).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        acc, avg_conf = correct[mask].mean(), conf[mask].mean()
        ece += mask.mean() * abs(acc - avg_conf)
        rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mask.sum()),
                     "mean_confidence": round(float(avg_conf), 4),
                     "empirical_accuracy": round(float(acc), 4)})
    return {"bins": rows, "ece": round(float(ece), 4)}


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> tuple:
    Xtr, Xte = train[cols].to_numpy(np.float32), test[cols].to_numpy(np.float32)
    ytr = train["target_result"].to_numpy(int)

    clf = XGBClassifier(**CLF_PARAMS).fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)

    hr = XGBRegressor(**REG_PARAMS).fit(Xtr, train["home_goals"].to_numpy(np.float32))
    ar = XGBRegressor(**REG_PARAMS).fit(Xtr, train["away_goals"].to_numpy(np.float32))
    return proba, hr.predict(Xte), ar.predict(Xte), clf, hr, ar


def score_split(train, test, cols) -> dict:
    proba, hp, ap, *_ = fit_predict(train, test, cols)
    return evaluate(test["target_result"].to_numpy(int), proba,
                    test["home_goals"].to_numpy(), test["away_goals"].to_numpy(), hp, ap)


def walk_forward(df: pd.DataFrame, cols: list[str], test_years: list[int],
                 min_train: int = 120) -> dict:
    folds = []
    for year in test_years:
        train = df[(df["year"] < year) & df["target_result"].notna()]
        test = df[(df["year"] == year) & df["target_result"].notna()]
        if len(train) < min_train or len(test) == 0:
            continue
        m = score_split(train, test, cols)
        m.update({"test_year": year, "n_train": int(len(train))})
        folds.append(m)

    keys = ["accuracy", "balanced_accuracy", "log_loss", "brier_multiclass",
            "f1_macro", "draw_recall", "draw_f1", "home_goals_mae", "away_goals_mae"]
    summary = {f"mean_{k}": round(float(np.mean([f[k] for f in folds])), 4) for k in keys}
    summary.update({f"std_{k}": round(float(np.std([f[k] for f in folds])), 4)
                    for k in ("accuracy", "log_loss")})
    summary["n_folds"] = len(folds)
    return {"summary": summary, "folds": folds}


# ---------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matches, teams, stats = load_canonical()
    report: dict = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds")}

    # ---------------------------------------------------------- 1. ABLATION
    print("=" * 74)
    print("1. CHRONOLOGICAL ABLATION")
    print("=" * 74)
    ablation = {}
    datasets: dict[str, pd.DataFrame] = {}
    for name, groups in EXPERIMENTS.items():
        df = build_dataset(matches, teams, stats, groups=groups)
        datasets[name] = df
        cols = feature_columns(df)
        res = walk_forward(df, cols, CV_TEST_YEARS)
        res["n_features"] = len(cols)
        res["feature_groups"] = list(groups)
        ablation[name] = res
        s = res["summary"]
        print(f"{name:<24} feats={len(cols):>4}  acc={s['mean_accuracy']:.4f}"
              f" ±{s['std_accuracy']:.4f}  logloss={s['mean_log_loss']:.4f}"
              f"  brier={s['mean_brier_multiclass']:.4f}  drawF1={s['mean_draw_f1']:.4f}"
              f"  MAE={s['mean_home_goals_mae']:.3f}/{s['mean_away_goals_mae']:.3f}")
    report["ablation"] = ablation

    # Selection: lowest log loss (proper scoring rule — rewards calibrated
    # probabilities, not just argmax hits, which matters because this model's
    # output is probabilities).
    best_name = min(ablation, key=lambda k: ablation[k]["summary"]["mean_log_loss"])
    print(f"\n-> best feature set by mean log loss: {best_name}")
    report["best_feature_set"] = best_name

    # ------------------------------------------------ 2. DATASET CONFIG
    print()
    print("=" * 74)
    print("2. DATASET CONFIGURATION (training era)")
    print("=" * 74)
    best_df = datasets[best_name]
    best_cols = feature_columns(best_df)
    configs = {
        "all_1930_2022": lambda d: d[d["year"] < 2026],
        "modern_1990_2022": lambda d: d[(d["year"] >= 1990) & (d["year"] < 2026)],
        "modern_2002_2022": lambda d: d[(d["year"] >= 2002) & (d["year"] < 2026)],
    }
    ds_results = {}
    for cfg, fn in configs.items():
        sub = fn(best_df)
        years = [y for y in CV_TEST_YEARS if y in set(sub["year"])]
        res = walk_forward(sub, best_cols, years)
        ds_results[cfg] = res
        s = res["summary"]
        print(f"{cfg:<20} rows={len(sub):>5} folds={s['n_folds']}  acc={s['mean_accuracy']:.4f}"
              f"  logloss={s['mean_log_loss']:.4f}  brier={s['mean_brier_multiclass']:.4f}")
    report["dataset_configs"] = ds_results
    best_cfg = min(ds_results, key=lambda k: ds_results[k]["summary"]["mean_log_loss"])
    print(f"\n-> best training era by mean log loss: {best_cfg}")
    report["best_dataset_config"] = best_cfg

    # ------------------------------------------- 3. WC2026 BACKTEST
    print()
    print("=" * 74)
    print("3. WC2026_BACKTEST — 104 unseen matches")
    print("=" * 74)
    # Accumulators frozen at 2022: no 2026 result influences any 2026 feature.
    bt = build_dataset(matches, teams, stats,
                       groups=EXPERIMENTS[best_name], freeze_after_year=2022)
    bt_cols = feature_columns(bt)
    train = bt[(bt["year"] < 2026) & bt["target_result"].notna()]
    test = bt[(bt["year"] == 2026) & bt["target_result"].notna()]
    if best_cfg == "modern_1990_2022":
        train = train[train["year"] >= 1990]
    elif best_cfg == "modern_2002_2022":
        train = train[train["year"] >= 2002]

    proba, hp, ap, clf, hr, ar = fit_predict(train, test, bt_cols)
    y_true = test["target_result"].to_numpy(int)
    backtest = evaluate(y_true, proba, test["home_goals"].to_numpy(),
                        test["away_goals"].to_numpy(), hp, ap)
    backtest["n_train"] = int(len(train))
    backtest["calibration"] = calibration_table(y_true, proba)
    backtest["classification_report"] = classification_report(
        y_true, proba.argmax(axis=1), labels=[0, 1, 2],
        target_names=["away_win", "draw", "home_win"], zero_division=0, output_dict=True)

    print(f"train n={len(train)}  test n={len(test)}")
    print(f"accuracy            {backtest['accuracy']:.4f}")
    print(f"balanced accuracy   {backtest['balanced_accuracy']:.4f}")
    print(f"log loss            {backtest['log_loss']:.4f}")
    print(f"brier (multiclass)  {backtest['brier_multiclass']:.4f}")
    print(f"ECE                 {backtest['calibration']['ece']:.4f}")
    print(f"draw recall / F1    {backtest['draw_recall']:.4f} / {backtest['draw_f1']:.4f}")
    print(f"goal MAE home/away  {backtest['home_goals_mae']:.3f} / {backtest['away_goals_mae']:.3f}")
    print(f"exact scoreline     {backtest['exact_score_accuracy']:.4f}")

    preds = test[["match_id", "date", "year", "stage", "home_team", "away_team",
                  "home_goals", "away_goals"]].copy()
    preds["p_away_win"] = proba[:, 0].round(4)
    preds["p_draw"] = proba[:, 1].round(4)
    preds["p_home_win"] = proba[:, 2].round(4)
    preds["pred_home_goals"] = np.round(hp, 3)
    preds["pred_away_goals"] = np.round(ap, 3)
    preds["pred_result"] = [CLASS_NAMES[c] for c in proba.argmax(axis=1)]
    preds["actual_result"] = [CLASS_NAMES[c] for c in y_true]
    preds["correct"] = preds["pred_result"] == preds["actual_result"]
    preds["date"] = preds["date"].dt.strftime("%Y-%m-%d")
    preds.to_csv(OUT_DIR / "wc2026_backtest_predictions.csv", index=False)

    by_stage = preds.groupby("stage")["correct"].agg(["sum", "count"])
    backtest["accuracy_by_stage"] = {
        st: {"correct": int(r["sum"]), "n": int(r["count"]),
             "accuracy": round(float(r["sum"] / r["count"]), 4)}
        for st, r in by_stage.iterrows()}
    report["wc2026_backtest"] = backtest
    print("\naccuracy by stage:")
    for st, v in backtest["accuracy_by_stage"].items():
        print(f"   {st:<16} {v['correct']:>3}/{v['n']:<4} = {v['accuracy']:.3f}")

    # feature importance of the backtest model
    imp = sorted(zip(bt_cols, clf.feature_importances_), key=lambda x: -x[1])
    report["wc2026_backtest"]["top_features"] = [
        {"feature": f, "importance": round(float(v), 5)} for f, v in imp[:25]]
    print("\ntop 10 features:")
    for f, v in imp[:10]:
        print(f"   {f:<34} {v:.5f}")

    # --------------------------------------- 4. CURRENT_PRODUCTION
    print()
    print("=" * 74)
    print("4. CURRENT_PRODUCTION — refit on the full corpus incl. 2026")
    print("=" * 74)
    prod_df = build_dataset(matches, teams, stats, groups=EXPERIMENTS[best_name])
    prod_cols = feature_columns(prod_df)
    prod_train = prod_df[prod_df["target_result"].notna()]
    if best_cfg == "modern_1990_2022":
        prod_train = prod_train[prod_train["year"] >= 1990]
    elif best_cfg == "modern_2002_2022":
        prod_train = prod_train[prod_train["year"] >= 2002]

    Xp = prod_train[prod_cols].to_numpy(np.float32)
    yp = prod_train["target_result"].to_numpy(int)
    prod_clf = XGBClassifier(**CLF_PARAMS).fit(Xp, yp)
    prod_home = XGBRegressor(**REG_PARAMS).fit(Xp, prod_train["home_goals"].to_numpy(np.float32))
    prod_away = XGBRegressor(**REG_PARAMS).fit(Xp, prod_train["away_goals"].to_numpy(np.float32))

    import joblib
    joblib.dump({
        "mode": "CURRENT_PRODUCTION",
        "classifier": prod_clf, "home_regressor": prod_home, "away_regressor": prod_away,
        "feature_columns": prod_cols, "feature_groups": list(EXPERIMENTS[best_name]),
        "training_rows": int(len(prod_train)),
        "training_years": [int(prod_train["year"].min()), int(prod_train["year"].max())],
        "trained_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "notes": ("Trained on the full canonical corpus INCLUDING the completed 2026 "
                  "tournament. For predicting future tournaments only — its 2026 "
                  "predictions are in-sample and must never be quoted as accuracy."),
    }, OUT_DIR / "model_current_production.pkl", compress=3)

    report["current_production"] = {
        "training_rows": int(len(prod_train)),
        "training_years": [int(prod_train["year"].min()), int(prod_train["year"].max())],
        "n_features": len(prod_cols),
        "artifact": "model_current_production.pkl",
        "warning": "in-sample on 2026; never quote 2026 accuracy from this model",
    }
    print(f"trained on {len(prod_train)} matches "
          f"({prod_train['year'].min()}-{prod_train['year'].max()}), {len(prod_cols)} features")

    joblib.dump({
        "mode": "WC2026_BACKTEST", "classifier": clf,
        "home_regressor": hr, "away_regressor": ar,
        "feature_columns": bt_cols, "feature_groups": list(EXPERIMENTS[best_name]),
        "training_rows": int(len(train)), "frozen_after_year": 2022,
    }, OUT_DIR / "model_wc2026_backtest.pkl", compress=3)

    (OUT_DIR / "experiment_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nartifacts -> {OUT_DIR}")


if __name__ == "__main__":
    main()
