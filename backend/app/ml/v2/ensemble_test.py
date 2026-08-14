"""
Ensemble test (Phase 13) — only kept if it beats the standalone model on the
same historical walk-forward.

Candidate: blend the XGBoost classifier's probabilities with a simple,
independent Elo-only heuristic (logistic win-probability from the Elo gap
alone, the same functional form the Elo update itself already uses — so it's
not a new, untested formula, just repurposing the Elo model's own implied
probabilities as a second, much simpler "model"). The Poisson score
distribution is already part of every prediction downstream (poisson.py) and
isn't a separate classifier to ensemble here.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.ensemble_test
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.features import build_dataset, feature_columns, load_canonical
from app.ml.v2.historical import (HISTORICAL_YEARS, composite_objective, full_metrics,
                                  _train)
from app.ml.v2.registry import log_experiment

ELO_HOME_ADV = 65.0


def elo_probabilities(row: pd.Series) -> np.ndarray:
    """The same logistic-Elo win model used for the Elo rating update itself,
    with the draw probability handled the same way Poisson-based blending in
    the rest of the system already does: split the "not a clean win" mass
    based on how close the sides are (closer Elo -> more draw mass)."""
    diff = row["elo_diff"]
    if pd.isna(diff):
        return np.array([1 / 3, 1 / 3, 1 / 3])
    p_home_beats_away = 1.0 / (1.0 + 10 ** (-diff / 400.0))
    closeness = 1.0 - min(abs(diff) / 400.0, 1.0)  # 1.0 when level, 0 when far apart
    draw_mass = 0.20 + 0.15 * closeness             # 20-35% draw mass, more when close
    home = p_home_beats_away * (1 - draw_mass)
    away = (1 - p_home_beats_away) * (1 - draw_mass)
    return np.array([away, draw_mass, home])


def evaluate_blend(groups: tuple[str, ...], weight_xgb: float,
                   clf_params: dict = CLF_PARAMS, reg_params: dict = REG_PARAMS) -> dict:
    matches, teams, stats = load_canonical()
    per_fold = []
    for year in HISTORICAL_YEARS:
        df, _ = build_dataset(matches, teams, stats, groups=groups,
                              freeze_after_year=year - 1, return_builder=True)
        cols = feature_columns(df)
        train = df[(df["year"] < year) & df["target_result"].notna()]
        test = df[(df["year"] == year) & df["target_result"].notna()]
        clf, hr, ar = _train(train, cols, clf_params, reg_params)
        Xte = test[cols].to_numpy(np.float32)
        xgb_proba = clf.predict_proba(Xte)
        elo_proba = np.array([elo_probabilities(row) for _, row in test.iterrows()])
        blended = weight_xgb * xgb_proba + (1 - weight_xgb) * elo_proba
        blended = blended / blended.sum(axis=1, keepdims=True)

        y_true = test["target_result"].to_numpy(int)
        hp, ap = hr.predict(Xte), ar.predict(Xte)
        m = full_metrics(y_true, blended, test["home_goals"].to_numpy(),
                         test["away_goals"].to_numpy(), hp, ap)
        m["composite_objective"] = round(composite_objective(m), 5)
        per_fold.append(m)

    keys = ["accuracy", "log_loss", "brier_multiclass", "ece", "draw_f1",
           "home_goals_mae", "away_goals_mae", "composite_objective"]
    return {k: round(float(np.mean([f[k] for f in per_fold])), 4) for k in keys}


#: Best hyperparameters found in Phase 7 (EXP-007) — the current accepted
#: best configuration this test builds on, not the original defaults, per
#: "test one meaningful change at a time" building on prior accepted changes.
TUNED_PARAMS = {"max_depth": 3, "learning_rate": 0.03328934350873081, "n_estimators": 200,
                "min_child_weight": 3, "subsample": 0.6950873836384747,
                "colsample_bytree": 0.860456436297428, "reg_alpha": 0.2586762826070334,
                "reg_lambda": 1.2456180155061534}


def main() -> None:
    from app.ml.v2.registry import list_experiments
    hp_experiments = list_experiments("hyperparameters")
    accepted_hp = [e for e in hp_experiments if e["accepted"]]
    baseline_composite = accepted_hp[-1]["composite_objective"] if accepted_hp else \
        list_experiments("baseline")[-1]["composite_objective"]
    groups = ("strength", "form", "history", "context")
    clf_params = dict(CLF_PARAMS); clf_params.update(TUNED_PARAMS)
    reg_params = dict(REG_PARAMS); reg_params.update(TUNED_PARAMS)

    print("Testing XGBoost(tuned) + Elo-heuristic ensemble at several blend weights...")
    print(f"(current best composite, EXP-007 = {baseline_composite:.5f})\n")

    results = {}
    for w in (1.0, 0.9, 0.8, 0.7, 0.5):
        agg = evaluate_blend(groups, weight_xgb=w, clf_params=clf_params, reg_params=reg_params)
        results[w] = agg
        tag = "= pure XGBoost (sanity check)" if w == 1.0 else ""
        print(f"  weight_xgb={w:.1f}  composite={agg['composite_objective']:.5f}  "
              f"acc={agg['accuracy']:.4f}  logloss={agg['log_loss']:.4f}  {tag}")

    best_w = min(results, key=lambda w: results[w]["composite_objective"])
    best = results[best_w]
    accepted = (baseline_composite - best["composite_objective"]) > 0.005 and best_w < 1.0

    record = log_experiment(
        category="ensemble",
        description="XGBoost(tuned, EXP-007 hyperparameters) classifier probabilities "
                    "blended with an independent Elo-only logistic win model (Elo gap "
                    "-> win probability via the same formula the Elo update itself "
                    "uses; draw mass scaled by closeness). Tested at blend "
                    "weights 1.0 (pure tuned XGBoost, sanity check), 0.9, 0.8, 0.7, 0.5.",
        change={"blend_weights_tested": list(results.keys()), "best_weight_xgb": best_w,
               "all_results": results},
        training_range="1930 - (year-1) per fold",
        validation_range=f"{HISTORICAL_YEARS} (WC2026 excluded)",
        aggregate_metrics=best,
        composite_objective=best["composite_objective"],
        baseline_composite_objective=baseline_composite,
        accepted=accepted,
        reason=(f"blending at weight_xgb={best_w} improved composite by "
               f"{baseline_composite - best['composite_objective']:.5f}"
               if accepted else
               "no blend weight beat pure XGBoost by more than the 0.005 threshold "
               "— the ensemble does not earn its added complexity; kept XGBoost alone."),
    )
    print(f"\n{record['id']}  best blend weight_xgb={best_w}  -> "
         f"{'ACCEPTED' if accepted else 'rejected'}: {record['reason']}")


if __name__ == "__main__":
    main()
