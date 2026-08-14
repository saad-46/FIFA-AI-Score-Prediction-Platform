"""
ModelLoader — feature-flagged selection between the legacy production
predictor and the V2 calibrated predictor.

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


class ModelLoader:
    """Resolves the active predictor from the feature flag, lazily and once."""

    def __init__(self) -> None:
        self._legacy: Optional[LegacyPredictionAdapter] = None
        self._v2 = None  # type: Optional[BasePredictionAdapter]

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
        """Selects the adapter per the current USE_V2_MODEL setting.

        Reads settings fresh (not module-level) so tests can flip the flag
        via monkeypatch/env without needing a process restart.
        """
        settings = get_settings()
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
