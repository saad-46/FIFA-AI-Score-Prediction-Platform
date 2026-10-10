"""
The selected forecaster as one object: train it, save it, load it, ask it.

    Forecaster = Poisson/Dixon-Coles  (+)  XGBoost  ->  equal-weight blend  ->  temperature

chosen by ``benchmark.select`` on development folds (see BENCHMARK_V3.md). The
blend supplies the win/draw/loss probabilities; the Dixon-Coles model supplies
the scoreline distribution. So that the two never disagree, the scoreline matrix
is rescaled region by region (A wins / draw / B wins) to carry exactly the
blended outcome probabilities -- the shape within each region stays the Poisson
model's.

A penalty shoot-out model is fitted alongside: P(A wins the shoot-out) as a
logistic function of the Elo difference, with no intercept so it is symmetric.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit

from app.ml.v3.calibration import Temperature
from app.ml.v3.features import FEATURE_NAMES, SCHEMA_VERSION, feature_matrix, mirror
from app.ml.v3.models import (MAX_GOALS, PoissonDixonColes, XGBOutcome, blend, encode_y, normalise,
                              score_matrix)

BLEND_WEIGHTS = (0.5, 0.5)          # poisson_dc, xgboost -- fixed, not fitted
CALIBRATION_YEARS = 4


@dataclass
class Forecaster:
    poisson: PoissonDixonColes
    xgb: XGBOutcome
    calibrator: Temperature
    pens_beta: float = 0.0
    pens_n: int = 0
    feature_names: tuple[str, ...] = FEATURE_NAMES
    schema_version: str = SCHEMA_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    # ── probabilities ───────────────────────────────────────────────────────
    def raw_components(self, frame: pd.DataFrame) -> list[np.ndarray]:
        return [self.poisson.predict_proba(frame), self.xgb.predict_proba(frame)]

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        self._check(frame)
        return self.calibrator.transform(blend(self.raw_components(frame), np.array(BLEND_WEIGHTS)))

    def predict_goals(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return self.poisson.predict_goals(frame)

    def _check(self, frame: pd.DataFrame) -> None:
        if tuple(self.feature_names) != tuple(FEATURE_NAMES):
            raise RuntimeError("model was trained with a different feature schema than this code builds")
        X = feature_matrix(frame)
        if not np.isfinite(X.to_numpy()).all():
            raise ValueError("non-finite feature values")

    # ── scorelines ──────────────────────────────────────────────────────────
    def score_matrices(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(matrices [n, G, G], outcome probs [n, 3], lambda_a, lambda_b)."""
        p = self.predict_proba(frame)
        la, lb = self.predict_goals(frame)
        n = MAX_GOALS + 1
        lower = np.tril(np.ones((n, n), dtype=bool), -1)   # i > j : A wins
        upper = np.triu(np.ones((n, n), dtype=bool), 1)
        diag = np.eye(n, dtype=bool)
        out = np.empty((len(frame), n, n))
        for k in range(len(frame)):
            m = score_matrix(float(la[k]), float(lb[k]), self.poisson.rho)
            for mask, target in ((lower, p[k, 0]), (diag, p[k, 1]), (upper, p[k, 2])):
                mass = m[mask].sum()
                if mass > 0:
                    m[mask] *= target / mass
            out[k] = m / m.sum()
        return out, p, la, lb

    def p_shootout(self, elo_diff: np.ndarray | float) -> np.ndarray | float:
        return expit(self.pens_beta * np.asarray(elo_diff, dtype=float) / 400.0)


