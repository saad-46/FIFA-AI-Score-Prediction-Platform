"""
Candidate models. Every one answers the same question with the same interface:

    fit(train, val)            train on `train`; `val` is a later, disjoint period
                               available for early stopping only
    predict_proba(frame)       (n, 3) array: P(A wins), P(draw), P(B wins)
    predict_goals(frame)       (lambda_a, lambda_b) or None

Outcome encoding is ``OUTCOMES = ("A", "D", "B")`` -> 0, 1, 2 throughout. "A" is
the first-listed team; whether A is at home is carried by the ``venue`` feature,
never by position.

Order invariance
----------------
Swapping the two teams must swap P(A) and P(B) and leave P(draw) alone. The
rating-based models are built from antisymmetric terms and satisfy that exactly.
The learned models (logistic regression, XGBoost) are trained on each fixture in
both orientations and predict as the average of the two orientations, which
makes the property exact for them too rather than approximately learned.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, gammaln
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.preprocessing import StandardScaler

from app.ml.v3.features import ANTISYMMETRIC, FEATURE_NAMES, feature_matrix, mirror

OUTCOMES = ("A", "D", "B")
_Y = {"A": 0, "D": 1, "B": 2}
MAX_GOALS = 10
EPS = 1e-12


def encode_y(frame: pd.DataFrame) -> np.ndarray:
    return frame["result"].map(_Y).to_numpy(dtype=int)


def _swap_ab(p: np.ndarray) -> np.ndarray:
    return p[:, [2, 1, 0]]


def normalise(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, None)
    return p / p.sum(axis=1, keepdims=True)


# ── Score-matrix utilities (shared by Poisson model and tournament engine) ───

_GRID = np.arange(MAX_GOALS + 1)
_LOGFACT = gammaln(_GRID + 1)


def poisson_pmf_vec(lam: float) -> np.ndarray:
    return np.exp(_GRID * math.log(max(lam, 1e-9)) - lam - _LOGFACT)


def score_matrix(lam_a: float, lam_b: float, rho: float = 0.0) -> np.ndarray:
    """
    Joint P(goals_a = i, goals_b = j) for i, j in 0..MAX_GOALS.

    Independent Poisson with the Dixon & Coles (1997) low-score correction tau:
    the four cells 0-0, 1-0, 0-1, 1-1 are reweighted by ``rho`` so that draws
    and 1-0 results match what is observed. The matrix is renormalised, which
    also absorbs the mass truncated above MAX_GOALS.
    """
    m = np.outer(poisson_pmf_vec(lam_a), poisson_pmf_vec(lam_b))
    if rho != 0.0:
        m[0, 0] *= max(1.0 - lam_a * lam_b * rho, 1e-6)
        m[0, 1] *= max(1.0 + lam_a * rho, 1e-6)
        m[1, 0] *= max(1.0 + lam_b * rho, 1e-6)
        m[1, 1] *= max(1.0 - rho, 1e-6)
    return m / m.sum()


def outcome_from_matrix(m: np.ndarray) -> tuple[float, float, float]:
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


# ── A. Baselines ─────────────────────────────────────────────────────────────

class PriorModel:
    """Historical class frequencies, by venue state. Knows nothing about teams."""
    name = "prior"

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None) -> "PriorModel":
        y = encode_y(train)
        home = train["venue"].to_numpy() == 1
        self.p_home = np.bincount(y[home], minlength=3) / max(home.sum(), 1)
        # Neutral games: listing order is arbitrary, so force P(A) = P(B).
        d = float((y[~home] == 1).mean()) if (~home).any() else 0.25
        self.p_neutral = np.array([(1 - d) / 2, d, (1 - d) / 2])
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        v = frame["venue"].to_numpy()
        out = np.tile(self.p_neutral, (len(frame), 1))
        out[v == 1] = self.p_home
        out[v == -1] = self.p_home[::-1]
        return out

    def predict_goals(self, frame):
        return None


class EloOrderedLogit:
    """
    Elo difference -> win/draw/loss through a symmetric ordered logit.

        P(B) = sigmoid(-c - b z),  P(A) = 1 - sigmoid(c - b z),  z = elo_diff_venue / 400
        c    = exp(c0 + c1 |z|)    (draws become rarer as the mismatch grows)

    Three parameters, fitted by maximum likelihood. Exactly order-invariant.
    """
    name = "elo_ordered_logit"

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None) -> "EloOrderedLogit":
        z = train["elo_diff_venue"].to_numpy() / 400.0
        y = encode_y(train)

        def nll(theta):
            p = self._proba(z, theta)
            return -np.log(p[np.arange(len(y)), y]).mean()

        res = minimize(nll, x0=np.array([1.6, math.log(0.55), 0.0]), method="Nelder-Mead",
                       options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 4000})
        self.theta = res.x
        return self

    @staticmethod
    def _proba(z: np.ndarray, theta) -> np.ndarray:
        b, c0, c1 = theta
        c = np.exp(c0 + c1 * np.abs(z))
        pb = expit(-c - b * z)
        pa = 1.0 - expit(c - b * z)
        return normalise(np.column_stack([pa, 1.0 - pa - pb, pb]))

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return self._proba(frame["elo_diff_venue"].to_numpy() / 400.0, self.theta)

    def predict_goals(self, frame):
        return None


# ── C. Poisson / Dixon-Coles ─────────────────────────────────────────────────

class PoissonDixonColes:
    """
    Goals for each side as Poisson with a log-linear rate, then a joint scoreline
    distribution with the Dixon-Coles correction.

        log lambda_A = t(x) + s(x)/2        s: antisymmetric features (who is better)
        log lambda_B = t(x) - s(x)/2        t: symmetric features (how open the game is)

    Fitted as one Poisson regression on a stacked design (each match contributes
    its A row and its mirrored B row), so swapping the teams swaps the rates
    exactly. ``rho`` is then estimated by maximum likelihood with the rates held
    fixed, as in Dixon & Coles' two-stage practice.
    """
    name = "poisson_dc"
    ANTI = ("elo_diff_venue", "venue", "log_xg_ratio", "form_gd_diff", "form_pts_diff", "h2h_gd_shrunk")
    SYM = ("log_xg_total", "tier", "abs_elo_diff")

    def __init__(self, alpha: float = 1e-4, use_dc: bool = True):
        self.alpha = alpha
        self.use_dc = use_dc
        self.rho = 0.0

    def _design(self, frame: pd.DataFrame, sign: float) -> np.ndarray:
        anti = frame.loc[:, list(self.ANTI)].to_numpy(dtype=float) * sign
        sym = frame.loc[:, list(self.SYM)].to_numpy(dtype=float)
        return np.hstack([anti, sym])

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None) -> "PoissonDixonColes":
        X = np.vstack([self._design(train, +1.0), self._design(train, -1.0)])
        y = np.concatenate([train["goals_a"].to_numpy(), train["goals_b"].to_numpy()]).astype(float)
        self.scaler = StandardScaler(with_mean=False).fit(X)   # scale only: keeps antisymmetry
        self.glm = PoissonRegressor(alpha=self.alpha, max_iter=500).fit(self.scaler.transform(X), y)
        if self.use_dc:
            la, lb = self.predict_goals(train)
            ga, gb = train["goals_a"].to_numpy(), train["goals_b"].to_numpy()
            low = (ga <= 1) & (gb <= 1)
            la_, lb_, ga_, gb_ = la[low], lb[low], ga[low], gb[low]

            def nll(r):
                r = float(r[0])
                tau = np.where((ga_ == 0) & (gb_ == 0), 1 - la_ * lb_ * r,
                      np.where((ga_ == 0) & (gb_ == 1), 1 + la_ * r,
                      np.where((ga_ == 1) & (gb_ == 0), 1 + lb_ * r, 1 - r)))
                return -np.log(np.clip(tau, 1e-9, None)).sum()

            self.rho = float(minimize(nll, x0=[-0.05], bounds=[(-0.3, 0.3)], method="L-BFGS-B").x[0])
        return self

    def predict_goals(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        la = self.glm.predict(self.scaler.transform(self._design(frame, +1.0)))
        lb = self.glm.predict(self.scaler.transform(self._design(frame, -1.0)))
        return np.clip(la, 0.05, 8.0), np.clip(lb, 0.05, 8.0)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        la, lb = self.predict_goals(frame)
        return normalise(np.array([outcome_from_matrix(score_matrix(a, b, self.rho)) for a, b in zip(la, lb)]))


# ── Learned models: shared symmetric training/prediction ─────────────────────

def _augmented(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    X = feature_matrix(frame)
    y = encode_y(frame)
    return pd.concat([X, mirror(X)], ignore_index=True), np.concatenate([y, 2 - y])


class MultinomialLogit:
    """Multinomial logistic regression on the registered pre-match features."""
    name = "multinomial_logit"

    def __init__(self, C: float = 1.0):
        self.C = C

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None) -> "MultinomialLogit":
        X, y = _augmented(train)
        self.scaler = StandardScaler().fit(X)
        self.clf = LogisticRegression(C=self.C, max_iter=2000).fit(self.scaler.transform(X), y)
        return self

    def _raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.clf.predict_proba(self.scaler.transform(X))

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        X = feature_matrix(frame)
        return normalise(0.5 * (self._raw(X) + _swap_ab(self._raw(mirror(X)))))

    def predict_goals(self, frame):
        return None


class XGBOutcome:
    """
    XGBoost multiclass on the same features, deliberately small: the signal in
    international results is thin and a deep model memorises noise. Early
    stopping uses the later validation period, never the test period.
    """
    name = "xgboost"

    def __init__(self, seed: int = 42, **params):
        self.seed = seed
        self.params = dict(max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                           min_child_weight=20, reg_lambda=5.0, gamma=0.0)
        self.params.update(params)
        self.best_iteration: Optional[int] = None

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None,
            n_estimators: Optional[int] = None) -> "XGBOutcome":
        import xgboost as xgb
        Xtr, ytr = _augmented(train)
        kw = dict(objective="multi:softprob", num_class=3, eval_metric="mlogloss", tree_method="hist",
                  random_state=self.seed, n_jobs=4, **self.params)
        if n_estimators is not None or val is None or len(val) == 0:
            self.clf = xgb.XGBClassifier(n_estimators=n_estimators or 300, **kw).fit(Xtr, ytr, verbose=False)
            self.best_iteration = n_estimators or 300
        else:
            Xv, yv = _augmented(val)
            self.clf = xgb.XGBClassifier(n_estimators=2000, early_stopping_rounds=50, **kw)
            self.clf.fit(Xtr, ytr, eval_set=[(Xv, yv)], verbose=False)
            self.best_iteration = int(self.clf.best_iteration) + 1
        return self

    def _raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.clf.predict_proba(X)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        X = feature_matrix(frame)
        return normalise(0.5 * (self._raw(X) + _swap_ab(self._raw(mirror(X)))))

    def predict_goals(self, frame):
        return None


class XGBGoals:
    """XGBoost Poisson regressor for goals, benchmarked against the Poisson GLM."""
    name = "xgboost_goals"

    def __init__(self, seed: int = 42):
        self.seed = seed

    def fit(self, train: pd.DataFrame, val: Optional[pd.DataFrame] = None) -> "XGBGoals":
        import xgboost as xgb
        def stack(f):
            X = feature_matrix(f)
            return (pd.concat([X, mirror(X)], ignore_index=True),
                    np.concatenate([f["goals_a"].to_numpy(), f["goals_b"].to_numpy()]).astype(float))
        Xtr, ytr = stack(train)
        kw = dict(objective="count:poisson", tree_method="hist", max_depth=3, learning_rate=0.05,
                  subsample=0.8, colsample_bytree=0.8, min_child_weight=20, reg_lambda=5.0,
                  random_state=self.seed, n_jobs=4)
        if val is not None and len(val):
            Xv, yv = stack(val)
            self.reg = xgb.XGBRegressor(n_estimators=2000, early_stopping_rounds=50, **kw)
            self.reg.fit(Xtr, ytr, eval_set=[(Xv, yv)], verbose=False)
        else:
            self.reg = xgb.XGBRegressor(n_estimators=300, **kw).fit(Xtr, ytr)
        return self

    def predict_goals(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        X = feature_matrix(frame)
        return np.clip(self.reg.predict(X), 0.05, 8.0), np.clip(self.reg.predict(mirror(X)), 0.05, 8.0)

    def predict_proba(self, frame):
        la, lb = self.predict_goals(frame)
        return normalise(np.array([outcome_from_matrix(score_matrix(a, b)) for a, b in zip(la, lb)]))


# ── E. Ensemble ──────────────────────────────────────────────────────────────

def fit_simplex_weights(prob_list: list[np.ndarray], y: np.ndarray) -> np.ndarray:
    """
    Non-negative weights summing to one that minimise log loss of the weighted
    average. Fitted on validation predictions only.
    """
    k = len(prob_list)
    P = np.stack(prob_list)                      # (k, n, 3)
    idx = np.arange(len(y))

    def nll(theta):
        w = np.exp(theta - theta.max()); w /= w.sum()
        p = np.tensordot(w, P, axes=1)
        return -np.log(np.clip(p[idx, y], EPS, None)).mean()

    res = minimize(nll, x0=np.zeros(k), method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-7})
    w = np.exp(res.x - res.x.max())
    return w / w.sum()


def blend(prob_list: list[np.ndarray], weights: np.ndarray) -> np.ndarray:
    return normalise(np.tensordot(np.asarray(weights), np.stack(prob_list), axes=1))
