"""
Genuine SHAP explanations for the V2 result classifier.

WHAT IS AND ISN'T EXPLAINABLE HERE — stated up front, because the honest
answer is not "everything".

  Result probabilities (home/draw/away)   EXPLAINABLE
      The V2 result model is an XGBoost multi-class classifier, so
      ``shap.TreeExplainer`` gives exact per-class, per-feature contributions
      in log-odds space. These are real attributions computed from the actual
      model against the actual input vector.

  Predicted score (home/away goals)       EXPLAINABLE, SEPARATELY
      Two Poisson-objective XGBRegressors. TreeExplainer works on them too,
      but the contributions live in a different space (log-expected-goals) and
      answer a different question. They are exposed as their own blocks rather
      than blended into the result explanation, because summing attributions
      across differently-scaled models would produce a number that looks
      meaningful and isn't.

  Most-likely scoreline / top scorelines  NOT SHAP-EXPLAINABLE
      These come from the Poisson engine, a closed-form transformation of the
      two xG values — not a learned model. There are no features to attribute
      to. Rather than invent an explanation, the API reports which xG values
      produced the distribution and leaves it at that.

  Calibration (temperature)               DELIBERATELY NOT ATTRIBUTED
      Temperature scaling is monotonic and feature-independent: it rescales
      every logit identically. It changes the probabilities but contributes
      nothing feature-specific, so it does not appear in the attributions.
      SHAP values are computed on the UNCALIBRATED classifier — which is the
      correct model to explain, since calibration cannot change the ranking of
      feature contributions.

Nothing here is fabricated. If SHAP is unavailable or errors, the explanation
is omitted (``None``) rather than replaced with a plausible-looking list of
"important factors" — the failure mode this module exists to avoid.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CLASS_INDEX = {"away_win": 0, "draw": 1, "home_win": 2}

# Human-readable labels. Anything not listed falls through to the generic
# formatter, so a newly added feature always gets a sensible name rather than
# being dropped or shown raw.
_LABEL_OVERRIDES = {
    "elo_diff": "Elo rating difference",
    "elo_abs_diff": "Elo gap (absolute)",
    "home_elo": "Home team Elo",
    "away_elo": "Away team Elo",
    "fifa_rank_diff": "FIFA ranking difference",
    "s5_elo_diff": "Pre-tournament Elo difference",
    "is_knockout": "Knockout match",
    "neutral_venue": "Neutral venue",
    "stage_order": "Tournament stage",
    "rest_days_diff": "Rest-days advantage",
    "wc_matches_diff": "World Cup experience difference",
    "wc_tournaments_diff": "Tournaments played difference",
    "wc_knockout_matches_diff": "Knockout experience difference",
    "wc_winrate_diff": "World Cup win-rate difference",
    "wc_gf_avg_diff": "Goals-scored average difference",
    "wc_ga_avg_diff": "Goals-conceded average difference",
}
_WINDOW_RE = re.compile(r"^(home|away)_form_(\w+?)_(\d+)$")
_STAT_NAMES = {
    "pts": "points per match", "gf": "goals scored", "ga": "goals conceded",
    "gd": "goal difference", "winrate": "win rate", "drawrate": "draw rate",
    "cs": "clean-sheet rate",
}


def readable_name(feature: str) -> str:
    if feature in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[feature]
    m = _WINDOW_RE.match(feature)
    if m:
        side, stat, window = m.groups()
        label = _STAT_NAMES.get(stat, stat.replace("_", " "))
        return f"{side.capitalize()} {label}, last {window}"
    m = re.match(r"^form_(\w+?)_diff_(\d+)$", feature)
    if m:
        stat, window = m.groups()
        return f"{_STAT_NAMES.get(stat, stat)} difference, last {window}"
    if feature.startswith(("home_wc_", "away_wc_")):
        side, rest = feature.split("_wc_", 1)
        return f"{side.capitalize()} World Cup {rest.replace('_', ' ')}"
    return feature.replace("_", " ").capitalize()


class V2Explainer:
    """
    TreeExplainer over the V2 bundle.

    Built lazily and degrades to ``None`` explanations on any failure — an
    explanation is a nice-to-have, and a prediction endpoint should not 500
    because SHAP had a problem.
    """

    def __init__(self, classifier, home_regressor, away_regressor,
                 feature_columns: list[str]):
        self.feature_columns = list(feature_columns)
        self._classifier = classifier
        self._home_regressor = home_regressor
        self._away_regressor = away_regressor
        self._clf_explainer = None
        self._home_explainer = None
        self._away_explainer = None
        self._ready = False
        self._init_error: Optional[str] = None
        self._build()

    def _build(self) -> None:
        try:
            import shap
            self._clf_explainer = shap.TreeExplainer(self._classifier)
            self._home_explainer = shap.TreeExplainer(self._home_regressor)
            self._away_explainer = shap.TreeExplainer(self._away_regressor)
            self._ready = True
            logger.info("V2Explainer ready (%d features)", len(self.feature_columns))
        except Exception as exc:                      # pragma: no cover
            self._init_error = f"{type(exc).__name__}: {exc}"
            logger.warning("V2Explainer unavailable — explanations will be omitted: %s",
                           self._init_error)

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------ core
    def explain(self, x: np.ndarray, predicted_class: str, top_n: int = 5) -> Optional[dict]:
        """
        Attributions for the predicted class, plus separate xG attributions.

        ``x`` must be the SAME vector passed to the model — the caller hands
        it in rather than rebuilding it, so SHAP input and prediction input
        cannot drift apart.
        """
        if not self._ready:
            return None
        if predicted_class not in CLASS_INDEX:
            logger.warning("V2Explainer: unknown class %r", predicted_class)
            return None

        try:
            x = np.asarray(x, dtype=np.float32).reshape(1, -1)
            if x.shape[1] != len(self.feature_columns):
                raise ValueError(
                    f"feature vector has {x.shape[1]} columns, expected "
                    f"{len(self.feature_columns)}"
                )

            values = self._clf_explainer.shap_values(x)
            class_idx = CLASS_INDEX[predicted_class]
            contribs = self._class_contributions(values, class_idx)
            if contribs is None:
                return None

            ranked = sorted(
                (
                    {
                        "feature": name,
                        "readable_name": readable_name(name),
                        "contribution": round(float(val), 6),
                        "direction": "increases" if val > 0 else "decreases",
                        "value": (None if np.isnan(x[0, i]) else round(float(x[0, i]), 4)),
                    }
                    for i, (name, val) in enumerate(zip(self.feature_columns, contribs))
                    if abs(val) > 1e-9
                ),
                key=lambda d: abs(d["contribution"]),
                reverse=True,
            )
            positive = [d for d in ranked if d["contribution"] > 0][:top_n]
            negative = [d for d in ranked if d["contribution"] < 0][:top_n]

            return {
                "method": "shap.TreeExplainer",
                "explained_output": predicted_class,
                "space": "log-odds contribution to the predicted class",
                "n_features": len(self.feature_columns),
                "top_positive_features": positive,
                "top_negative_features": negative,
            }
        except Exception as exc:                      # pragma: no cover
            logger.warning("V2Explainer.explain failed — omitting explanation: %s", exc)
            return None

    def explain_goals(self, x: np.ndarray, top_n: int = 3) -> Optional[dict]:
        """Separate attributions for the two xG regressors (different space —
        never merged with the result attributions)."""
        if not self._ready:
            return None
        try:
            x = np.asarray(x, dtype=np.float32).reshape(1, -1)
            out = {}
            for side, explainer in (("home", self._home_explainer),
                                    ("away", self._away_explainer)):
                vals = np.asarray(explainer.shap_values(x)).reshape(-1)
                ranked = sorted(
                    (
                        {
                            "feature": name,
                            "readable_name": readable_name(name),
                            "contribution": round(float(v), 6),
                            "direction": "increases" if v > 0 else "decreases",
                        }
                        for name, v in zip(self.feature_columns, vals)
                        if abs(v) > 1e-9
                    ),
                    key=lambda d: abs(d["contribution"]), reverse=True,
                )[:top_n]
                out[f"{side}_expected_goals"] = ranked
            out["space"] = "contribution to log expected goals"
            return out
        except Exception as exc:                      # pragma: no cover
            logger.warning("V2Explainer.explain_goals failed: %s", exc)
            return None

    @staticmethod
    def _class_contributions(values, class_idx: int):
        """
        Normalise SHAP's several multi-class return shapes.

        Depending on version and model, ``shap_values`` returns a list of
        per-class arrays, or a single (n, features, classes) array. Guessing
        wrong here silently attributes the wrong class — hence the explicit
        shape handling rather than an index-and-hope.
        """
        arr = values
        if isinstance(arr, list):
            if class_idx >= len(arr):
                return None
            return np.asarray(arr[class_idx]).reshape(-1)
        arr = np.asarray(arr)
        if arr.ndim == 3:                       # (n, features, classes)
            if class_idx >= arr.shape[2]:
                return None
            return arr[0, :, class_idx].reshape(-1)
        if arr.ndim == 2:                       # (n, features) — binary/regression
            return arr[0].reshape(-1)
        return None
