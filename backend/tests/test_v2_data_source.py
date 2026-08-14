"""
V2 data-source tests: CSV vs Supabase equivalence.

The feature engine must not be able to tell which source it was given —
otherwise "switching to Supabase" silently becomes "changing the model's
inputs". Tests that need a live database are skipped (not failed) when
DATABASE_URL is absent, so the suite still runs offline; the CSV-side
structural tests always run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.ml.v2.data_source import (
    CANON_DIR, load_canonical_from, load_from_csv, verify_consistency,
)

_HAS_DB = bool(os.environ.get("DATABASE_URL")) or (
    Path(__file__).resolve().parents[1] / ".env"
).exists()
requires_db = pytest.mark.skipif(not _HAS_DB, reason="no DATABASE_URL configured")


def test_csv_source_loads():
    matches, teams, stats = load_from_csv()
    assert len(matches) == 1069
    assert len(teams) == 89
    assert len(stats) == 208


def test_csv_source_has_expected_schema():
    matches, teams, stats = load_from_csv()
    for col in ("match_id", "date", "year", "home_team", "away_team",
                "home_goals", "away_goals", "stage", "is_knockout"):
        assert col in matches.columns
    for col in ("team_name", "is_wc2026_team", "elo_rating_pre_wc2026"):
        assert col in teams.columns


def test_csv_decisive_score_rule():
    """home_goals must be extra-time score where played, else full-time —
    the same rule the canonical build applied."""
    matches, _, _ = load_from_csv()
    with_et = matches[matches["home_score_et"].notna()]
    assert len(with_et) > 0
    assert (with_et["home_goals"] == with_et["home_score_et"]).all()
    no_et = matches[matches["home_score_et"].isna() & matches["home_score_ft"].notna()]
    assert (no_et["home_goals"] == no_et["home_score_ft"]).all()


def test_unknown_source_rejected():
    with pytest.raises(ValueError, match="unknown V2 data source"):
        load_canonical_from("redis")  # type: ignore[arg-type]


@requires_db
def test_supabase_source_loads():
    matches, teams, stats = load_canonical_from("supabase")
    assert len(matches) == 1069
    assert len(teams) == 89
    assert len(stats) == 208


@requires_db
def test_supabase_matches_csv_row_counts():
    csv_m, csv_t, csv_s = load_from_csv()
    sb_m, sb_t, sb_s = load_canonical_from("supabase")
    assert len(csv_m) == len(sb_m)
    assert len(csv_t) == len(sb_t)
    assert len(csv_s) == len(sb_s)


@requires_db
def test_supabase_and_csv_feature_states_are_identical():
    """
    The pass/fail gate for switching production inference to Supabase.

    Equal row counts with different feature values would be a silent model
    change, so this compares actual built feature vectors, not just counts.
    """
    report = verify_consistency(sample_size=25)
    assert report["passed"], report["checks"]
    assert report["checks"]["all_feature_values"]["mismatched_values"] == 0
    assert report["checks"]["feature_columns_identical"]["match"] is True


@requires_db
def test_supabase_consistency_covers_counts_and_ranges():
    report = verify_consistency(sample_size=5)
    checks = report["checks"]
    for name in ("match_rows", "team_rows", "stat_rows", "distinct_teams",
                 "distinct_tournaments", "earliest_date", "latest_date",
                 "wc2026_teams", "per_tournament_counts"):
        assert name in checks, f"missing consistency check: {name}"
        assert checks[name]["match"] is True, f"{name} differs: {checks[name]}"
