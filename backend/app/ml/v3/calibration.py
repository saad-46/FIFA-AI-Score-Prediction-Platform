"""
Probability calibration.

A calibrator is fitted on predictions for a period the base model did not train
on, and judged on a later period again. Three methods are compared in the
benchmark; which one ships is decided there, not here.

* ``Temperature`` -- one parameter: p_i^(1/T), renormalised. Cannot reorder
  classes, so it can fix over/under-confidence but cannot hide a model that
  discriminates poorly.
* ``SigmoidOvR`` -- Platt scaling per class on the logit, renormalised (the
  multiclass form scikit-learn's ``CalibratedClassifierCV(method="sigmoid")``
  uses).
* ``IsotonicOvR`` -- isotonic regression per class, renormalised. Flexible, and
  for that reason only trustworthy with a large calibration sample.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

EPS = 1e-12


def _norm(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, None)
    return p / p.sum(axis=1, keepdims=True)


class Identity:
    name = "none"

    def fit(self, p, y):
        return self

    def transform(self, p):
        return _norm(p)

    def describe(self):
        return {"method": "none"}


class Temperature:
    name = "temperature"

    def __init__(self):
        self.T = 1.0

    def fit(self, p: np.ndarray, y: np.ndarray) -> "Temperature":
        logp = np.log(np.clip(p, EPS, None))
        idx = np.arange(len(y))

        def nll(t):
            q = _norm(np.exp(logp / t))
            return -np.log(q[idx, y]).mean()

        self.T = float(minimize_scalar(nll, bounds=(0.3, 3.0), method="bounded").x)
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        return _norm(np.exp(np.log(np.clip(p, EPS, None)) / self.T))

    def describe(self):
        return {"method": "temperature", "T": round(self.T, 4)}


class SigmoidOvR:
    name = "sigmoid"

    def fit(self, p: np.ndarray, y: np.ndarray) -> "SigmoidOvR":
        self.models = []
        for k in range(p.shape[1]):
            z = np.log(np.clip(p[:, k], EPS, 1 - EPS) / np.clip(1 - p[:, k], EPS, 1))
            self.models.append(LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), (y == k).astype(int)))
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        cols = []
        for k, m in enumerate(self.models):
            z = np.log(np.clip(p[:, k], EPS, 1 - EPS) / np.clip(1 - p[:, k], EPS, 1))
            cols.append(m.predict_proba(z.reshape(-1, 1))[:, 1])
        return _norm(np.column_stack(cols))

    def describe(self):
        return {"method": "sigmoid_ovr",
                "coef": [round(float(m.coef_[0, 0]), 4) for m in self.models],
                "intercept": [round(float(m.intercept_[0]), 4) for m in self.models]}


class IsotonicOvR:
    name = "isotonic"

    def fit(self, p: np.ndarray, y: np.ndarray) -> "IsotonicOvR":
        self.models = [IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p[:, k], (y == k).astype(float))
                       for k in range(p.shape[1])]
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        return _norm(np.column_stack([m.predict(p[:, k]) for k, m in enumerate(self.models)]))

    def describe(self):
        return {"method": "isotonic_ovr"}


CALIBRATORS = {"none": Identity, "temperature": Temperature, "sigmoid": SigmoidOvR, "isotonic": IsotonicOvR}
