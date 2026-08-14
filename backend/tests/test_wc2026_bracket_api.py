"""
Tests for the WC2026 tournament-structure data layer (app/data/wc2026) and the
four read-only endpoints backed by it:

  GET /api/v1/tournament/2026/bracket
  GET /api/v1/tournament/2026/standings
  GET /api/v1/tournament/2026/teams
  GET /api/v1/tournament/2026/backtest

These endpoints read committed canonical files and touch neither the database
nor the model, so they are exercised directly against the ASGI app with no
dependency overrides — matching test_fifa_2026_data.py.

The backtest assertions pin the *published* frozen-model numbers (73/104,
70.19%). They are regression guards: if a future change silently alters the
frozen ledger or the way it is scored, these fail rather than the UI quietly
reporting a different accuracy than the model report.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.data.wc2026 import (
    STAGE_ORDER,
    build_backtest,
    build_bracket,
    build_standings,
    load_frozen_predictions,
    load_tournament_graph,
    load_wc2026_matches,
    load_wc2026_teams,
)


# ─── Raw loader sanity checks ────────────────────────────────────────────────

def test_tournament_graph_has_104_nodes():
    graph = load_tournament_graph()
    assert len(graph["nodes"]) == 104
    assert {r["stage"] for r in graph["stage_ranges"]} == set(STAGE_ORDER)


def test_canonical_matches_has_104_wc2026_fixtures():
    assert len(load_wc2026_matches()) == 104


def test_frozen_predictions_cover_all_104_matches():
    predictions = load_frozen_predictions()
    assert len(predictions) == 104
    assert set(predictions) == set(range(1, 105))
    # Every prediction must be a real probability distribution.
    for number, p in predictions.items():
        total = p["home_win_probability"] + p["draw_probability"] + p["away_win_probability"]
        assert abs(total - 1.0) < 1e-3, f"match {number} probabilities sum to {total}"


def test_frozen_predictions_all_from_the_frozen_model():
    versions = {p["model_version"] for p in load_frozen_predictions().values()}
    assert versions == {"v2.1.0-historical-optimized"}


def test_wc2026_teams_are_48_with_group_and_elo():
    teams = load_wc2026_teams()
    assert len(teams) == 48
    for name, meta in teams.items():
        assert meta["group"], f"{name} has no group"
        assert meta["elo_rating"] is not None, f"{name} has no Elo"


# ─── Bracket ─────────────────────────────────────────────────────────────────

def test_bracket_progression_wiring_is_consistent():
    """Every feeds_winner_to must be mirrored by a winner_of on the target.

    This is the property that lets the UI draw connectors from the graph alone;
    if the two directions ever disagree the bracket would render orphan edges.
    """
    nodes = {n["match_number"]: n for n in build_bracket()["nodes"]}
    for number, node in nodes.items():
        target = node.get("feeds_winner_to")
        if target is None:
            continue
        downstream = nodes[target]
        sources = [downstream.get("home_source"), downstream.get("away_source")]
        assert any(
            s and s.get("type") == "winner_of" and s.get("match_number") == number
            for s in sources
        ), f"match {number} feeds winner to {target}, which does not claim it"


def test_bracket_third_place_is_fed_by_semi_final_losers():
    nodes = {n["match_number"]: n for n in build_bracket()["nodes"]}
    third = nodes[103]
    assert third["stage"] == "third_place"
    assert third["home_source"]["type"] == "loser_of"
    assert third["away_source"]["type"] == "loser_of"
    assert {third["home_source"]["match_number"], third["away_source"]["match_number"]} == {101, 102}


def test_bracket_extra_time_matches_expose_et_score():
    """A knockout tie decided in ET must carry the ET score, otherwise the UI
    shows a bare draw next to a winner."""
    nodes = {n["match_number"]: n for n in build_bracket()["nodes"]}
    final = nodes[104]
    assert final["result_method"] == "Extra Time"
    assert final["home_score"] == 0 and final["away_score"] == 0
    assert final["home_score_et"] == 1 and final["away_score_et"] == 0
    assert final["winner_team"] == "Spain"


def test_bracket_penalty_match_exposes_shootout_score():
    nodes = {n["match_number"]: n for n in build_bracket()["nodes"]}
    match = nodes[76]
    assert match["result_method"] == "Penalties"
    assert match["home_penalties"] == 3 and match["away_penalties"] == 4
    assert match["winner_team"] == "Paraguay"


def test_every_bracket_node_carries_a_prediction():
    for node in build_bracket()["nodes"]:
        assert node["prediction"] is not None, f"match {node['match_number']} has no prediction"


# ─── Standings ───────────────────────────────────────────────────────────────

def test_standings_have_12_groups_of_4_teams_each_playing_3():
    groups = build_standings()
    assert len(groups) == 12
    for group in groups:
        assert len(group["standings"]) == 4
        for row in group["standings"]:
            assert row["played"] == 3
            assert row["won"] + row["drawn"] + row["lost"] == 3


def test_standings_points_match_results():
    for group in build_standings():
        for row in group["standings"]:
            assert row["points"] == row["won"] * 3 + row["drawn"]
            assert row["goal_difference"] == row["goals_for"] - row["goals_against"]


def test_standings_are_ordered_by_points_then_goal_difference():
    for group in build_standings():
        rows = group["standings"]
        keys = [(-r["points"], -r["goal_difference"], -r["goals_for"]) for r in rows]
        assert keys == sorted(keys), f"group {group['group']} is not correctly ordered"
        assert [r["position"] for r in rows] == [1, 2, 3, 4]


# ─── Backtest ────────────────────────────────────────────────────────────────

def test_backtest_reports_the_published_frozen_model_numbers():
    backtest = build_backtest()
    assert backtest["model_version"] == "v2.1.0-historical-optimized"
    assert backtest["n_matches_scored"] == 104
    assert backtest["correct"] == 73
    assert backtest["accuracy"] == pytest.approx(0.7019, abs=1e-4)


def test_backtest_stage_breakdown_sums_to_the_overall_total():
    backtest = build_backtest()
    assert sum(s["total"] for s in backtest["by_stage"]) == 104
    assert sum(s["correct"] for s in backtest["by_stage"]) == 73
    # Stages must come back in playing order, not dict order.
    stages = [s["stage"] for s in backtest["by_stage"]]
    assert stages == [s for s in STAGE_ORDER if s in stages]


def test_backtest_records_the_missed_final():
    """The frozen model picked Argentina; Spain won. That miss is part of the
    honest record and must not be smoothed over."""
    backtest = build_backtest()
    assert backtest["predicted_champion"] == "Argentina"
    assert backtest["actual_champion"] == "Spain"
    final = [m for m in backtest["matches"] if m["stage"] == "final"][0]
    assert final["correct"] is False


def test_backtest_match_rows_align_predictions_with_results():
    """Guards the index alignment between the comparison ledger and the
    prediction CSV — a silent off-by-one here would mislabel every match."""
    backtest = build_backtest()
    assert len(backtest["matches"]) == 104
    for row in backtest["matches"]:
        assert row["match_number"] is not None
        assert row["match"] is not None
        total = (
            row["home_win_probability"] + row["draw_probability"] + row["away_win_probability"]
        )
        assert abs(total - 1.0) < 1e-3


# ─── Endpoints ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bracket_endpoint_returns_104_nodes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tournament/2026/bracket")
    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 104
    assert len(body["stage_ranges"]) == len(STAGE_ORDER)


@pytest.mark.asyncio
async def test_standings_endpoint_returns_12_groups():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tournament/2026/standings")
    assert response.status_code == 200
    assert len(response.json()["groups"]) == 12


@pytest.mark.asyncio
async def test_teams_endpoint_returns_48_teams():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tournament/2026/teams")
    assert response.status_code == 200
    assert len(response.json()["teams"]) == 48


@pytest.mark.asyncio
async def test_backtest_endpoint_is_labelled_as_a_historical_comparison():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tournament/2026/backtest")
    assert response.status_code == 200
    body = response.json()
    assert body["accuracy"] == pytest.approx(0.7019, abs=1e-4)
    # The note is what stops a client presenting the backtest as a forecast.
    assert body["note"] and "comparison" in body["note"].lower()