def fit_shootout_model(frame: pd.DataFrame) -> tuple[float, int, dict]:
    """
    P(first-listed team wins the shoot-out) = sigmoid(beta * elo_diff / 400).
    Venue is deliberately left out: by the time of a shoot-out there is no
    evidence here that the crowd matters, and adding it would add a parameter
    to a ~700-row fit.
    """
    so = frame[frame["shootout_winner"].notna() & (frame["goals_a"] == frame["goals_b"])]
    so = so[(so["shootout_winner"] == so["team_a"]) | (so["shootout_winner"] == so["team_b"])]
    if len(so) < 50:
        return 0.0, int(len(so)), {"note": "too few shoot-outs; using 50/50"}
    z = so["elo_diff"].to_numpy() / 400.0
    y = (so["shootout_winner"] == so["team_a"]).to_numpy().astype(float)

    def nll(b):
        p = np.clip(expit(b * z), 1e-9, 1 - 1e-9)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()

    beta = float(minimize_scalar(nll, bounds=(-2.0, 4.0), method="bounded").x)
    # Is beta distinguishable from zero? Likelihood ratio against the coin flip.
    lr = 2 * len(so) * (nll(0.0) - nll(beta))
    higher_rated_won = float(((z > 0) == (y == 1))[z != 0].mean())
    info = {"n_shootouts": int(len(so)), "beta": round(beta, 4), "lr_statistic_vs_coin_flip": round(float(lr), 3),
            "significant_at_5pct": bool(lr > 3.841), "higher_rated_side_win_rate": round(higher_rated_won, 4)}
    if lr <= 3.841:
        # Not distinguishable from a coin flip on this data: do not pretend otherwise.
        return 0.0, int(len(so)), {**info, "used": "beta=0 (coin flip)"}
    return beta, int(len(so)), {**info, "used": "fitted beta"}


def fit_on_split(train: pd.DataFrame, val: pd.DataFrame, xgb_params: dict, seed: int = 42) -> Forecaster:
    """
    The evaluated configuration: base models on ``train``; the first half of
    ``val`` stops XGBoost early, the second half fits the temperature.
    """
    mid = val["date"].quantile(0.5)
    val_es, val_cal = val[val["date"] <= mid], val[val["date"] > mid]
    poisson = PoissonDixonColes(use_dc=True).fit(train)
    xgb = XGBOutcome(seed=seed, **xgb_params).fit(train, val_es)
    p_cal = blend([poisson.predict_proba(val_cal), xgb.predict_proba(val_cal)], np.array(BLEND_WEIGHTS))
    cal = Temperature().fit(p_cal, encode_y(val_cal))
    beta, n, info = fit_shootout_model(pd.concat([train, val]))
    return Forecaster(poisson, xgb, cal, beta, n, meta={
        "fit": "split", "n_train": len(train), "n_val_es": len(val_es), "n_val_cal": len(val_cal),
        "xgb_best_iteration": xgb.best_iteration, "xgb_params": xgb_params, "shootout": info,
        "temperature": cal.T, "rho": poisson.rho})


def fit_production(frame: pd.DataFrame, cutoff: pd.Timestamp, xgb_params: dict, seed: int = 42,
                   train_start: str = "1990-01-01") -> Forecaster:
    """
    The shipped model for a given information cutoff.

    1. Fit exactly as evaluated, holding out the last CALIBRATION_YEARS before the
       cutoff: that fixes XGBoost's tree count and the temperature using
       out-of-time predictions.
    2. Refit both base models on everything before the cutoff with those two
       numbers frozen, so the most recent matches are not wasted.

    Nothing dated on or after ``cutoff`` is touched.
    """
    data = frame[(frame["date"] >= train_start) & (frame["date"] < cutoff)]
    if data["date"].max() >= cutoff:
        raise AssertionError("training data reaches the cutoff")
    val_start = cutoff - pd.DateOffset(years=CALIBRATION_YEARS)
    train, val = data[data["date"] < val_start], data[data["date"] >= val_start]
    staged = fit_on_split(train, val, xgb_params, seed)

    poisson = PoissonDixonColes(use_dc=True).fit(data)
    xgb = XGBOutcome(seed=seed, **xgb_params).fit(data, None, n_estimators=staged.xgb.best_iteration)
    beta, n, info = fit_shootout_model(data)
    return Forecaster(poisson, xgb, staged.calibrator, beta, n, meta={
        "fit": "production", "cutoff": str(cutoff.date()), "train_start": train_start,
        "n_train": int(len(data)), "train_last_match": str(data["date"].max().date()),
        "calibration_window": [str(val_start.date()), str(cutoff.date())],
        "n_calibration": staged.meta["n_val_cal"], "xgb_n_estimators": staged.xgb.best_iteration,
        "xgb_params": xgb_params, "temperature": staged.calibrator.T, "rho": poisson.rho,
        "blend_weights": {"poisson_dc": BLEND_WEIGHTS[0], "xgboost": BLEND_WEIGHTS[1]},
        "shootout": info, "seed": seed})
