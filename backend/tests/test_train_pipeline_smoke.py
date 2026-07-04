"""
Smoke test for app/ml/train.py's data-loading + feature-matrix pipeline.

This is deliberately NOT a full retrain (that's slow and is the ML
Engineering wave's job, already covered by MODEL_EVALUATION.md's reported
metrics) — it just proves the pipeline can load the new processed CSV
(app/data/processed/matches_historical.csv, the Data Engineering wave's
merged WC-only corpus) and build a real feature matrix out of a small slice
of it without crashing. Regression target: a future change to loader paths,
CSV schema, or build_training_dataset() that silently breaks the training
entry point before any model-fitting code even runs.
"""

import pandas as pd
import pytest

from app.ml.train import load_data, build_training_dataset, MIN_HISTORY


def test_load_data_reads_processed_matches_historical_csv():
    """load_data() must find and parse the real processed CSV, returning only
    completed matches (Scheduled 2026 fixtures excluded), sorted by date."""
    df = load_data()

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    for col in ("date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral_venue"):
        assert col in df.columns

    # No Scheduled (unplayed) rows should have slipped through.
    assert df["home_score"].notna().all()
    assert df["away_score"].notna().all()

    # Sorted chronologically, no shuffling.
    assert df["date"].is_monotonic_increasing


def test_build_training_dataset_builds_feature_matrix_from_small_slice():
    """build_training_dataset() must run end-to-end on a small slice of the
    real data (fast: a few dozen rows) and produce a non-empty, NaN-free-once-
    filled feature matrix aligned 1:1 with its three target vectors and the
    match-dates series — i.e. the exact object shapes train_models() expects,
    without needing a full ~400-row run or any actual XGBoost fitting."""
    df = load_data()
    # Small slice so this stays a fast smoke test rather than a full retrain;
    # min_history=10 (smaller than the module default) so a modest slice
    # still yields several real feature rows for a meaningful assertion.
    small_slice = df.iloc[:40].reset_index(drop=True)

    X, y_home, y_away, y_result, match_dates = build_training_dataset(
        small_slice, min_history=10
    )

    assert isinstance(X, pd.DataFrame)
    assert len(X) > 0
    assert len(X) == len(y_home) == len(y_away) == len(y_result) == len(match_dates)

    # Targets must be well-formed.
    assert y_home.ge(0).all()
    assert y_away.ge(0).all()
    assert set(y_result.unique()).issubset({0, 1, 2})

    # Feature matrix should have many engineered columns (Elo, rolling stats,
    # FIFA ranking, knockout experience, etc. — see feature_engineering.py),
    # not just a handful of raw fields.
    assert X.shape[1] > 50


def test_build_training_dataset_respects_min_history_warmup():
    """Rows before `min_history` must be skipped entirely (not enough prior
    match history yet for rolling-window features to be meaningful) — the
    returned feature matrix must have strictly fewer rows than the input
    slice whenever min_history > 0."""
    df = load_data()
    small_slice = df.iloc[:40].reset_index(drop=True)

    X, y_home, _, _, _ = build_training_dataset(small_slice, min_history=15)

    assert len(X) <= len(small_slice) - 15
    assert len(X) == len(y_home)


def test_module_default_min_history_is_reasonable():
    """Sanity check on the MIN_HISTORY constant train.py's main() actually
    uses — should be a small positive warmup, not accidentally 0 (no warmup
    at all) or larger than a full World Cup (55 matches), which would silently
    discard entire tournaments' worth of the small WC-only corpus."""
    assert 0 < MIN_HISTORY < 55
