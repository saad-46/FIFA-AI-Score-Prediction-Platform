"""
Team identity in the tournament simulator (legacy engine).

The "USA wins the World Cup" forecast came from a vocabulary mismatch: the
simulator works in FIFA codes ("BRA"), the predictor's match history is keyed
by team name ("Brazil"), and codes were passed straight through. "USA" is the
only code that is also a name, so it was the only team with any history and
the other 47 were interchangeable blanks.

These tests pin the fix at that boundary: the predictor is asked about names,
the simulator keeps its codes, and every one of the 48 teams is a team the
predictor's history actually contains.
"""

from __future__ import annotations

from itertools import combinations
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.data.fifa_2026 import get_groups_as_team_codes
from app.ml import tournament_simulator as ts


def _codes() -> list[str]:
    return [t for g in get_groups_as_team_codes().values() for t in g]


def _recording_predictor():
    asked: list[tuple[str, str]] = []

    def predict_batch(df, pairs, **kwargs):
        asked.extend(pairs)
        return [{"home_team": a, "away_team": b, "expected_home_goals": 1.2, "expected_away_goals": 1.0,
                 "home_win_probability": 0.45, "draw_probability": 0.25, "away_win_probability": 0.30}
                for a, b in pairs]

    predictor = MagicMock()
    predictor.is_loaded = True
    predictor.predict_batch = predict_batch
    return predictor, asked


def test_reference_maps_all_48_codes_to_distinct_names():
    name_to_code = ts._load_name_to_code_map()
    codes = _codes()
    assert len(codes) == len(set(codes)) == 48
    code_to_name = {c: n for n, c in name_to_code.items()}
    assert set(codes) <= set(code_to_name), sorted(set(codes) - set(code_to_name))
    assert len({code_to_name[c] for c in codes}) == 48


def test_predictor_is_asked_about_team_names_not_codes():
    predictor, asked = _recording_predictor()
    sim = ts.TournamentSimulator(predictor, pd.DataFrame(), use_real_results=False)
    codes = _codes()
    sim._precompute_matchups(codes)

    code_to_name = {c: n for n, c in ts._load_name_to_code_map().items()}
    expected = [(code_to_name[a], code_to_name[b]) for a, b in combinations(codes, 2)]
    assert asked == expected
    asked_names = {t for pair in asked for t in pair}
    assert "Brazil" in asked_names and "Spain" in asked_names
    assert "BRA" not in asked_names and "ESP" not in asked_names


def test_simulator_keeps_its_own_codes_in_the_matchup_cache():
    predictor, _ = _recording_predictor()
    sim = ts.TournamentSimulator(predictor, pd.DataFrame(), use_real_results=False)
    codes = _codes()
    sim._precompute_matchups(codes)
    assert len(sim.matchup_cache) == 48 * 47 // 2
    for a, b in combinations(codes, 2):
        entry = sim.matchup_cache[sim._get_matchup_key(a, b)]
        assert (entry["home_team"], entry["away_team"]) == (a, b)


def test_labels_that_are_not_fifa_codes_pass_through_unchanged():
    predictor, asked = _recording_predictor()
    sim = ts.TournamentSimulator(predictor, pd.DataFrame(), use_real_results=False)
    sim._precompute_matchups(["Team0_0", "Team0_1", "Team0_2"])
    assert asked == [("Team0_0", "Team0_1"), ("Team0_0", "Team0_2"), ("Team0_1", "Team0_2")]


def test_real_predictor_sees_48_different_teams():
    """
    End to end with the real v1.0.0 predictor and its real history frame: every
    team is found in the history, and the pairings are no longer three
    predictions repeated 1,128 times.
    """
    from app.ml.features.feature_engineering import compute_dynamic_elo
    from app.ml.models.predictor import get_predictor
    from app.ml.train import load_data

    predictor = get_predictor()
    if not predictor.is_loaded:
        pytest.skip("legacy model bundle not available")
    df = compute_dynamic_elo(load_data())
    in_history = set(df["home_team"]) | set(df["away_team"])
    code_to_name = {c: n for n, c in ts._load_name_to_code_map().items()}
    codes = _codes()
    missing = [c for c in codes if code_to_name[c] not in in_history]
    assert missing == []

    sim = ts.TournamentSimulator(predictor, df, use_real_results=False)
    sim._precompute_matchups(codes)
    distinct = {(round(m["home_win_probability"], 4), round(m["draw_probability"], 4),
                 round(m["expected_home_goals"], 3), round(m["expected_away_goals"], 3))
                for m in sim.matchup_cache.values()}
    assert len(distinct) > 500, len(distinct)

    # USA is no longer the only team with an identity: its predictions against
    # two very different opponents differ, and so do another team's.
    def p(a, b):
        m = sim.matchup_cache[sim._get_matchup_key(a, b)]
        return m["home_win_probability"] if m["home_team"] == a else m["away_win_probability"]

    assert abs(p("USA", "ESP") - p("USA", "CUW")) > 0.02
    assert abs(p("BRA", "ESP") - p("BRA", "CUW")) > 0.02
