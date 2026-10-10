"""
Benchmark suite: rating hyper-parameter search, the candidate comparison, the
calibration comparison and the selection rule.

Run with ``python -m app.ml.v3.train benchmark``. Everything it decides is
decided on development folds; the 2026 fold is scored once, at the end, for the
candidates already chosen.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from app.ml.v3 import backtest as bt
from app.ml.v3.calibration import CALIBRATORS
from app.ml.v3.features import build_training_frame
from app.ml.v3.models import (EloOrderedLogit, MultinomialLogit, PoissonDixonColes, PriorModel,
                              XGBGoals, XGBOutcome, blend, encode_y, fit_simplex_weights)
from app.ml.v3.ratings import EloConfig

# Folds used to tune the rating engine. 2022-2025 is held back from this search
# so it stays a cleaner development check; 2026 is never used for any choice.
RATING_TUNE_FOLDS = bt.DEV_FOLDS[:3]


def _mean_ll(frame: pd.DataFrame, model_factory, folds) -> float:
    lls = []
    for fold in folds:
        train, val, test = bt.split(frame, fold)
        m = model_factory().fit(pd.concat([train, val]), None)
        lls.append(bt.log_loss(m.predict_proba(test), encode_y(test)))
    return float(np.mean(lls))


def tune_rating_config(matches: pd.DataFrame, log=print) -> tuple[EloConfig, list[dict]]:
    """
    Two-stage coordinate search. Stage 1 picks the Elo parameters by the Elo
    model's own out-of-sample log loss; stage 2 picks the attack/defence step
    size and form half-life by the Poisson model's. Small grids on purpose: this
    is a handful of interpretable knobs, not a black-box search.
    """
    trials: list[dict] = []
    base = EloConfig()

    best, best_ll = base, np.inf
    for k, h, mg in itertools.product((0.6, 0.8, 1.0, 1.25), (60.0, 80.0, 100.0, 120.0), (True, False)):
        cfg = replace(base, k_scale=k, home_advantage=h, use_margin=mg)
        frame, _ = build_training_frame(matches, cfg)
        ll = _mean_ll(frame, EloOrderedLogit, RATING_TUNE_FOLDS)
        trials.append({"stage": "elo", "k_scale": k, "home_advantage": h, "use_margin": mg, "mean_log_loss": round(ll, 5)})
        if ll < best_ll - 1e-6:
            best, best_ll = cfg, ll
    log(f"  elo stage best: k_scale={best.k_scale} home={best.home_advantage} margin={best.use_margin} ll={best_ll:.5f}")

    best2, best2_ll = best, np.inf
    for lr, hl in itertools.product((0.015, 0.03, 0.05, 0.08), (5.0, 8.0, 12.0)):
        cfg = replace(best, ad_lr=lr, form_halflife=hl)
        frame, _ = build_training_frame(matches, cfg)
        ll = _mean_ll(frame, PoissonDixonColes, RATING_TUNE_FOLDS)
        trials.append({"stage": "attack_defence", "ad_lr": lr, "form_halflife": hl, "mean_log_loss": round(ll, 5)})
        if ll < best2_ll - 1e-6:
            best2, best2_ll = cfg, ll
    log(f"  attack/defence stage best: ad_lr={best2.ad_lr} form_halflife={best2.form_halflife} ll={best2_ll:.5f}")
    return best2, trials


XGB_GRID = (
    dict(max_depth=2, min_child_weight=20, learning_rate=0.05),
    dict(max_depth=3, min_child_weight=20, learning_rate=0.05),
    dict(max_depth=3, min_child_weight=60, learning_rate=0.03),
    dict(max_depth=4, min_child_weight=40, learning_rate=0.03),
)


def _fit_fold(frame: pd.DataFrame, fold: bt.Fold, xgb_params: dict | None, seed: int = 42) -> dict[str, Any]:
    """Fit every candidate on one fold; return raw predictions on val_cal and test."""
    train, val, test = bt.split(frame, fold)
    mid = val["date"].quantile(0.5)
    val_es, val_cal = val[val["date"] <= mid], val[val["date"] > mid]

    models = {
        "prior": PriorModel().fit(train),
        "elo_ordered_logit": EloOrderedLogit().fit(train),
        "poisson": PoissonDixonColes(use_dc=False).fit(train),
        "poisson_dc": PoissonDixonColes(use_dc=True).fit(train),
        "multinomial_logit": MultinomialLogit().fit(train),
    }
    xgb_trials = []
    if xgb_params is None:
        best, best_ll = None, np.inf
        for params in XGB_GRID:
            m = XGBOutcome(seed=seed, **params).fit(train, val_es)
            ll = bt.log_loss(m.predict_proba(val_es), encode_y(val_es))
            xgb_trials.append({**params, "best_iteration": m.best_iteration, "val_log_loss": round(ll, 5)})
            if ll < best_ll:
                best, best_ll = m, ll
        models["xgboost"] = best
    else:
        models["xgboost"] = XGBOutcome(seed=seed, **xgb_params).fit(train, val_es)
    goals_xgb = XGBGoals(seed=seed).fit(train, val_es)

    return {
        "fold": fold, "train": train, "val_cal": val_cal, "test": test,
        "models": models, "goals_xgb": goals_xgb, "xgb_trials": xgb_trials,
        "p_cal": {k: m.predict_proba(val_cal) for k, m in models.items()},
        "p_test": {k: m.predict_proba(test) for k, m in models.items()},
        "y_cal": encode_y(val_cal), "y_test": encode_y(test),
    }


ENSEMBLES = {
    "ens_elo+poisson": ("elo_ordered_logit", "poisson_dc"),
    "ens_poisson+xgb": ("poisson_dc", "xgboost"),
    "ens_poisson+mlr+xgb": ("poisson_dc", "multinomial_logit", "xgboost"),
}


def evaluate_fold(fit: dict[str, Any]) -> dict[str, Any]:
    test, y_test, y_cal = fit["test"], fit["y_test"], fit["y_cal"]
    actual_goals = (test["goals_a"].to_numpy(), test["goals_b"].to_numpy())
    out: dict[str, Any] = {"fold": fit["fold"].name, "n_train": len(fit["train"]), "n_cal": len(fit["val_cal"]),
                           "n_test": len(test), "models": {}, "calibration": {}, "ensembles": {},
                           "xgb_trials": fit["xgb_trials"]}

    cal_probs: dict[str, np.ndarray] = {}      # temperature-calibrated test probs, by candidate
    for name, p_test in fit["p_test"].items():
        m = fit["models"][name]
        goals = m.predict_goals(test)
        raw = bt.score(p_test, y_test, goals, actual_goals if goals is not None else None)
        cals = {}
        for cname, C in CALIBRATORS.items():
            c = C().fit(fit["p_cal"][name], y_cal)
            p = c.transform(p_test)
            cals[cname] = {**bt.score(p, y_test), "params": c.describe()}
            if cname == "temperature":
                cal_probs[name] = p
        out["models"][name] = raw
        out["calibration"][name] = cals

    g = fit["goals_xgb"].predict_goals(test)
    err = np.concatenate([g[0] - actual_goals[0], g[1] - actual_goals[1]])
    out["xgb_goal_mae"] = round(float(np.abs(err).mean()), 4)
    out["xgb_goal_rmse"] = round(float(np.sqrt((err ** 2).mean())), 4)
    naive = float(np.concatenate([fit["train"]["goals_a"], fit["train"]["goals_b"]]).mean())
    out["naive_goal_mae"] = round(float(np.abs(np.concatenate(actual_goals) - naive).mean()), 4)

    for ename, members in ENSEMBLES.items():
        pc = [fit["p_cal"][m] for m in members]
        pt = [fit["p_test"][m] for m in members]
        for mode in ("equal", "fitted"):
            w = np.full(len(members), 1 / len(members)) if mode == "equal" else fit_simplex_weights(pc, y_cal)
            c = CALIBRATORS["temperature"]().fit(blend(pc, w), y_cal)
            p = c.transform(blend(pt, w))
            key = f"{ename}[{mode}]"
            out["ensembles"][key] = {**bt.score(p, y_test), "weights": {m: round(float(x), 3) for m, x in zip(members, w)},
                                     "params": c.describe()}
            cal_probs[key] = p

    ref = cal_probs["prior"]
    out["vs_prior"] = {k: bt.bootstrap_diff(p, ref, y_test) for k, p in cal_probs.items() if k != "prior"}
    ref2 = cal_probs["elo_ordered_logit"]
    out["vs_elo"] = {k: bt.bootstrap_diff(p, ref2, y_test) for k, p in cal_probs.items()
                     if k not in ("prior", "elo_ordered_logit")}
    out["_cal_probs"] = cal_probs
    return out


def run_benchmark(frame: pd.DataFrame, log=print) -> dict[str, Any]:
    t0 = time.time()
    dev = []
    for fold in bt.DEV_FOLDS:
        fit = _fit_fold(frame, fold, xgb_params=None)
        ev = evaluate_fold(fit)
        ev.pop("_cal_probs")
        dev.append(ev)
        log(f"  dev fold {fold.name}: n_test={ev['n_test']}  " + "  ".join(
            f"{k}={v['temperature']['log_loss']:.4f}" for k, v in ev["calibration"].items()))

    # ---- selection on development folds only --------------------------------
    cands: dict[str, list[float]] = {}
    for ev in dev:
        for k, v in ev["calibration"].items():
            cands.setdefault(k, []).append(v["temperature"]["log_loss"])
        for k, v in ev["ensembles"].items():
            cands.setdefault(k, []).append(v["log_loss"])
    dev_mean = {k: round(float(np.mean(v)), 5) for k, v in cands.items()}

    cal_choice: dict[str, list[float]] = {c: [] for c in CALIBRATORS}
    for ev in dev:
        for c in CALIBRATORS:
            cal_choice[c].append(np.mean([ev["calibration"][m][c]["log_loss"] for m in ev["calibration"] if m != "prior"]))
    cal_mean = {c: round(float(np.mean(v)), 5) for c, v in cal_choice.items()}

    # xgboost hyper-parameters: the grid point chosen most often across dev folds
    picks = [min(ev["xgb_trials"], key=lambda t: t["val_log_loss"]) for ev in dev]
    key = lambda t: (t["max_depth"], t["min_child_weight"], t["learning_rate"])
    counts: dict[tuple, int] = {}
    for t in picks:
        counts[key(t)] = counts.get(key(t), 0) + 1
    chosen = max(counts, key=counts.get)
    xgb_params = dict(max_depth=chosen[0], min_child_weight=chosen[1], learning_rate=chosen[2])

    log(f"  dev mean log loss: " + "  ".join(f"{k}={v}" for k, v in sorted(dev_mean.items(), key=lambda x: x[1])))
    return {"dev_folds": dev, "dev_mean_log_loss": dev_mean, "calibration_dev_mean_log_loss": cal_mean,
            "xgb_params_selected": xgb_params, "seconds": round(time.time() - t0, 1)}


# Complexity order used to break near-ties in favour of the simpler model.
SIMPLICITY = ["elo_ordered_logit", "poisson_dc", "poisson", "multinomial_logit", "ens_elo+poisson[equal]",
              "ens_elo+poisson[fitted]", "xgboost", "ens_poisson+xgb[equal]", "ens_poisson+xgb[fitted]",
              "ens_poisson+mlr+xgb[equal]", "ens_poisson+mlr+xgb[fitted]"]
TIE_MARGIN = 0.001   # log-loss difference below which two candidates are treated as equal


def select(dev_mean: dict[str, float]) -> dict[str, Any]:
    """Best mean development log loss; within TIE_MARGIN of it, the simplest wins."""
    eligible = {k: v for k, v in dev_mean.items() if k != "prior"}
    best = min(eligible.values())
    tied = [k for k, v in eligible.items() if v - best <= TIE_MARGIN]
    winner = min(tied, key=lambda k: SIMPLICITY.index(k) if k in SIMPLICITY else 99)
    return {"selected": winner, "best_dev_log_loss": best, "within_tie_margin": sorted(tied),
            "tie_margin": TIE_MARGIN,
            "rule": "lowest mean dev-fold log loss after temperature scaling; candidates within the tie "
                    "margin are treated as equal and the simplest is chosen"}
