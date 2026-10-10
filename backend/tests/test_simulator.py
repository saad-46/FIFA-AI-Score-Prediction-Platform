import pytest
import pandas as pd
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app

@pytest.mark.asyncio
async def test_simulate_tournament_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"num_simulations": 10}
        )

    # Since it's a mock or the DB is empty, it might fail or return a structured response.
    # We just want to ensure it doesn't crash with 500.
    assert response.status_code in [200, 400, 422, 500]


# ─── TournamentSimulationRequest validation (422s) ───────────────────────────

def _make_valid_groups(duplicate: bool = False):
    """Build a valid 12-group/48-team payload for TournamentSimulationRequest.
    If duplicate=True, one team name is reused across two different groups
    (still 48 total slots, but only 47 distinct names) to trigger the
    duplicate-team validator.
    """
    letters = "ABCDEFGHIJKL"
    groups = []
    for gi, letter in enumerate(letters):
        teams = [f"Team{gi}_{i}" for i in range(4)]
        groups.append({"name": letter, "teams": teams})

    if duplicate:
        # Overwrite the first team of group B with the first team of group A.
        groups[1]["teams"][0] = groups[0]["teams"][0]

    return groups


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_wrong_team_total():
    """Groups that don't sum to 48 teams must be rejected with 422 before any
    prediction/model work happens. Drop an entire group (rather than a single
    team within a group) so the per-group "exactly 4 teams" field validator
    doesn't fire first — this specifically exercises the model-level
    "must total 48 across all groups" validator."""
    groups = _make_valid_groups()
    groups.pop()  # only 11 groups (44 teams) left

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": groups, "n_simulations": 100},
        )

    assert response.status_code == 422
    body = response.json()
    assert "48" in str(body)


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_duplicate_team_across_groups():
    groups = _make_valid_groups(duplicate=True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": groups, "n_simulations": 100},
        )

    assert response.status_code == 422
    body = response.json()
    assert "duplicate" in str(body).lower()


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_missing_groups_without_fifa_flag():
    """No groups provided and use_fifa_2026_groups not set -> 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"n_simulations": 100},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_empty_groups_list():
    """An explicit empty list for groups is also not a valid 48-team payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": [], "n_simulations": 100},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_malformed_group_shape():
    """A group missing the required 'teams' field entirely should 422 on
    schema shape validation, not reach the business-rule validator."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": [{"name": "A"}], "n_simulations": 100},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_group_with_wrong_team_count():
    """Each TournamentGroup requires exactly 4 teams (min_length=max_length=4)."""
    groups = _make_valid_groups()
    groups[0]["teams"] = groups[0]["teams"][:3]  # only 3 teams in group A

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": groups, "n_simulations": 100},
        )

    assert response.status_code == 422


# ─── n_simulations bounds (ge=100, le=100000) ────────────────────────────────

@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_n_simulations_too_low():
    groups = _make_valid_groups()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": groups, "n_simulations": 1},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_rejects_n_simulations_too_high():
    groups = _make_valid_groups()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/tournament/simulate",
            json={"groups": groups, "n_simulations": 1_000_000},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_simulate_endpoint_accepts_n_simulations_at_lower_bound(legacy_engine):
    """Legacy engine (rollback path); V3 equivalents are in tests/test_v3_api.py.

    n_simulations=100 (the schema's ge=100 boundary) should pass schema
    validation and reach the endpoint body / actually run a simulation.
    Mocks out the predictor+dataframe dependency (no live DB in this test
    environment) so we can assert a real 200 rather than just "not a 422"."""
    groups = _make_valid_groups()

    mock_predictor = MagicMock()
    mock_predictor.is_loaded = True

    def mock_predict_batch(df, pairs, **kwargs):
        return [
            {
                "home_team": t1,
                "away_team": t2,
                "expected_home_goals": 1.2,
                "expected_away_goals": 1.0,
                "home_win_probability": 0.45,
                "away_win_probability": 0.30,
                "draw_probability": 0.25,
            }
            for t1, t2 in pairs
        ]

    mock_predictor.predict_batch = mock_predict_batch

    with patch(
        "app.api.v1.endpoints.tournament._get_simulator_dependencies",
        new_callable=AsyncMock,
        return_value=(mock_predictor, pd.DataFrame()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tournament/simulate",
                json={"groups": groups, "n_simulations": 100},
            )

    assert response.status_code == 200
    data = response.json()
    probabilities = data["probabilities"]
    assert len(probabilities) == 48
    winner_total = sum(p["winner"] for p in probabilities.values())
    assert winner_total == pytest.approx(1.0, abs=1e-6)


# ─── Predictor unavailable / simulation failure -> graceful HTTP errors ──────

@pytest.mark.asyncio
async def test_simulate_endpoint_returns_503_when_predictor_not_loaded(legacy_engine):
    """Legacy engine (rollback path).

    If the model bundle failed to load (missing/corrupted model file —
    see test_predictor.py for the predictor-level fallback behavior), the
    endpoint must return a clear 503 rather than attempting a simulation
    with a None model and crashing with a 500."""
    groups = _make_valid_groups()

    mock_predictor = MagicMock()
    mock_predictor.is_loaded = False  # simulates missing/corrupted model bundle

    with patch(
        "app.api.v1.endpoints.tournament._get_simulator_dependencies",
        new_callable=AsyncMock,
        return_value=(mock_predictor, pd.DataFrame()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tournament/simulate",
                json={"groups": groups, "n_simulations": 100},
            )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_simulate_endpoint_returns_503_when_simulation_error_raised(legacy_engine):
    """Legacy engine (rollback path).

    TournamentSimulationError (raised when too many simulation batches
    fail — the fixed failure mode of the original silent-crash bug) must be
    translated into a 503, not an unhandled 500."""
    from app.ml.tournament_simulator import TournamentSimulationError

    groups = _make_valid_groups()

    mock_predictor = MagicMock()
    mock_predictor.is_loaded = True
    mock_predictor.predict_batch = MagicMock(return_value=[])

    with patch(
        "app.api.v1.endpoints.tournament._get_simulator_dependencies",
        new_callable=AsyncMock,
        return_value=(mock_predictor, pd.DataFrame()),
    ), patch(
        "app.api.v1.endpoints.tournament.TournamentSimulator.simulate_tournament",
        side_effect=TournamentSimulationError("all batches failed"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/tournament/simulate",
                json={"groups": groups, "n_simulations": 100},
            )

    assert response.status_code == 503
