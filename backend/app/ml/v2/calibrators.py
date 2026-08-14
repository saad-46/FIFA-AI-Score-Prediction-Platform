"""
Probability calibrators for the V2 model.

These live in their own module rather than beside the training script on
purpose: a class defined in a module executed as ``__main__`` pickles with the
module path ``__main__.ClassName``, which then fails to load from any other
entry point. Keeping them here means a saved bundle records
``app.ml.v2.calibrators.ClassName`` and loads anywhere in the project.

Platt and isotonic follow the per-class + renormalise convention already used
by ``app/ml/calibration.py`` so V2 stays consistent with the existing pipeline.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

EPS = 1e-12


def _renorm(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1.0)
    return p / p.sum(axis=1, keepdims=True)


class NoCalibration:
    """Passthrough baseline (still renormalised, so the contract holds)."""
    name = "none"

    def fit(self, proba, y):
        return self

    def transform(self, proba):
        return _renorm(np.asarray(proba, dtype=float))

    @property
    def params(self) -> dict:
        return {}


class PlattCalibration:
    """Per-class logistic (sigmoid) calibration, then renormalise."""
    name = "platt"

    def __init__(self):
        self.models: list[LogisticRegression] = []

    def fit(self, proba, y):
        proba = np.asarray(proba, dtype=float)
        y = np.asarray(y, dtype=int)
        self.models = []
        for c in range(proba.shape[1]):
            lr = LogisticRegression(C=1.0, max_iter=1000)
            lr.fit(proba[:, [c]], (y == c).astype(int))
            self.models.append(lr)
        return self

    def transform(self, proba):
        proba = np.asarray(proba, dtype=float)
        out = np.column_stack([
            m.predict_proba(proba[:, [c]])[:, 1] for c, m in enumerate(self.models)])
        return _renorm(out)

    @property
    def params(self) -> dict:
        return {f"class_{c}": {"coef": float(m.coef_[0][0]),
                               "intercept": float(m.intercept_[0])}
                for c, m in enumerate(self.models)}


class IsotonicCalibration:
    """Per-class isotonic regression, then renormalise."""
    name = "isotonic"

    def __init__(self):
        self.models: list[IsotonicRegression] = []

    def fit(self, proba, y):
        proba = np.asarray(proba, dtype=float)
        y = np.asarray(y, dtype=int)
        self.models = []
        for c in range(proba.shape[1]):
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(proba[:, c], (y == c).astype(int))
            self.models.append(iso)
        return self

    def transform(self, proba):
        proba = np.asarray(proba, dtype=float)
        out = np.column_stack([m.predict(proba[:, c]) for c, m in enumerate(self.models)])
        return _renorm(out)

    @property
    def params(self) -> dict:
        return {"n_class_models": len(self.models),
                "type": "per-class isotonic, renormalised"}


class TemperatureCalibration:
    """
    ``softmax(log(p) / T)`` with a single fitted scalar T.

    T > 1 softens an overconfident model. The transform is monotonic and applied
    identically to every class, so the argmax cannot change — accuracy,
    precision, recall, draw recall and the confusion matrix are provably
    unaffected. Only the probabilities move, which is exactly the intervention
    an overconfidence problem calls for.
    """
    name = "temperature"

    def __init__(self):
        self.T = 1.0

    def fit(self, proba, y):
        proba = np.asarray(proba, dtype=float)
        y = np.asarray(y, dtype=int)
        logits = np.log(np.clip(proba, EPS, 1.0))
        idx = np.arange(len(y))

        def nll(t: float) -> float:
            if t <= 0:
                return 1e9
            scaled = logits / t
            scaled -= scaled.max(axis=1, keepdims=True)
            e = np.exp(scaled)
            p = e / e.sum(axis=1, keepdims=True)
            return float(-np.mean(np.log(np.clip(p[idx, y], EPS, 1.0))))

        self.T = float(minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded").x)
        return self

    def transform(self, proba):
        proba = np.asarray(proba, dtype=float)
        logits = np.log(np.clip(proba, EPS, 1.0)) / self.T
        logits -= logits.max(axis=1, keepdims=True)
        e = np.exp(logits)
        return _renorm(e / e.sum(axis=1, keepdims=True))

    @property
    def params(self) -> dict:
        return {"temperature": round(self.T, 6)}


class FrozenTemperature(TemperatureCalibration):
    """
    Temperature scaling pinned to a pre-established T instead of refitting.

    Used as a control when calibrating a second model: it answers "does
    refitting the temperature on this model's own out-of-fold predictions
    actually beat reusing the value fitted for the previous model?" — so the
    reuse decision is a measured result rather than an assumption.

    Lives here, not in the training script, for the same reason as every other
    calibrator: a class defined in a module executed as ``__main__`` pickles as
    ``__main__.FrozenTemperature`` and then fails to load from any other entry
    point.
    """
    name = "temperature_frozen"

    #: T fitted on the v2 backtest model's out-of-fold predictions.
    DEFAULT_T = 2.472107

    def __init__(self, temperature: float | None = None):
        super().__init__()
        self.T = float(temperature if temperature is not None else self.DEFAULT_T)

    def fit(self, proba, y):
        return self          # pinned by construction — nothing to fit


CALIBRATORS = {
    "none": NoCalibration,
    "platt": PlattCalibration,
    "isotonic": IsotonicCalibration,
    "temperature": TemperatureCalibration,
}
