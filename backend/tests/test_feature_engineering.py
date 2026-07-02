"""
Tests for the feature engineering pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.ml.features.feature_engineering import (
    compute_team_rolling_stats,
    compute_head_to_head,
    build_feature_vector,
)


@pytest.fixture
def sample_df():
    """Create a sample match DataFrame for testing."""
    dates = pd.date_range(start="2020-01-01", periods=50, freq="7D")
    data = []
    teams = ["Brazil", "Argentina", "Germany", "France"]

    for i, date in enumerate(dates):
        home = teams[i % len(teams)]
        away = teams[(i + 1) % len(teams)]
        data.append({
            "date": date,
            "home_team": home,
            "away_team": away,
            "home_score": np.random.randint(0, 4),
            "away_score": np.random.randint(0, 3),
            "tournament": "Friendly",
            "neutral_venue": False,
        })

    return pd.DataFrame(data)


def test_compute_team_rolling_stats_returns_dict(sample_df):
    """Rolling stats should return a dict with expected keys."""
    stats = compute_team_rolling_stats(
        sample_df,
        team_name="Brazil",
        as_of_date=pd.Timestamp("2021-01-01"),
        is_home=True,
        window=10,
    )
    assert isinstance(stats, dict)
    assert "home_weighted_points_10" in stats
    assert "home_avg_goals_scored_10" in stats
    assert stats["home_avg_goals_scored_10"] >= 0


def test_compute_team_rolling_stats_empty_team(sample_df):
    """Unknown team should return default values."""
    stats = compute_team_rolling_stats(
        sample_df,
        team_name="Unknown FC",
        as_of_date=pd.Timestamp("2021-01-01"),
        is_home=True,
        window=10,
    )
    assert stats["home_weighted_points_10"] == 1.00


def test_compute_head_to_head(sample_df):
    """H2H stats should be computed correctly."""
    h2h = compute_head_to_head(
        sample_df,
        home_team="Brazil",
        away_team="Argentina",
        as_of_date=pd.Timestamp("2021-01-01"),
    )
    assert isinstance(h2h, dict)
    assert "h2h_home_win_rate" in h2h
    assert "h2h_avg_goals" in h2h
    assert 0 <= h2h["h2h_home_win_rate"] <= 1


def test_build_feature_vector_shape(sample_df):
    """Feature vector should be a single-row DataFrame."""
    X = build_feature_vector(
        df=sample_df,
        home_team="Brazil",
        away_team="Argentina",
        match_date=pd.Timestamp("2021-01-01"),
        tournament="Friendly",
        neutral_venue=False,
    )
    assert isinstance(X, pd.DataFrame)
    assert len(X) == 1
    assert len(X.columns) > 10  # Should have many features


def test_build_feature_vector_no_nan(sample_df):
    """Feature vector should not contain NaN values."""
    X = build_feature_vector(
        df=sample_df,
        home_team="Brazil",
        away_team="Argentina",
        match_date=pd.Timestamp("2021-01-01"),
    )
    assert not X.isnull().any().any()
