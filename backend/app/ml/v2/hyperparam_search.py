"""
Controlled hyperparameter search (Phase 7).

Uses the existing XGBoost architecture (two Poisson-objective regressors +
one softprob classifier) — the task says to keep it "unless evidence shows
it is inadequate", and nothing in the historical simulation or the prior
ablation phase suggested the architecture itself is the bottleneck (form
features hurting, small-sample noise, and draw difficulty all point at data/
feature issues, not model-family issues).

Search space stays intentionally modest — a few dozen trials via Optuna's
TPE sampler, evaluated on the SAME six-tournament chronological walk-forward
used by every other experiment in this phase, never WC2026. Small search
space + a fixed random seed + logging every trial to the registry keeps this
from becoming exactly the "run hundreds of experiments and keep the highest
historical accuracy" over-fitting trap the task explicitly warns against —
the objective being optimized is the same composite score (Phase 9), not
raw accuracy, and only the single best trial is logged as an "experiment"
(the others are recorded in the trial log for transparency but don't each
get their own registry entry).

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.hyperparam_search [--groups ...] [--trials 30]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import optuna
from optuna.samplers import TPESampler

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.historical import HISTORICAL_YEARS, run_historical_simulation
from app.ml.v2.registry import log_experiment

ART = Path(__file__).resolve().parent / "artifacts"
N_TRIALS_DEFAULT = 30
SEED = 42


def _params_from_trial(trial: optuna.Trial, base: dict) -> dict:
    p = dict(base)
    p["max_depth"] = trial.suggest_int("max_depth", 3, 6)
    p["learning_rate"] = trial.suggest_float("learning_rate", 0.02, 0.12, log=True)
    p["n_estimators"] = trial.suggest_int("n_estimators", 150, 600, step=50)
    p["min_child_weight"] = trial.suggest_int("min_child_weight", 2, 10)
    p["subsample"] = trial.suggest_float("subsample", 0.6, 1.0)
    p["colsample_bytree"] = trial.suggest_float("colsample_bytree", 0.6, 1.0)
    p["reg_alpha"] = trial.suggest_float("reg_alpha", 0.0, 0.5)
    p["reg_lambda"] = trial.suggest_float("reg_lambda", 0.5, 3.0)
    return p


def run_search(groups: tuple[str, ...], n_trials: int = N_TRIALS_DEFAULT,
               baseline_composite: float | None = None) -> dict:
    from app.ml.v2.historical import composite_objective
    from app.ml.v2.registry import list_experiments

    if baseline_composite is None:
        baselines = list_experiments("baseline")
        if not baselines:
            raise RuntimeError("no baseline in registry — run run_baseline.py first")
        baseline_composite = baselines[-1]["composite_objective"]

    trial_log = []

    def objective(trial: optuna.Trial) -> float:
        clf_params = _params_from_trial(trial, CLF_PARAMS)
        # Share the same sampled tree-shape params between classifier and
        # regressors (both are XGBoost with the same rough capacity needs
        # for ~500-1000 training rows) rather than doubling the search space.
        reg_params = dict(REG_PARAMS)
        for k in ("max_depth", "learning_rate", "n_estimators", "min_child_weight",
                 "subsample", "colsample_bytree", "reg_alpha", "reg_lambda"):
            reg_params[k] = clf_params[k]

        result = run_historical_simulation(groups, clf_params, reg_params, light=True)
        composite = result["aggregate"]["mean"]["composite_objective"]
        trial_log.append({"trial": trial.number, "params": {k: clf_params[k] for k in
                          ("max_depth", "learning_rate", "n_estimators", "min_child_weight",
                           "subsample", "colsample_bytree", "reg_alpha", "reg_lambda")},
                          "composite_objective": composite,
                          "aggregate_metrics": result["aggregate"]["mean"]})
        return composite

    study = optuna.create_study(direction="minimize", sampler=TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_trial = min(trial_log, key=lambda t: t["composite_objective"])
    best_composite = best_trial["composite_objective"]
    accepted = (baseline_composite - best_composite) > 0.005

    record = log_experiment(
        category="hyperparameters",
        description=f"Optuna TPE search, {n_trials} trials, over max_depth/"
                    f"learning_rate/n_estimators/min_child_weight/subsample/"
                    f"colsample_bytree/reg_alpha/reg_lambda, shared between the "
                    f"classifier and both regressors. Best trial #{best_trial['trial']}.",
        change={"best_params": best_trial["params"], "n_trials": n_trials,
               "feature_groups": list(groups)},
        training_range="1930 - (year-1) per fold",
        validation_range=f"{HISTORICAL_YEARS} (WC2026 excluded)",
        aggregate_metrics=best_trial["aggregate_metrics"],
        composite_objective=best_composite,
        baseline_composite_objective=baseline_composite,
        accepted=accepted,
        reason=(f"composite improved by {baseline_composite - best_composite:.5f}"
               if accepted else
               f"composite change {baseline_composite - best_composite:+.5f} did not "
               f"clear the 0.005 threshold"),
    )

    (ART / "hyperparam_search_trials.json").write_text(
        json.dumps({"trials": trial_log, "best": best_trial, "experiment_id": record["id"]},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{record['id']}  best trial #{best_trial['trial']}  composite={best_composite:.5f} "
          f"(baseline={baseline_composite:.5f}, delta={record['delta_vs_baseline']:+.5f}) "
          f"-> {'ACCEPTED' if accepted else 'rejected'}")
    print(f"best params: {best_trial['params']}")
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", nargs="+", default=["strength", "form", "history", "context"])
    ap.add_argument("--trials", type=int, default=N_TRIALS_DEFAULT)
    args = ap.parse_args()
    run_search(tuple(args.groups), n_trials=args.trials)


if __name__ == "__main__":
    main()
