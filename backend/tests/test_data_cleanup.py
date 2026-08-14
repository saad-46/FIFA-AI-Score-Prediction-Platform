"""
Regression tests for the UI/data cleanup wave.

Each test here pins a *specific defect that was visible in the product*, so a
future change that silently reintroduces one fails loudly:

  - "Central Spain" (a CONIFA-style regional side carried in the legacy teams
    seed) appearing in a WC2026 team picker, and the directory showing 20 of
    48 teams.
  - Head-to-head reporting "No previous meetings" for Spain v Argentina, who
    met at the 1966 World Cup — the served corpus only starts in 2002.
  - The Insights card headlining 28.9% "Model Accuracy": a stale, draw-boosted
    legacy v1 holdout number, not the shipped V2 model.

The team-directory test overrides `get_db` with a fake session rather than
hitting Postgres, matching test_wc2026_api.py.
"""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.data.wc2026 import (
    load_wc2026_teams,
    world_cup_head_to_head,
)
from app.db.database import get_db
from app.main import app


# ─── Team identity / directory ───────────────────────────────────────────────

def test_wc2026_team_set_is_exactly_48_with_no_placeholder_entities():
    teams = load_wc2026_teams()
    assert len(teams) == 48
    names = set(teams)
    # The specific junk that reached the UI, plus the generic placeholder.
    for bad in ("Central Spain", "TBD", "Asturias", "Ticino", "Yoruba Nation"):
        assert bad not in names, f"{bad!r} must not be in the WC2026 team set"
    # Spain must be present exactly once, as itself.
    assert "Spain" in names
    assert len([n for n in names if "Spain" in n]) == 1


def test_wc2026_teams_have_no_duplicates_and_complete_metadata():
    teams = load_wc2026_teams()
    codes = [t["fifa_code"] for t in teams.values()]
    assert len(codes) == len(set(codes)) == 48, "FIFA codes must be unique across the 48"
    groups = {}
    for meta in teams.values():
        assert meta["group"], "every WC2026 team needs a group"
        assert meta["elo_rating"] is not None
        groups.setdefault(meta["group"], []).append(meta)
    assert len(groups) == 12
    assert all(len(v) == 4 for v in groups.values()), "each group holds exactly 4 teams"


def test_historical_predecessor_states_are_not_in_the_wc2026_set():
    """Phase 27: historical identities stay distinct and out of the current
    team picker — they must be neither merged into successors nor listed."""
    names = set(load_wc2026_teams())
    for historical in ("West Germany", "Soviet Union", "Czechoslovakia", "Yugoslavia"):
        assert historical not in names


# ─── Head-to-head ────────────────────────────────────────────────────────────

def test_spain_argentina_world_cup_meetings_are_found():
    """The exact pair that rendered "No previous meetings" in the UI."""
    h2h = world_cup_head_to_head("Spain", "Argentina")
    assert h2h["total_matches"] == 2
    years = {m["year"] for m in h2h["meetings"]}
    assert years == {1966, 2026}


def test_extra_time_win_counts_as_a_win_not_a_draw():
    """The 2026 final finished 0-0 after 90 and 1-0 after extra time. Scoring
    it on the full-time line would report a draw beside a declared winner."""
    h2h = world_cup_head_to_head("Spain", "Argentina")
    assert h2h["draws"] == 0
    assert h2h["team_a_wins"] == 1  # Spain, 2026 final in ET
    assert h2h["team_b_wins"] == 1  # Argentina, 1966 group stage
    final = [m for m in h2h["meetings"] if m["year"] == 2026][0]
    assert final["result_method"] == "Extra Time"
    assert final["winner_team"] == "Spain"


def test_penalty_shootout_counts_as_a_draw_with_winner_recorded():
    """Converse of the ET case: a shootout leaves the match drawn."""
    h2h = world_cup_head_to_head("Switzerland", "Colombia")
    shootout = [m for m in h2h["meetings"] if m["result_method"] == "Penalties"]
    assert len(shootout) == 1
    assert h2h["draws"] == 1
    assert shootout[0]["winner_team"] == "Switzerland"
    assert "pens" in (shootout[0]["display_score"] or "")


def test_head_to_head_is_symmetric():
    forward = world_cup_head_to_head("Brazil", "Germany")
    reverse = world_cup_head_to_head("Germany", "Brazil")
    assert forward["total_matches"] == reverse["total_matches"]
    assert forward["team_a_wins"] == reverse["team_b_wins"]
    assert forward["draws"] == reverse["draws"]


def test_empty_head_to_head_still_declares_its_scope():
    """Zero World Cup meetings must not be presentable as "never played" —
    the corpus excludes friendlies and qualifiers."""
    h2h = world_cup_head_to_head("Haiti", "Jordan")
    assert h2h["total_matches"] == 0
    assert h2h["meetings"] == []
    assert "World Cup" in h2h["scope_label"]
    assert h2h["scope"] == "fifa_world_cup_1930_2026"


# ─── Endpoints ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_world_cup_h2h_endpoint_returns_meetings_and_scope():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/teams/world-cup-head-to-head",
            params={"team_a": "Spain", "team_b": "Argentina"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total_matches"] == 2
    assert body["scope_label"]


@pytest.mark.asyncio
async def test_model_evaluation_headlines_the_v2_backtest_not_legacy_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/model-evaluation")
    assert response.status_code == 200
    body = response.json()

    assert body["model_version"] == "v2.1.0-historical-optimized"
    assert body["accuracy"] == pytest.approx(0.7019, abs=1e-4)
    assert (body["correct"], body["total"]) == (73, 104)
    assert body["is_out_of_sample"] is True
    # The headline must be named, not a bare "accuracy".
    assert "backtest" in body["evaluation_name"].lower()

    # The 28.9% legacy figure is retained but explicitly labelled superseded.
    legacy = body["legacy"]
    assert legacy["classifier_adjusted_accuracy"] == pytest.approx(0.28947, abs=1e-5)
    assert legacy["training_samples"] == 376
    assert "superseded" in legacy["label"].lower()


@pytest.mark.asyncio
async def test_wc2026_team_directory_endpoint_returns_48_alphabetically():
    """The directory previously rendered a 20-team win-rate leaderboard."""
    teams = sorted(load_wc2026_teams().values(), key=lambda t: t["team_name"])

    # SimpleNamespace, not MagicMock: `name` is a reserved MagicMock kwarg
    # (it names the mock) so `MagicMock(name=...)` never sets a `.name`
    # attribute and Pydantic sees a mock object instead of a string.
    class _FakeScalars:
        def all(self):
            return [
                SimpleNamespace(
                    id=f"id-{i}",
                    name=t["team_name"],
                    country=t["team_name"],
                    confederation=t["confederation"],
                    fifa_ranking=t["fifa_ranking"],
                    elo_rating=int(t["elo_rating"]),
                    fifa_code=t["fifa_code"],
                    wc2026_group=t["group"],
                    ranking_updated_at=None,
                    logo_url=None,
                    founded_year=None,
                    home_stadium=None,
                    created_at="2026-01-01T00:00:00+00:00",
                )
                for i, t in enumerate(teams)
            ]

    class _FakeResult:
        def scalars(self):
            return _FakeScalars()

    class _FakeSession:
        async def execute(self, *_args, **_kwargs):
            return _FakeResult()

    async def _override():
        yield _FakeSession()

    app.dependency_overrides[get_db] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/teams/wc2026")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 48
    names = [t["name"] for t in body]
    assert "Central Spain" not in names
    assert names == sorted(names), "directory must come back alphabetically"
