"""
Regression tests for the Database Engineering / Backend API upgrade wave:

  - TeamResponse now surfaces teams_reference.csv-sourced ranking fields
    (elo_rating, fifa_code, wc2026_group) — see RANKINGS_INTEGRATION.md.
  - GET /matches/{match_id} returns team_statistics from the new
    team_statistics table, including the documented gap where some matches
    have no stats row at all (must degrade gracefully, not 500).
  - GET /matches must not silently drop matches whose away_team_id is NULL
    (the real TBD Round-of-16 opponent case) from the paginated list.

No live Postgres is reachable from this test environment (Supabase host is
unresolvable here), so these tests override the `get_db` FastAPI dependency
with a lightweight fake AsyncSession whose `execute()` returns canned
SQLAlchemy-shaped results, rather than hitting a real database. This mirrors
how test_simulator.py / test_tournament.py mock out DB-adjacent dependencies
elsewhere in this suite.
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.models.match import Team, Match, TeamStatistics


# ─── Fake AsyncSession plumbing ──────────────────────────────────────────────

class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def one_or_none(self):
        return self._items[0] if self._items else None


class _FakeResult:
    """Stands in for sqlalchemy.engine.Result: supports .scalars(),
    .scalar_one_or_none(), and .scalar() as needed by the service functions
    under test."""

    def __init__(self, items=None, scalar_value=None):
        self._items = items or []
        self._scalar_value = scalar_value

    def scalars(self):
        return _FakeScalarResult(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._scalar_value if self._scalar_value is not None else len(self._items)


class _FakeSession:
    """A minimal stand-in for AsyncSession that returns pre-programmed
    results in sequence for each call to execute(), so a test can control
    exactly what each query in a service function sees."""

    def __init__(self, results: list):
        self._results = list(results)
        self.call_count = 0

    async def execute(self, stmt):
        idx = min(self.call_count, len(self._results) - 1)
        self.call_count += 1
        return self._results[idx]


def _make_team(id_, name, country="Testland", **kwargs):
    t = Team(id=id_, name=name, country=country, **kwargs)
    return t


def _make_match(id_, home_team, away_team, **kwargs):
    defaults = dict(
        date=date(2026, 6, 20),
        home_team_id=home_team.id if home_team else None,
        away_team_id=away_team.id if away_team else None,
        home_score=None,
        away_score=None,
        tournament="FIFA World Cup 2026",
        stage="Round of 16",
        stage_id=None,
        tournament_year=2026,
        neutral_venue=True,
        city="Toronto",
        country="Canada",
        home_xg=None,
        away_xg=None,
        status="scheduled",
    )
    defaults.update(kwargs)
    m = Match(id=id_, **defaults)
    m.home_team = home_team
    m.away_team = away_team
    return m


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Ensure dependency_overrides never leaks between tests in this module
    or into other test modules."""
    yield
    app.dependency_overrides.pop(get_db, None)


# ─── TeamResponse ranking fields (elo_rating / fifa_code / wc2026_group) ─────

@pytest.mark.asyncio
async def test_get_team_returns_wc2026_ranking_fields():
    """A team populated from teams_reference.csv (via the DB seed) must
    surface elo_rating, fifa_code, and wc2026_group on the TeamResponse —
    these are new columns added in the DATABASE_SCHEMA.md / RANKINGS_INTEGRATION.md
    upgrade, not present on the old TeamBase schema."""
    team = _make_team(
        "11111111-1111-1111-1111-111111111111", "Germany", country="Germany", confederation="UEFA",
        fifa_ranking=16, elo_rating=1950, fifa_code="GER", wc2026_group="A",
        ranking_updated_at=datetime(2026, 6, 1),
        created_at=datetime(2025, 1, 1),
    )

    fake_session = _FakeSession([_FakeResult(items=[team])])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/teams/11111111-1111-1111-1111-111111111111")

    assert response.status_code == 200
    data = response.json()
    assert data["elo_rating"] == 1950
    assert data["fifa_code"] == "GER"
    assert data["wc2026_group"] == "A"


@pytest.mark.asyncio
async def test_get_team_ranking_fields_null_for_non_2026_team():
    """A historical-only team not in teams_reference.csv's 48-team field must
    return null (not fabricated/zeroed) ranking fields — see
    RANKINGS_INTEGRATION.md's documented coverage gap."""
    team = _make_team(
        "22222222-2222-2222-2222-222222222222", "Historical FC", country="Nowhere",
        fifa_ranking=None, elo_rating=None, fifa_code=None, wc2026_group=None,
        ranking_updated_at=None,
        created_at=datetime(2025, 1, 1),
    )

    fake_session = _FakeSession([_FakeResult(items=[team])])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/teams/22222222-2222-2222-2222-222222222222")

    assert response.status_code == 200
    data = response.json()
    assert data["elo_rating"] is None
    assert data["fifa_code"] is None
    assert data["wc2026_group"] is None


# ─── GET /matches/{match_id} — team_statistics ───────────────────────────────

