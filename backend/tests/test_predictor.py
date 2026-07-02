"""
Unit tests for app/ml/models/predictor.py — focused on the graceful-fallback
paths: missing model bundle file, corrupted model bundle file, and
unrecognized/unknown team names at prediction time. These are the "predictor
falls back gracefully" scenarios called out in the audit mandate (Phase 12
edge cases), rather than the scaler/NaN bugs already covered by the ML
engineer's earlier pass.
"""

import os
import tempfile

import pandas as pd
import pytest
from unittest.mock import patch

import app.ml.models.predictor as predictor_mod
from app.ml.models.predictor import MatchPredictor


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
        "home_team": ["Brazil", "Argentina", "Brazil"],
        "away_team": ["Argentina", "Brazil", "Germany"],
        "home_score": [2, 1, 3],
        "away_score": [1, 1, 0],
        "tournament": ["Friendly", "Friendly", "Friendly"],
        "neutral_venue": [False, False, False],
    })


# ─── Missing model bundle file ────────────────────────────────────────────────

def test_load_with_missing_model_file_leaves_predictor_unloaded():
    """If the model bundle file doesn't exist on disk, load() must log and
    return rather than raising, leaving is_loaded False so predict() takes
    the historical-average fallback path instead of crashing."""
    predictor = MatchPredictor()

    with patch.object(predictor_mod.settings, "MODEL_PATH", "nonexistent/path/model.pkl"):
        predictor.load()  # must not raise

    assert predictor.is_loaded is False
    assert predictor.home_model is None
    assert predictor.away_model is None


def test_predict_falls_back_to_historical_averages_when_not_loaded(sample_df):
    """With no model loaded, predict() should still return a complete,
    well-formed prediction dict using the Poisson-only / historical-average
    fallback path, not raise."""
    predictor = MatchPredictor()
    assert predictor.is_loaded is False

    result = predictor.predict(df=sample_df, home_team="Brazil", away_team="Argentina")

    assert result["home_team"] == "Brazil"
    assert result["away_team"] == "Argentina"
    assert result["expected_home_goals"] > 0
    assert result["expected_away_goals"] > 0
    assert 0.0 <= result["home_win_probability"] <= 1.0
    assert 0.0 <= result["draw_probability"] <= 1.0
    assert 0.0 <= result["away_win_probability"] <= 1.0
    prob_sum = (
        result["home_win_probability"]
        + result["draw_probability"]
        + result["away_win_probability"]
    )
    assert prob_sum == pytest.approx(1.0, abs=1e-3)
    # Fallback path never ran SHAP -> explanation stays empty, not an error.
    assert result["prediction_explanation"] == {}
    assert result["model_version"] == "unknown"


# ─── Corrupted model bundle file ──────────────────────────────────────────────

def test_load_with_corrupted_model_file_leaves_predictor_unloaded():
    """A file that exists at MODEL_PATH but isn't a valid joblib/pickle
    bundle must be caught by load()'s broad exception handler rather than
    propagating and crashing the app at startup."""
    predictor = MatchPredictor()

    fd, tmp_path = tempfile.mkstemp(suffix=".pkl", dir="D:/")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b"this is not a valid joblib/pickle file")

        with patch.object(predictor_mod.settings, "MODEL_PATH", tmp_path):
            predictor.load()  # must not raise

        assert predictor.is_loaded is False
    finally:
        os.remove(tmp_path)


# ─── Unknown / unrecognized team names ────────────────────────────────────────

def test_predict_with_unknown_teams_does_not_raise(sample_df):
    """Teams with zero history in df should not crash predict() — the
    feature-engineering layer's per-team defaults (see
    compute_team_rolling_stats' 'Unknown FC' handling in
    test_feature_engineering.py) should carry through end-to-end."""
    predictor = MatchPredictor()

    result = predictor.predict(df=sample_df, home_team="Wakanda", away_team="Narnia")

    assert result["home_team"] == "Wakanda"
    assert result["away_team"] == "Narnia"
    assert result["expected_home_goals"] > 0
    assert result["expected_away_goals"] > 0
    prob_sum = (
        result["home_win_probability"]
        + result["draw_probability"]
        + result["away_win_probability"]
    )
    assert prob_sum == pytest.approx(1.0, abs=1e-3)
    # No history for either team -> lowest-confidence bucket.
    assert result["confidence_score"] == pytest.approx(0.0, abs=1e-6)


def test_predict_with_one_known_one_unknown_team(sample_df):
    """Mixed case: a real team with history vs. a team with none."""
    predictor = MatchPredictor()

    result = predictor.predict(df=sample_df, home_team="Brazil", away_team="Wakanda")

    assert result["expected_home_goals"] > 0
    assert result["expected_away_goals"] > 0
    prob_sum = (
        result["home_win_probability"]
        + result["draw_probability"]
        + result["away_win_probability"]
    )
    assert prob_sum == pytest.approx(1.0, abs=1e-3)


def test_predict_batch_with_unknown_teams_does_not_raise(sample_df):
    """The batch prediction path (used by the tournament simulator) must
    also tolerate unknown teams without raising."""
    predictor = MatchPredictor()

    results = predictor.predict_batch(
        df=sample_df,
        pairs=[("Wakanda", "Narnia"), ("Brazil", "Atlantis")],
    )

    assert len(results) == 2
    for r in results:
        assert r["expected_home_goals"] > 0
        assert r["expected_away_goals"] > 0
