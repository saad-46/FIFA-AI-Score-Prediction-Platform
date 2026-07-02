"""
FIFA AI — Match Predictor
==========================

Prediction flow
---------------
1. Build feature vector from historical data
2. Predict expected goals (home / away) via XGBRegressor
3. Predict result probabilities via XGBClassifier
4. Run Poisson simulation on expected goals
5. Blend Poisson + classifier probabilities
6. Return structured PredictionOutput

Model bundle keys
-----------------
  home_model      : XGBRegressor
  away_model      : XGBRegressor
  result_model    : XGBClassifier  (classes: 0=Away Win, 1=Draw, 2=Home Win)
  feature_columns : list[str]
  model_version   : str
  trained_at      : str (ISO-8601)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from app.core.config import get_settings
from app.ml.features.feature_engineering import (
    BASE_ELO,
    build_feature_vector,
    build_team_index,
)
from app.ml.poisson import PoissonEngine, Scoreline, get_poisson_engine
from app.ml.calibration import apply_calibration
from app.ml.explainability import PredictionExplainer

logger = logging.getLogger(__name__)
settings = get_settings()

# Blend weights: Poisson captures score distribution, classifier captures
# non-linear result patterns (home advantage, Elo gaps, etc.)
_POISSON_WEIGHT    = 0.60
_CLASSIFIER_WEIGHT = 0.40


# ─── Output dataclass ─────────────────────────────────────────────────────────

@dataclass
class PredictionOutput:
    home_team:              str
    away_team:              str
    expected_home_goals:    float
    expected_away_goals:    float
    home_win_probability:   float
    draw_probability:       float
    away_win_probability:   float
    most_likely_score:      str
    top_scorelines:         list[Scoreline] = field(default_factory=list)
    prediction_explanation: dict = field(default_factory=dict)
    confidence_score:       float = 0.0
    model_version:          str   = "unknown"

    def to_dict(self) -> dict:
        return {
            "home_team":             self.home_team,
            "away_team":             self.away_team,
            "expected_home_goals":   round(self.expected_home_goals, 3),
            "expected_away_goals":   round(self.expected_away_goals, 3),
            "home_win_probability":  round(self.home_win_probability, 4),
            "draw_probability":      round(self.draw_probability, 4),
            "away_win_probability":  round(self.away_win_probability, 4),
            "most_likely_score":     self.most_likely_score,
            "top_scorelines": [
                {"score": s.score, "probability": s.probability}
                for s in self.top_scorelines
            ],
            "confidence_score":      round(self.confidence_score, 4),
            "prediction_explanation": self.prediction_explanation,
            "model_version":         self.model_version,
        }


# ─── Predictor ────────────────────────────────────────────────────────────────

class MatchPredictor:
    """
    Loads trained model bundle and generates match predictions.
    Thread-safe for read operations after load().
    """

    def __init__(self) -> None:
        self.home_model:    Optional[xgb.XGBRegressor]  = None
        self.away_model:    Optional[xgb.XGBRegressor]  = None
        self.result_model:  Optional[xgb.XGBClassifier] = None
        self.scaler         = None
        self.feature_columns: list[str] = []
        self.model_version: str = "unknown"
        self.draw_config:   dict = {}
        self.calibration_bundle: dict = {}
        self._loaded: bool = False
        self._poisson: PoissonEngine = get_poisson_engine()
        self.explainer: Optional[PredictionExplainer] = None

        # Cache of build_team_index(df) keyed by (id(df), len(df)). The
        # historical DataFrame is itself cached with a 6h TTL by
        # load_matches_dataframe(), so the *same* df object is passed into
        # predict() on every request until the next refresh. Rebuilding the
        # team index (a full-history scan) on every single prediction was
        # the dominant cost of predict() — measured at ~93% of per-call
        # latency on a 45k-row history. Keying on id() + len() means a
        # refreshed/mutated df is detected and the index is rebuilt.
        self._team_index_cache: tuple[int, int, dict[str, list[int]]] | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load model bundle from disk. Called once at application startup."""
        model_path  = Path(settings.MODEL_PATH)
        scaler_path = Path(settings.SCALER_PATH)

        if not model_path.exists():
            logger.warning(
                "Model bundle not found at %s. "
                "Run: python -m app.ml.train",
                model_path,
            )
            return

        try:
            bundle = joblib.load(model_path)
            self.home_model      = bundle["home_model"]
            self.away_model      = bundle["away_model"]
            self.result_model    = bundle.get("result_model")
            self.feature_columns = bundle["feature_columns"]
            self.model_version   = bundle.get("model_version", "unknown")
            self.draw_config     = bundle.get("draw_config", {})
            self.calibration_bundle = bundle.get("calibration_bundle", {})

            if scaler_path.exists():
                self.scaler = joblib.load(scaler_path)
            else:
                # Models are trained on standardised features. Without the
                # scaler we would silently feed raw (unscaled) features into
                # models that expect standardised input, producing garbage
                # predictions instead of a clear failure. Fall back to the
                # historical-average path instead (self._loaded stays False).
                logger.error(
                    "Scaler not found at %s — model bundle requires a "
                    "matching scaler. Falling back to historical averages "
                    "until a valid scaler is present.",
                    scaler_path,
                )
                self.home_model = None
                self.away_model = None
                self.result_model = None
                return

            if self.result_model is not None and self.feature_columns:
                self.explainer = PredictionExplainer(self.result_model, self.feature_columns)

            self._loaded = True
            logger.info(
                "Models loaded from %s  (version: %s, features: %d)",
                model_path,
                self.model_version,
                len(self.feature_columns),
            )
        except Exception as exc:
            logger.error("Failed to load models: %s", exc, exc_info=True)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Main prediction ───────────────────────────────────────────────────────

    def predict(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
        match_date: Optional[pd.Timestamp] = None,
    ) -> dict:
        """
        Generate a full match prediction.

        Parameters
        ----------
        df            : Full historical match DataFrame (with Elo pre-computed).
        home_team     : Home team name.
        away_team     : Away team name.
        tournament    : Tournament name (optional).
        neutral_venue : Whether the match is at a neutral venue.
        match_date    : Date of the match (defaults to now).

        Returns
        -------
        dict matching the PredictionOutput.to_dict() schema.
        """
        if match_date is None:
            match_date = pd.Timestamp.now()

        # ── Feature vector ────────────────────────────────────────────────────
        team_index = self._get_team_index(df)
        X = build_feature_vector(
            df=df,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            tournament=tournament,
            neutral_venue=neutral_venue,
            team_index=team_index,
        )
        X = self._align_features(X).fillna(0.0)

        # ── Scale ─────────────────────────────────────────────────────────────
        X_s = self.scaler.transform(X) if self.scaler is not None else X.values

        # ── Expected goals ────────────────────────────────────────────────────
        if self._loaded:
            home_xg = float(np.clip(self.home_model.predict(X_s)[0], 0.05, 9.0))
            away_xg = float(np.clip(self.away_model.predict(X_s)[0], 0.05, 9.0))
        else:
            home_xg, away_xg = self._historical_fallback(df, home_team, away_team, match_date)

        # ── Poisson probabilities ─────────────────────────────────────────────
        poisson_result = self._poisson.predict(home_xg, away_xg)

        # ── Classifier probabilities ──────────────────────────────────────────
        if self._loaded and self.result_model is not None:
            clf_proba = self.result_model.predict_proba(X_s)[0]
            # classes: 0=Away Win, 1=Draw, 2=Home Win
            clf_away_win = float(clf_proba[0])
            clf_draw     = float(clf_proba[1])
            clf_home_win = float(clf_proba[2])

            # Apply probability calibration (fitted during training)
            if self.calibration_bundle:
                cal_proba = apply_calibration(
                    self.calibration_bundle,
                    np.array([[clf_away_win, clf_draw, clf_home_win]]),
                )
                clf_away_win = float(cal_proba[0, 0])
                clf_draw     = float(cal_proba[0, 1])
                clf_home_win = float(cal_proba[0, 2])

            # Apply draw threshold adjustment (optimised during training)
            draw_boost = self.draw_config.get("draw_boost", 1.0)
            if draw_boost > 1.0:
                clf_draw *= draw_boost
                total_clf = clf_home_win + clf_draw + clf_away_win
                clf_home_win /= total_clf
                clf_draw     /= total_clf
                clf_away_win /= total_clf
        else:
            # Fall back to Poisson only
            clf_home_win = poisson_result.home_win_probability
            clf_draw     = poisson_result.draw_probability
            clf_away_win = poisson_result.away_win_probability

        # ── Blend ─────────────────────────────────────────────────────────────
        home_win_prob, draw_prob, away_win_prob = self._blend_probabilities(
            poisson_result.home_win_probability,
            poisson_result.draw_probability,
            poisson_result.away_win_probability,
            clf_home_win,
            clf_draw,
            clf_away_win,
        )

        # ── Confidence ────────────────────────────────────────────────────────
        confidence = self._compute_confidence(df, home_team, away_team, match_date, team_index)

        # ── Explainability ────────────────────────────────────────────────────
        prediction_explanation = None
        if self.explainer and self.explainer.is_ready():
            # Determine predicted class index (0: Away Win, 1: Draw, 2: Home Win)
            probs = [away_win_prob, draw_prob, home_win_prob]
            predicted_class_idx = np.argmax(probs)
            outcomes = ["Away Win", "Draw", "Home Win"]
            predicted_outcome = outcomes[predicted_class_idx]
            
            prediction_explanation = self.explainer.explain(
                X_s, int(predicted_class_idx), predicted_outcome, confidence
            )

        output = PredictionOutput(
            home_team=home_team,
            away_team=away_team,
            expected_home_goals=round(home_xg, 3),
            expected_away_goals=round(away_xg, 3),
            home_win_probability=round(home_win_prob, 4),
            draw_probability=round(draw_prob, 4),
            away_win_probability=round(away_win_prob, 4),
            most_likely_score=poisson_result.most_likely_score,
            top_scorelines=poisson_result.top_scorelines,
            prediction_explanation=prediction_explanation or {},
            confidence_score=round(confidence, 4),
            model_version=self.model_version,
        )
        return output.to_dict()

    # ── Batch prediction (no SHAP, no per-row model calls) ───────────────────

    def predict_batch(
        self,
        df: pd.DataFrame,
        pairs: list[tuple[str, str]],
        tournament: Optional[str] = None,
        neutral_venue: bool = False,
        match_date: Optional[pd.Timestamp] = None,
    ) -> list[dict]:
        """
        Predict xG + win/draw/away probabilities for many (home, away) pairs
        in one vectorised pass through the models, instead of calling
        ``predict()`` once per pair.

        Intended for callers (e.g. the tournament simulator's matchup
        precompute step) that need only the core numeric outputs — this
        skips SHAP explainability and the confidence-score computation,
        which are the two most expensive per-call steps in ``predict()``
        and aren't consumed by those callers. Feature-vector construction
        still runs once per pair (it's cheap once team_index is cached),
        but scaling and model inference run once for the whole batch —
        XGBoost's batch predict cost is close to O(1) per extra row, so
        this turns N sequential model round-trips into 1.

        Returns
        -------
        list[dict] in the same order as ``pairs``, each with the subset of
        PredictionOutput fields needed for matchup caching: home_team,
        away_team, expected_home_goals, expected_away_goals,
        home_win_probability, draw_probability, away_win_probability.
        """
        if not pairs:
            return []

        if match_date is None:
            match_date = pd.Timestamp.now()

        team_index = self._get_team_index(df)

        # ── Build all feature vectors ─────────────────────────────────────────
        # team_stats_cache memoises each team's own rolling-stats/rest-days/Elo
        # (which don't depend on the opponent) across the whole batch, since
        # match_date is fixed for every pair here. Only head-to-head features
        # are genuinely pair-specific and always recomputed. This is what
        # turns an O(pairs * teams_per_pair) feature-engineering cost into
        # roughly O(pairs + teams) for a full round-robin precompute.
        team_stats_cache: dict = {}
        rows = []
        for home_team, away_team in pairs:
            X = build_feature_vector(
                df=df,
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                tournament=tournament,
                neutral_venue=neutral_venue,
                team_index=team_index,
                team_stats_cache=team_stats_cache,
            )
            rows.append(X)
        X_all = pd.concat(rows, ignore_index=True)
        X_all = self._align_features(X_all).fillna(0.0)

        # ── Scale (single call for the whole batch) ───────────────────────────
        X_s = self.scaler.transform(X_all) if self.scaler is not None else X_all.values

        # ── Expected goals (single batch call per model) ──────────────────────
        if self._loaded:
            home_xg_arr = np.clip(self.home_model.predict(X_s), 0.05, 9.0)
            away_xg_arr = np.clip(self.away_model.predict(X_s), 0.05, 9.0)
        else:
            home_xg_arr = np.empty(len(pairs))
            away_xg_arr = np.empty(len(pairs))
            for i, (home_team, away_team) in enumerate(pairs):
                h, a = self._historical_fallback(df, home_team, away_team, match_date)
                home_xg_arr[i] = h
                away_xg_arr[i] = a

        # ── Classifier probabilities (single batch call) ──────────────────────
        if self._loaded and self.result_model is not None:
            clf_proba = self.result_model.predict_proba(X_s)  # (n, 3): away/draw/home

            if self.calibration_bundle:
                clf_proba = apply_calibration(self.calibration_bundle, clf_proba)

            clf_away_win = clf_proba[:, 0].copy()
            clf_draw     = clf_proba[:, 1].copy()
            clf_home_win = clf_proba[:, 2].copy()

            draw_boost = self.draw_config.get("draw_boost", 1.0)
            if draw_boost > 1.0:
                clf_draw = clf_draw * draw_boost
                total_clf = clf_home_win + clf_draw + clf_away_win
                clf_home_win = clf_home_win / total_clf
                clf_draw     = clf_draw / total_clf
                clf_away_win = clf_away_win / total_clf
        else:
            clf_home_win = None  # filled in per-row below from Poisson
            clf_draw = None
            clf_away_win = None

        # ── Poisson + blend (per-row; PoissonEngine has no batch API, but
        #    each call is ~0.3ms so this isn't the bottleneck) ────────────────
        results: list[dict] = []
        for i, (home_team, away_team) in enumerate(pairs):
            home_xg = float(home_xg_arr[i])
            away_xg = float(away_xg_arr[i])
            poisson_result = self._poisson.predict(home_xg, away_xg)

            if clf_home_win is not None:
                c_home = float(clf_home_win[i])
                c_draw = float(clf_draw[i])
                c_away = float(clf_away_win[i])
            else:
                c_home = poisson_result.home_win_probability
                c_draw = poisson_result.draw_probability
                c_away = poisson_result.away_win_probability

            home_win_prob, draw_prob, away_win_prob = self._blend_probabilities(
                poisson_result.home_win_probability,
                poisson_result.draw_probability,
                poisson_result.away_win_probability,
                c_home, c_draw, c_away,
            )

            results.append({
                "home_team": home_team,
                "away_team": away_team,
                "expected_home_goals": round(home_xg, 3),
                "expected_away_goals": round(away_xg, 3),
                "home_win_probability": round(home_win_prob, 4),
                "draw_probability": round(draw_prob, 4),
                "away_win_probability": round(away_win_prob, 4),
            })

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_team_index(self, df: pd.DataFrame) -> dict[str, list[int]]:
        """
        Return build_team_index(df), reusing the cached result when df is the
        same object (and same length) as the last call. See
        ``self._team_index_cache`` for why this matters.
        """
        cache_key = (id(df), len(df))
        if self._team_index_cache is not None and self._team_index_cache[:2] == cache_key:
            return self._team_index_cache[2]
        team_index = build_team_index(df)
        self._team_index_cache = (cache_key[0], cache_key[1], team_index)
        return team_index

    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Ensure feature columns match training order, filling missing with 0."""
        if not self.feature_columns:
            return X
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0.0
        return X[self.feature_columns]

    @staticmethod
    def _blend_probabilities(
        p_home_win: float, p_draw: float, p_away_win: float,
        c_home_win: float, c_draw: float, c_away_win: float,
    ) -> tuple[float, float, float]:
        """
        Blend Poisson and classifier probabilities, then re-normalise.
        """
        pw = _POISSON_WEIGHT
        cw = _CLASSIFIER_WEIGHT
        h = pw * p_home_win + cw * c_home_win
        d = pw * p_draw     + cw * c_draw
        a = pw * p_away_win + cw * c_away_win
        total = h + d + a
        if total <= 0:
            return 1 / 3, 1 / 3, 1 / 3
        return h / total, d / total, a / total

    def _historical_fallback(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        match_date: Optional[pd.Timestamp] = None,
    ) -> tuple[float, float]:
        """Use historical averages when models are not loaded."""
        past = df[df["date"] < match_date] if match_date is not None else df
        home_matches = past[past["home_team"] == home_team].dropna(subset=["home_score"])
        away_matches = past[past["away_team"] == away_team].dropna(subset=["away_score"])
        home_xg = float(home_matches["home_score"].mean()) if len(home_matches) > 0 else 1.30
        away_xg = float(away_matches["away_score"].mean()) if len(away_matches) > 0 else 1.10
        return home_xg, away_xg

    def _compute_confidence(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        match_date: pd.Timestamp,
        team_index: Optional[dict[str, list[int]]] = None,
    ) -> float:
        """
        Confidence score based on data availability.
        Sigmoid-like: 50+ matches per team → ~0.85 confidence.

        Only matches strictly before ``match_date`` are counted, consistent
        with the leakage-safe "as of this date" convention used throughout
        feature engineering — otherwise a prediction for a past/mid-history
        date would have its confidence inflated by matches that haven't
        happened yet relative to that date.

        When ``team_index`` is supplied, counts are derived from the
        pre-built team->row-index mapping instead of scanning the full
        DataFrame with boolean masks — avoids an O(n) pass per prediction.
        """
        if team_index is not None:
            home_count = sum(
                1 for i in team_index.get(home_team, []) if df.at[i, "date"] < match_date
            )
            away_count = sum(
                1 for i in team_index.get(away_team, []) if df.at[i, "date"] < match_date
            )
        else:
            past = df[df["date"] < match_date]
            home_count = int(
                ((past["home_team"] == home_team) | (past["away_team"] == home_team))
                .sum()
            )
            away_count = int(
                ((past["home_team"] == away_team) | (past["away_team"] == away_team))
                .sum()
            )
        min_count = min(home_count, away_count)
        base = 1.0 - np.exp(-min_count / 30.0)
        model_bonus = 0.10 if self._loaded else 0.0
        return min(0.95, base * 0.85 + model_bonus)


# ─── Singleton ────────────────────────────────────────────────────────────────

_predictor: Optional[MatchPredictor] = None


def get_predictor() -> MatchPredictor:
    """Return the shared MatchPredictor instance (lazy init + load)."""
    global _predictor
    if _predictor is None:
        _predictor = MatchPredictor()
        _predictor.load()
    return _predictor