@pytest.mark.asyncio
async def test_get_match_by_id_returns_team_statistics():
    """A completed match with rows in team_statistics for both teams must
    surface them on MatchDetailResponse.team_statistics."""
    home = _make_team("44444444-4444-4444-4444-444444444444", "Brazil")
    away = _make_team("55555555-5555-5555-5555-555555555555", "Argentina")
    match = _make_match(
        "33333333-3333-3333-3333-333333333333", home, away,
        home_score=2, away_score=1, status="completed", stage="Final",
    )

    stat_home = TeamStatistics(
        id="66666666-6666-6666-6666-666666666666", match_id="33333333-3333-3333-3333-333333333333", team_id="44444444-4444-4444-4444-444444444444",
        possession_pct=55, total_shots=14, shots_on_target=6,
        corners=6, fouls=10, offsides=2, saves=3,
        player_of_the_match="Player A",
    )
    stat_home.team = home
    stat_away = TeamStatistics(
        id="77777777-7777-7777-7777-777777777777", match_id="33333333-3333-3333-3333-333333333333", team_id="55555555-5555-5555-5555-555555555555",
        possession_pct=45, total_shots=9, shots_on_target=4,
        corners=3, fouls=12, offsides=1, saves=4,
        player_of_the_match=None,
    )
    stat_away.team = away

    fake_session = _FakeSession([
        _FakeResult(items=[match]),               # SELECT Match
        _FakeResult(items=[stat_home, stat_away]),  # SELECT TeamStatistics
    ])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/matches/33333333-3333-3333-3333-333333333333")

    assert response.status_code == 200
    data = response.json()
    assert len(data["team_statistics"]) == 2
    team_ids = {s["team_id"] for s in data["team_statistics"]}
    assert team_ids == {"44444444-4444-4444-4444-444444444444", "55555555-5555-5555-5555-555555555555"}
    home_stat = next(s for s in data["team_statistics"] if s["team_id"] == "44444444-4444-4444-4444-444444444444")
    assert home_stat["possession_pct"] == 55
    assert home_stat["player_of_the_match"] == "Player A"


@pytest.mark.asyncio
async def test_get_match_by_id_with_no_stats_row_returns_empty_list_not_500():
    """One of the 10 documented gaps (DATABASE_SCHEMA.md): some completed
    2026 matches have zero rows in team_statistics. The endpoint must
    return team_statistics=[] gracefully, not 500."""
    home = _make_team("99999999-9999-9999-9999-999999999999", "Morocco")
    away = _make_team("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Portugal")
    match = _make_match(
        "88888888-8888-8888-8888-888888888888", home, away,
        home_score=0, away_score=0, status="completed", stage="Group Stage",
    )

    fake_session = _FakeSession([
        _FakeResult(items=[match]),  # SELECT Match
        _FakeResult(items=[]),        # SELECT TeamStatistics -> none found
    ])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/matches/88888888-8888-8888-8888-888888888888")

    assert response.status_code == 200
    data = response.json()
    assert data["team_statistics"] == []


@pytest.mark.asyncio
async def test_get_match_by_id_not_found_returns_404_not_500():
    fake_session = _FakeSession([_FakeResult(items=[])])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/matches/does-not-exist")

    assert response.status_code == 404


# ─── GET /matches — away_team_id IS NULL (TBD knockout opponent) ────────────

@pytest.mark.asyncio
async def test_list_matches_does_not_drop_match_with_null_away_team():
    """Regression test: a match with away_team_id IS NULL (the real WC2026
    Canada Round-of-16 fixture whose opponent is still TBD) must still
    appear in the paginated /matches response instead of being silently
    filtered out, which was the pre-fix behaviour (match_service.py used to
    require both home_team AND away_team to be truthy)."""
    home = _make_team("can-1", "Canada", country="Canada")
    tbd_match = _make_match(
        "match-tbd", home, None,
        home_score=None, away_score=None, status="scheduled",
        stage="Round of 16",
    )

    # match_service.get_matches issues: 1) a count query, 2) the paginated
    # SELECT of Match rows.
    fake_session = _FakeSession([
        _FakeResult(scalar_value=1),        # COUNT(*)
        _FakeResult(items=[tbd_match]),      # paginated SELECT
    ])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/matches", params={"team": "Canada"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["data"]) == 1
    match_out = data["data"][0]
    assert match_out["id"] == "match-tbd"
    assert match_out["home_team"]["name"] == "Canada"
    assert match_out["away_team_id"] is None
    assert match_out["away_team"] is None


@pytest.mark.asyncio
async def test_list_matches_includes_both_null_and_resolved_away_teams():
    """A page containing a mix of a fully-resolved match and a TBD-opponent
    match must return both — the fix only relaxed the "away_team truthy"
    requirement, it must not affect matches that do have a real away team."""
    home1 = _make_team("h1", "Spain")
    away1 = _make_team("a1", "France")
    resolved_match = _make_match(
        "match-resolved", home1, away1,
        home_score=2, away_score=1, status="completed", stage="Semi Final",
    )

    home2 = _make_team("h2", "Canada", country="Canada")
    tbd_match = _make_match(
        "match-tbd-2", home2, None,
        home_score=None, away_score=None, status="scheduled",
        stage="Round of 16",
    )

    fake_session = _FakeSession([
        _FakeResult(scalar_value=2),
        _FakeResult(items=[resolved_match, tbd_match]),
    ])

    async def _override_get_db():
        yield fake_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/matches")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["data"]) == 2
    ids = {m["id"] for m in data["data"]}
    assert ids == {"match-resolved", "match-tbd-2"}
