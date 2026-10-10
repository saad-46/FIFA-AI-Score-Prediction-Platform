"""
ModelLoader — selects the prediction pipeline that serves the API.

    PREDICTION_ENGINE=legacy (default) -> the existing behaviour, below, unchanged
    PREDICTION_ENGINE=v3               -> V3PredictionAdapter (app.ml.v3), opt-in

The legacy path:

        USE_V2_MODEL=false                    USE_V2_MODEL=true
                |                                     |
       LegacyPredictionAdapter              V2PredictionAdapter
                |                                     |
     app.ml.models.predictor.MatchPredictor   app.ml.v2 feature engine
     (unmodified — every call forwarded        + XGBoost (E4_plus_context,
      verbatim to the existing singleton)         92 features)
                |                              + temperature calibration
     EXISTING PRODUCTION BEHAVIOR                    |
                                                 V2 PREDICTION

Both adapters implement ``BasePredictionAdapter``, so
``app.services.prediction_service.run_prediction`` calls through one
interface and never branches on the flag itself. The V2 adapter module is
imported lazily, inside ``get_v2()`` — a backend running with the flag off
never imports xgboost's V2 bundle path or touches ``app.ml.v2`` at all, so
USE_V2_MODEL=false cannot be affected by anything V2-related, by construction
rather than by convention.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BasePredictionAdapter(ABC):
    """Common interface implemented by both the legacy and V2 predictors."""

    model_version: str

    @abstractmethod
    async def get_history_dataframe(self) -> pd.DataFrame:
        """
        Match history used for head-to-head stats and insight generation.
        Must contain at minimum the columns: home_team, away_team,
        home_score, away_score.
        """

    @abstractmethod
    def predict(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
    ) -> dict:
        """
        Returns a dict with exactly the keys the legacy predictor already
        produces (see ``app.ml.models.predictor.PredictionOutput.to_dict``):
        expected_home_goals, expected_away_goals, home_win_probability,
        draw_probability, away_win_probability, most_likely_score,
        top_scorelines, prediction_explanation, confidence_score,
        model_version. This is the contract that keeps
        ``prediction_service.run_prediction`` identical regardless of which
        adapter is active.
        """


class LegacyPredictionAdapter(BasePredictionAdapter):
    """
    Thin forwarding wrapper around the existing, unmodified production
    predictor. Every call delegates verbatim to ``app.ml.data.loader`` and
    ``app.ml.models.predictor`` — no legacy logic is reimplemented or altered
    here, so USE_V2_MODEL=false is behaviorally identical to the code path
    that existed before this module did.
    """

    def __init__(self) -> None:
        from app.ml.models.predictor import get_predictor
        self._predictor = get_predictor()
        self.model_version = self._predictor.model_version

    async def get_history_dataframe(self) -> pd.DataFrame:
        from app.ml.data.loader import load_matches_dataframe
        return await load_matches_dataframe()

    def predict(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
    ) -> dict:
        return self._predictor.predict(
            df=df,
            home_team=home_team,
            away_team=away_team,
            tournament=tournament,
            neutral_venue=neutral_venue,
        )


class V3PredictionAdapter(BasePredictionAdapter):
    """
    The V3 pipeline (``app.ml.v3``) behind the same interface.

    It serves from the committed match corpus, not the database, so the
    features a request sees are built by the code and data the model was
    trained with (the bundle's manifest is checked against both on load).
    ``home_team``/``away_team`` are the API's names for team A / team B;
    ``neutral_venue`` decides whether team A actually gets home advantage, and
    at a neutral venue the prediction is exactly order-invariant.

    Raises ``app.ml.v3.inference.ModelUnavailable`` if the bundle cannot be
    validated and ``UnknownTeam`` for a team with no recorded matches. Neither
    is ever papered over with a default prediction.
    """

    def __init__(self) -> None:
        from app.ml.v3.inference import get_service
        self._service = get_service()
        self.model_version = self._service.version
        self._history: Optional[pd.DataFrame] = None

    async def get_history_dataframe(self) -> pd.DataFrame:
        if self._history is None:
            self._history = self._service.history_frame()
        return self._history

    def predict(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
    ) -> dict:
        import math
        from app.ml.v3.inference import tier_for

        from app.ml.v3.inference import UnknownTeam

        svc = self._service
        # The API may be given a FIFA code or a display name ("Korea Republic");
        # the model is keyed by corpus name. Resolve, and refuse what cannot be
        # resolved -- never fall through to a team with no history.
        resolved = []
        for label in (home_team, away_team):
            name = svc.resolve(label)
            if name is None:
                raise UnknownTeam(f"no match history for {label!r}")
            resolved.append(name)
        home_team, away_team = resolved
        out = svc.predict(home_team, away_team, venue=0 if neutral_venue else 1, tier=tier_for(tournament))
        probs = {
            "Home Win": out["team_a_win_probability"],
            "Draw": out["draw_probability"],
            "Away Win": out["team_b_win_probability"],
        }
        outcome = max(probs, key=probs.get)
        # Same meaning as the legacy score: how much match history backs the
        # less-documented side. It is a data-sufficiency measure, not the
        # probability that the pick is right (that is `confidence` below).
        depth = min(svc.engine.n.get(home_team, 0), svc.engine.n.get(away_team, 0))
        confidence_score = min(0.95, 1.0 - math.exp(-depth / 30.0))
        expl = out["explanation"]
        return {
            "expected_home_goals": round(out["expected_goals_a"], 3),
            "expected_away_goals": round(out["expected_goals_b"], 3),
            "home_win_probability": round(probs["Home Win"], 4),
            "draw_probability": round(probs["Draw"], 4),
            "away_win_probability": round(probs["Away Win"], 4),
            "most_likely_score": out["most_likely_score"],
            "top_scorelines": out["top_scorelines"],
            "prediction_explanation": {
                "predicted_outcome": outcome,
                "confidence": round(probs[outcome], 4),
                "top_positive_features": expl["top_positive_features"],
                "top_negative_features": expl["top_negative_features"],
            },
            "confidence_score": round(confidence_score, 4),
            "model_version": out["model_version"],
        }


class ModelLoader:
    """Resolves the active predictor from settings, lazily and once."""

    def __init__(self) -> None:
        self._legacy: Optional[LegacyPredictionAdapter] = None
        self._v2 = None  # type: Optional[BasePredictionAdapter]
        self._v3 = None  # type: Optional[BasePredictionAdapter]

    def get_v3(self) -> BasePredictionAdapter:
        if self._v3 is None:
            self._v3 = V3PredictionAdapter()
        return self._v3

    def get_legacy(self) -> LegacyPredictionAdapter:
        if self._legacy is None:
            self._legacy = LegacyPredictionAdapter()
        return self._legacy

    def get_v2(self) -> BasePredictionAdapter:
        if self._v2 is None:
            from app.ml.v2.model_wrapper import V2PredictionAdapter
            self._v2 = V2PredictionAdapter()
        return self._v2

    def get_active(self) -> BasePredictionAdapter:
        """Selects the adapter per PREDICTION_ENGINE (and, on the legacy
        path, USE_V2_MODEL).

        Reads settings fresh (not module-level) so tests can flip the flag
        via monkeypatch/env without needing a process restart.
        """
        settings = get_settings()
        if settings.PREDICTION_ENGINE.strip().lower() == "v3":
            return self.get_v3()
        if settings.USE_V2_MODEL:
            logger.info("ModelLoader: USE_V2_MODEL=true -> serving v2-calibrated")
            return self.get_v2()
        return self.get_legacy()


_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """Process-wide singleton, mirroring get_predictor()'s existing pattern."""
    global _loader
    if _loader is None:
        _loader = ModelLoader()
    return _loader


def reset_model_loader() -> None:
    """Test-only: drop cached adapters so a flag change takes effect."""
    global _loader
    _loader = None
