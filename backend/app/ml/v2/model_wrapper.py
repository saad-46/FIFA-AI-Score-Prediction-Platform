"""
V2PredictionAdapter — the V2 side of the ModelLoader abstraction
(see app/ml/model_loader.py).

Serves the ``v2-calibrated`` bundle produced by the calibration phase
(``app/ml/v2/calibrate.py``): E4_plus_context (92 features), XGBoost result
classifier + Poisson-objective goal regressors, temperature-scaled
probabilities (T=2.472).

Reuses rather than reimplements wherever the legacy pipeline already has a
model-independent component:
  * ``app.ml.poisson.PoissonEngine`` turns (home_xg, away_xg) into the
    scoreline distribution — identical component the legacy path uses.
  * Team-name aliasing reuses the same TEAM_ALIASES table the dataset build
    used, so "Iran" resolves to the same bucket as "IR Iran" at inference
    time as it did at training time.

Known scope limits of this integration phase (see the integration report):
  * The feature-accumulator state is frozen at the end of 2022 (this is the
    WC2026_BACKTEST-mode bundle — the one actually calibrated and validated).
    A prediction made today does not learn from 2026 results. Serving from
    the CURRENT_PRODUCTION-trained bundle instead would require calibrating
    *that* bundle, which was not done in the calibration phase and is not
    invented here.
  * No SHAP explainer is wired up for V2 yet — ``prediction_explanation`` is
    always empty, which the shared PredictionResult assembly already treats
    as "no explanation available" (same as it does for the legacy path when
    SHAP isn't ready).
  * Feature building reads the local canonical CSV snapshot
    (``app/data/canonical/``), the same source the training/validation
    pipeline already used — not the ``matches_v2`` Supabase table. That
    table is a mirror of the same data; switching to it is a read-only
    follow-up, not a schema change, and is listed as remaining work.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.ml.poisson import PoissonEngine
from app.ml.v2.data_source import load_canonical_from
from app.ml.v2.explain import V2Explainer
from app.ml.v2.features import FeatureBuilder, synthetic_match

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "model_v2_calibrated.pkl"
PRODUCTION_ARTIFACT_PATH = ARTIFACT_DIR / "model_v2_production_calibrated.pkl"
REQUIRED_KEYS = {
    "model_version", "mode", "classifier", "home_regressor", "away_regressor",
    "calibrator", "calibration_method", "feature_columns", "feature_groups",
}
_PROB_SUM_TOLERANCE = 1e-4


def _load_team_aliases() -> dict[str, str]:
    """
    Same alias table the five-source rebuild used to canonicalise team
    names (USA/United States, IR Iran/Iran, etc.) — imported rather than
    duplicated so the two stay in sync by construction.
    """
    try:
        from app.data.build_canonical_dataset import TEAM_ALIASES
        return dict(TEAM_ALIASES)
    except ImportError:
        logger.warning("V2: could not import TEAM_ALIASES; proceeding without aliasing")
        return {}


class V2PredictionAdapter:
    """Loads the calibrated V2 bundle and the frozen feature-accumulator
    state once, then serves predictions from cached in-memory objects —
    the same lazy-singleton pattern the legacy MatchPredictor uses."""

    def __init__(self, artifact_path: Path | None = None,
                 data_source: str | None = None) -> None:
        settings = get_settings()
        if artifact_path is None:
            artifact_path = (PRODUCTION_ARTIFACT_PATH
                             if settings.V2_USE_PRODUCTION_MODEL
                             else ARTIFACT_PATH)
        if data_source is None:
            data_source = settings.V2_DATA_SOURCE

        if not artifact_path.exists():
            raise FileNotFoundError(
                f"V2 model artifact not found at {artifact_path}. Run "
                "`python -m app.ml.v2.calibrate` (backtest) or "
                "`python -m app.ml.v2.calibrate_production` (production) to "
                "produce it, or set USE_V2_MODEL=false."
            )

        bundle = joblib.load(artifact_path)
        missing = REQUIRED_KEYS - bundle.keys()
        if missing:
            raise ValueError(f"V2 model bundle at {artifact_path} is missing keys: {missing}")

        self.model_version: str = bundle["model_version"]
        self.mode: str = bundle["mode"]
        self.classifier = bundle["classifier"]
        self.home_regressor = bundle["home_regressor"]
        self.away_regressor = bundle["away_regressor"]
        self.calibrator = bundle["calibrator"]
        self.calibration_method: str = bundle["calibration_method"]
        self.feature_columns: list[str] = list(bundle["feature_columns"])
        self.feature_groups: tuple = tuple(bundle["feature_groups"])

        self.data_source = data_source
        matches, teams, stats = load_canonical_from(data_source)
        self._teams_df = teams
        # Backtest mode freezes accumulators at 2022 so no 2026 match learns
        # from an earlier 2026 match. Production runs them normally: when
        # predicting a future match you legitimately know past results.
        freeze_year = 2022 if self.mode == "WC2026_BACKTEST" else None
        _, self.builder = self._build_dataset(
            matches, teams, stats, freeze_after_year=freeze_year
        )
        self._known_teams = set(self.builder.state.keys()) | set(matches["home_team"]) | set(matches["away_team"])
        self._aliases = _load_team_aliases()
        self._lower_lookup = {t.lower(): t for t in self._known_teams}
        self._poisson = PoissonEngine()
        self._history_df: Optional[pd.DataFrame] = None

        self.explainer = V2Explainer(
            self.classifier, self.home_regressor, self.away_regressor,
            self.feature_columns,
        )

        logger.info(
            "V2PredictionAdapter loaded: version=%s mode=%s calibration=%s "
            "features=%d source=%s shap=%s",
            self.model_version, self.mode, self.calibration_method,
            len(self.feature_columns), data_source, self.explainer.is_ready,
        )

    @staticmethod
    def _build_dataset(matches, teams, stats, freeze_after_year):
        from app.ml.v2.features import build_dataset
        return build_dataset(
            matches, teams, stats, groups=("strength", "form", "history", "context"),
            freeze_after_year=freeze_after_year, return_builder=True,
        )

    # -- team name resolution ------------------------------------------------
    def _resolve_team(self, raw: str) -> str:
        name = raw.strip()
        if name in self._known_teams:
            return name
        alias = self._aliases.get(name)
        if alias and alias in self._known_teams:
            return alias
        lower_hit = self._lower_lookup.get(name.lower())
        if lower_hit:
            return lower_hit
        # Unresolved: don't fail the request. The feature builder's
        # accumulator is a defaultdict, so an unrecognised name simply gets
        # neutral BASE_ELO priors — the same graceful-degradation behavior
        # documented for the legacy predictor's unknown-team fallback,
        # just logged explicitly here so it's never a silent guess.
        logger.warning(
            "V2 predictor: team %r not found in the canonical registry "
            "(nor via alias/case-insensitive match); using neutral priors", raw
        )
        return name

    # -- history dataframe (for h2h / insights, shared with legacy path) ----
    async def get_history_dataframe(self) -> pd.DataFrame:
        if self._history_df is None:
            matches, _, _ = load_canonical_from(self.data_source)
            self._history_df = matches.rename(
                columns={"home_goals": "home_score", "away_goals": "away_score"}
            )[["date", "home_team", "away_team", "home_score", "away_score", "tournament"]]
        return self._history_df

    # -- prediction -----------------------------------------------------------
    def predict(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
        explain: bool = True,
    ) -> dict:
        home = self._resolve_team(home_team)
        away = self._resolve_team(away_team)

        row = synthetic_match(
            home, away,
            stage="group_stage", stage_order=1, is_knockout=False,
            date=pd.Timestamp.now(),
            home_is_host=not neutral_venue,
            away_is_host=False,
        )
        feats = self.builder.features_for(row)
        x = np.array([[feats.get(c, np.nan) for c in self.feature_columns]], dtype=np.float32)

        raw_proba = self.classifier.predict_proba(x)
        proba = self.calibrator.transform(raw_proba)[0]
        self._assert_valid_probabilities(proba, home, away)

        home_xg = float(np.clip(self.home_regressor.predict(x)[0], 0.0, None))
        away_xg = float(np.clip(self.away_regressor.predict(x)[0], 0.0, None))

        poisson_result = self._poisson.predict(home_xg=home_xg, away_xg=away_xg)

        # SHAP over the SAME feature vector `x` that produced the prediction —
        # passed in rather than rebuilt, so explanation and prediction inputs
        # cannot drift apart. Returns None (omitted, never fabricated) if the
        # explainer is unavailable.
        explanation = None
        if explain and self.explainer.is_ready:
            predicted_class = ["away_win", "draw", "home_win"][int(np.argmax(proba))]
            shap_block = self.explainer.explain(x, predicted_class)
            if shap_block:
                explanation = {
                    "predicted_outcome": predicted_class,
                    "confidence": round(float(np.max(proba)), 4),
                    "top_positive_features": [
                        {"feature": f["feature"], "readable_name": f["readable_name"],
                         "impact": f["contribution"]}
                        for f in shap_block["top_positive_features"]
                    ],
                    "top_negative_features": [
                        {"feature": f["feature"], "readable_name": f["readable_name"],
                         "impact": f["contribution"]}
                        for f in shap_block["top_negative_features"]
                    ],
                }

        return {
            "home_team": home_team,
            "away_team": away_team,
            "expected_home_goals": home_xg,
            "expected_away_goals": away_xg,
            # Class order (0=away, 1=draw, 2=home) matches the legacy
            # predictor's documented convention exactly — no reordering.
            "away_win_probability": round(float(proba[0]), 4),
            "draw_probability": round(float(proba[1]), 4),
            "home_win_probability": round(float(proba[2]), 4),
            "most_likely_score": poisson_result.most_likely_score,
            "top_scorelines": [
                {"score": s.score, "probability": s.probability}
                for s in poisson_result.top_scorelines
            ],
            "prediction_explanation": explanation or {},
            "confidence_score": round(float(np.max(proba)), 4),
            "model_version": self.model_version,
        }

    @staticmethod
    def _assert_valid_probabilities(proba: np.ndarray, home: str, away: str) -> None:
        """
        Fail loudly rather than silently patch a broken model output. The
        calibrator already renormalises internally (that's correct,
        documented architecture, not a workaround for bad output) — this is
        a defensive boundary check on what actually leaves the model, so a
        future change to the calibrator/model can't silently ship invalid
        probabilities to the API.
        """
        if proba.shape != (3,):
            raise RuntimeError(f"V2 model returned malformed probability shape {proba.shape} for {home} v {away}")
        if not np.all(np.isfinite(proba)) or np.any(proba < 0) or np.any(proba > 1):
            raise RuntimeError(f"V2 model returned out-of-range probabilities {proba.tolist()} for {home} v {away}")
        total = float(proba.sum())
        if abs(total - 1.0) > _PROB_SUM_TOLERANCE:
            raise RuntimeError(
                f"V2 model probabilities sum to {total:.6f}, not 1.0, for {home} v {away}"
            )
