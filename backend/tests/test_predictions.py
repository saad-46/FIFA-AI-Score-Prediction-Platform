"""
Tests for the prediction endpoint.
"""

import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.schemas.prediction import HeadToHeadStats
from app.services.prediction_service import _generate_insights, run_prediction


@pytest.fixture
def mock_prediction_result():
    return {
        "prediction_id": "test-uuid-1234",
        "home_team": "Brazil",
        "away_team": "Argentina",
        "predicted_home_score": 2,
        "predicted_away_score": 1,
        "home_win_probability": 0.52,
        "draw_probability": 0.24,
        "away_win_probability": 0.24,
        "expected_home_goals": 1.85,
        "expected_away_goals": 0.92,
        "confidence_score": 0.78,
        "model_version": "1.0.0",
        "most_likely_score": "2-1",
        "prediction_explanation": {
            "predicted_outcome": "Home Win",
            "confidence": 0.78,
            "top_positive_features": [],
            "top_negative_features": []
        },
        "insights": [],
        "head_to_head": {
            "total_matches": 45,
            "home_team_wins": 18,
            "away_team_wins": 16,
            "draws": 11,
            "home_team_goals": 72,
            "away_team_goals": 68,
        },
        "created_at": "2025-01-01T00:00:00",
    }


@pytest.mark.asyncio
async def test_predict_match_success(mock_prediction_result):
    """Test successful match prediction."""
    with patch(
        "app.api.v1.endpoints.predictions.run_prediction",
        new_callable=AsyncMock,
        return_value=MagicMock(**mock_prediction_result),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/predictions/predict",
                json={"home_team": "Brazil", "away_team": "Argentina"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["home_team"] == "Brazil"
    assert data["away_team"] == "Argentina"
    assert 0 <= data["home_win_probability"] <= 1
    assert 0 <= data["draw_probability"] <= 1
    assert 0 <= data["away_win_probability"] <= 1


@pytest.mark.asyncio
async def test_predict_same_teams_rejected():
    """Test that same home/away team is rejected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/predictions/predict",
            json={"home_team": "Brazil", "away_team": "Brazil"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_missing_team_rejected():
    """Test that missing team name is rejected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/predictions/predict",
            json={"home_team": "Brazil"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def _strong_home_team_df(home_team: str, away_team: str) -> pd.DataFrame:
    """A DataFrame where home_team wins >55% of its home matches, so the
    'strong at home' insight would fire if neutral_venue were (incorrectly)
    treated as False."""
    rows = []
    for i in range(8):
        rows.append({
            "home_team": home_team, "away_team": f"Filler{i}",
            "home_score": 3, "away_score": 0, "tournament": "Friendly",
        })
    rows.append({
        "home_team": away_team, "away_team": home_team,
        "home_score": 1, "away_score": 1, "tournament": "Friendly",
    })
    return pd.DataFrame(rows)


def test_generate_insights_suppresses_home_advantage_when_neutral_venue():
    """
    Regression test: PredictionOutput.to_dict() (predictor.py) never emits a
    "neutral_venue" key, so previously _generate_insights read
    pred.get("neutral_venue", False) and always got False — meaning the home
    advantage insight fired even when the caller explicitly requested a
    neutral-venue match. _generate_insights now takes neutral_venue as an
    explicit parameter sourced from the original request instead.
    """
    df = _strong_home_team_df("Brazil", "Argentina")
    pred = {"expected_home_goals": 1.5, "expected_away_goals": 1.0, "confidence_score": 0.8}
    h2h = HeadToHeadStats(
        total_matches=0, home_team_wins=0, away_team_wins=0,
        draws=0, home_team_goals=0, away_team_goals=0,
    )

    # Neutral venue requested: home-advantage insight must NOT appear.
    neutral_insights = _generate_insights(df, "Brazil", "Argentina", pred, h2h, neutral_venue=True)
    assert not any("strong at home" in i.title for i in neutral_insights)

    # Non-neutral (default) venue: home-advantage insight SHOULD appear given
    # the lopsided home record baked into the fixture data above.
    home_insights = _generate_insights(df, "Brazil", "Argentina", pred, h2h, neutral_venue=False)
    assert any("strong at home" in i.title for i in home_insights)


# ─── Unknown / unrecognized team name handling ───────────────────────────────

def _small_history_df() -> pd.DataFrame:
    rows = []
    for i in range(6):
        rows.append({
            "date": pd.Timestamp("2021-01-01") + pd.Timedelta(days=7 * i),
            "home_team": "Brazil", "away_team": f"Filler{i}",
            "home_score": 2, "away_score": 1, "tournament": "Friendly",
            "neutral_venue": False,
        })
    return pd.DataFrame(rows)


@pytest.mark.asyncio
async def test_run_prediction_with_unknown_team_does_not_raise(legacy_engine):
    """Legacy engine only (PREDICTION_ENGINE=legacy). The V3 engine refuses a
    team it has no matches for -- see tests/test_v3_api.py -- because this
    fallback is what let 47 of 48 World Cup teams be simulated as blanks.

    A team name with zero historical matches (e.g. a typo, or a team not
    yet in the reference data) must not crash the prediction pipeline end to
    end — feature engineering falls back to defaults for unknown teams (see
    test_feature_engineering.py's 'Unknown FC' case and
    test_predictor.py's unknown-team predictor tests), and run_prediction
    should surface a normal (if low-confidence) PredictionResult."""
    df = _small_history_df()

    # Patched at its true source rather than at
    # app.services.prediction_service (which no longer imports it at module
    # level since the V2 ModelLoader refactor — run_prediction now goes
    # through app.ml.model_loader.LegacyPredictionAdapter, which does a
    # function-local `from app.ml.data.loader import load_matches_dataframe`
    # and so still picks up this patch; USE_V2_MODEL defaults to false, so
    # this exercises the legacy path exactly as before).
    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        result = await run_prediction(
            home_team="Atlantis FC", away_team="Wakanda United"
        )

    assert result.home_team == "Atlantis FC"
    assert result.away_team == "Wakanda United"
    assert 0.0 <= result.home_win_probability <= 1.0
    assert 0.0 <= result.draw_probability <= 1.0
    assert 0.0 <= result.away_win_probability <= 1.0
    assert result.head_to_head.total_matches == 0


@pytest.mark.asyncio
async def test_predict_endpoint_with_unknown_teams_returns_200(legacy_engine):
    """Legacy engine only; the V3 engine answers 422 (tests/test_v3_api.py).

    End-to-end through the HTTP endpoint: unrecognized (but validly
    formatted) team names should not be rejected by validation and should
    not 500 — the predictor's fallback path handles them."""
    df = _small_history_df()

    with patch(
        "app.ml.data.loader.load_matches_dataframe",
        new_callable=AsyncMock,
        return_value=df,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/predictions/predict",
                json={"home_team": "Atlantis FC", "away_team": "Wakanda United"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["home_team"] == "Atlantis FC"
    assert data["away_team"] == "Wakanda United"
