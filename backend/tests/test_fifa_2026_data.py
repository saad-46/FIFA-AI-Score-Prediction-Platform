"""
Tests for the FIFA World Cup 2026 reference data (app/data/fifa_2026) and the
two read-only endpoints backed by it:
  GET /api/v1/tournament/2026/groups
  GET /api/v1/tournament/2026/schedule
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.data.fifa_2026 import load_groups, load_schedule, get_groups_as_team_codes


# ─── Raw data loader sanity checks ───────────────────────────────────────────

def test_load_groups_has_12_groups_48_teams():
    groups = load_groups()
    assert len(groups) == 12
    total_teams = sum(len(teams) for teams in groups.values())
    assert total_teams == 48
    for name, teams in groups.items():
        assert len(teams) == 4, f"Group {name} does not have 4 teams"


def test_get_groups_as_team_codes_matches_load_groups():
    codes = get_groups_as_team_codes()
    assert len(codes) == 12
    assert sum(len(v) for v in codes.values()) == 48
    # Every entry should be a bare team code string, not a dict.
    for teams in codes.values():
        for t in teams:
            assert isinstance(t, str)


def test_load_schedule_has_104_matches_with_correct_stage_breakdown():
    matches = load_schedule()
    assert len(matches) == 104

    stage_counts = {}
    for m in matches:
        stage_counts[m["stage"]] = stage_counts.get(m["stage"], 0) + 1

    assert stage_counts == {
        "group_stage": 72,
        "round_of_32": 16,
        "round_of_16": 8,
        "quarter_final": 4,
        "semi_final": 2,
        "third_place": 1,
        "final": 1,
    }


# ─── GET /api/v1/tournament/2026/groups ──────────────────────────────────────

@pytest.mark.asyncio
async def test_groups_endpoint_returns_12_groups_48_teams():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/tournament/2026/groups")

    assert response.status_code == 200
    data = response.json()
    groups = data["groups"]
    assert len(groups) == 12

    total_teams = sum(len(g["teams"]) for g in groups)
    assert total_teams == 48

    # Each team entry should carry a code + name.
    first_team = groups[0]["teams"][0]
    assert "code" in first_team
    assert "name" in first_team


# ─── GET /api/v1/tournament/2026/schedule ────────────────────────────────────

@pytest.mark.asyncio
async def test_schedule_endpoint_returns_104_matches_with_stage_breakdown():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/tournament/2026/schedule")

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 104

    stage_counts = {}
    for m in matches:
        stage_counts[m["stage"]] = stage_counts.get(m["stage"], 0) + 1

    assert stage_counts == {
        "group_stage": 72,
        "round_of_32": 16,
        "round_of_16": 8,
        "quarter_final": 4,
        "semi_final": 2,
        "third_place": 1,
        "final": 1,
    }


@pytest.mark.asyncio
async def test_schedule_endpoint_stage_filter():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/tournament/2026/schedule", params={"stage": "final"}
        )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["stage"] == "final"


@pytest.mark.asyncio
async def test_schedule_endpoint_stage_filter_group_stage_count():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/tournament/2026/schedule", params={"stage": "group_stage"}
        )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 72
    assert all(m["stage"] == "group_stage" for m in matches)


@pytest.mark.asyncio
async def test_schedule_endpoint_venue_city_filter():
    # Discover a real venue_city from the unfiltered schedule first, so the
    # test doesn't depend on hardcoding a city that might not be in the data.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        all_response = await client.get("/api/v1/tournament/2026/schedule")
        all_matches = all_response.json()["matches"]
        sample_city = all_matches[0]["venue_city"]
        expected_count = sum(1 for m in all_matches if m["venue_city"] == sample_city)

        response = await client.get(
            "/api/v1/tournament/2026/schedule", params={"venue_city": sample_city}
        )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == expected_count
    assert all(m["venue_city"] == sample_city for m in matches)


@pytest.mark.asyncio
async def test_schedule_endpoint_combined_stage_and_venue_filter():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/tournament/2026/schedule",
            params={"stage": "group_stage", "venue_city": "Mexico City"},
        )

    assert response.status_code == 200
    matches = response.json()["matches"]
    assert all(m["stage"] == "group_stage" for m in matches)
    assert all(m["venue_city"] == "Mexico City" for m in matches)


@pytest.mark.asyncio
async def test_schedule_endpoint_unknown_stage_returns_empty_list():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/tournament/2026/schedule", params={"stage": "not_a_real_stage"}
        )

    assert response.status_code == 200
    assert response.json()["matches"] == []
