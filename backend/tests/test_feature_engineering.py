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
    compute_dynamic_elo,
    BASE_ELO,
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


# ─── Regression: Elo-at-inference bug ────────────────────────────────────────
#
# The live prediction path used to call build_feature_vector() on a raw
# DataFrame that never had home_elo/away_elo/elo_difference columns computed
# (compute_dynamic_elo() was only ever called at training time). Because
# build_feature_vector()'s Elo lookup reads those columns straight off the
# given df and silently falls back to BASE_ELO for both teams when they're
# absent, every served prediction's elo_difference was a constant 0.0 even
# for lopsided matchups. The fix (app/ml/data/loader.py) now runs
# compute_dynamic_elo(df) once when building the cached DataFrame that both
# the predictor and the tournament simulator consume, closing the train/serve
# skew. These tests pin that down directly against build_feature_vector.

def _lopsided_elo_df() -> pd.DataFrame:
    """Build a small history where one team (Brazil) has strong results and
    another (Chile) has weak ones, plus several other pairings, so that
    compute_dynamic_elo() produces genuinely different, non-BASE_ELO ratings
    per team rather than everyone converging to the same value."""
    rows = []
    date = pd.Timestamp("2020-01-01")
    strong, weak = "Brazil", "Chile"
    others = ["Peru", "Ecuador", "Bolivia", "Uruguay"]

    # Brazil beats a rotating cast of opponents repeatedly (builds Elo up).
    for i in range(15):
        rows.append({
            "date": date + pd.Timedelta(days=7 * i),
            "home_team": strong, "away_team": others[i % len(others)],
            "home_score": 3, "away_score": 0,
            "tournament": "FIFA World Cup", "neutral_venue": True,
        })

    # Chile loses repeatedly to a rotating cast of opponents (Elo drops).
    for i in range(15):
        rows.append({
            "date": date + pd.Timedelta(days=7 * i + 3),
            "home_team": others[i % len(others)], "away_team": weak,
            "home_score": 3, "away_score": 0,
            "tournament": "FIFA World Cup", "neutral_venue": True,
        })

    return pd.DataFrame(rows)


def test_build_feature_vector_elo_difference_is_zero_without_precomputed_elo():
    """Pins down the OLD buggy behaviour as a contrast case: if the caller
    forgets to run compute_dynamic_elo() first (the exact bug), home_elo/
    away_elo aren't present on the df and the lookup falls back to BASE_ELO
    for both sides, so elo_difference is always exactly 0.0 regardless of
    how lopsided the two teams' real records are."""
    df = _lopsided_elo_df()  # note: NOT run through compute_dynamic_elo()

    X = build_feature_vector(
        df=df,
        home_team="Brazil",
        away_team="Chile",
        match_date=pd.Timestamp("2021-06-01"),
    )

    assert X["elo_difference"].iloc[0] == 0.0
    assert X["home_elo"].iloc[0] == BASE_ELO
    assert X["away_elo"].iloc[0] == BASE_ELO


def test_build_feature_vector_elo_difference_nonzero_and_varying_with_precomputed_elo():
    """The fixed behaviour: once compute_dynamic_elo() has been run over the
    history (as app/ml/data/loader.py's load_matches_dataframe() now does
    before caching), build_feature_vector() picks up real, divergent Elo
    ratings for a genuinely lopsided matchup — elo_difference must be
    materially non-zero, not the constant-0.0 fallback."""
    df = compute_dynamic_elo(_lopsided_elo_df())

    X = build_feature_vector(
        df=df,
        home_team="Brazil",
        away_team="Chile",
        match_date=pd.Timestamp("2021-06-01"),
    )

    elo_diff = X["elo_difference"].iloc[0]
    assert elo_diff != 0.0
    assert elo_diff > 50  # Brazil (all wins) must clearly outrate Chile (all losses)
    assert X["home_elo"].iloc[0] != BASE_ELO
    assert X["away_elo"].iloc[0] != BASE_ELO

    # And it genuinely varies by matchup — a neutral pairing of two mid-table
    # teams should produce a different (much smaller magnitude) elo_difference
    # than the Brazil/Chile extreme, proving this isn't a different hardcoded
    # constant.
    X_other = build_feature_vector(
        df=df,
        home_team="Peru",
        away_team="Ecuador",
        match_date=pd.Timestamp("2021-06-01"),
    )
    other_diff = X_other["elo_difference"].iloc[0]
    assert other_diff != elo_diff
