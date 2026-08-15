"""
Validation for the WC2026 squad data layer.

The team detail page is only trustworthy if the mapping underneath it is total
and unambiguous, so these tests assert that directly rather than spot-checking a
few teams: every registry team resolves, every squad is the full 26, every
captain is real and belongs to the squad shown, and no statistic is invented for
a player who did not play.
"""

import pytest

from app.data.players import (
    SQUAD_SIZE,
    TEAM_ALIASES,
    captain_for_team,
    load_players,
    mapped_team_names,
    squad_for_team,
    team_squad_summary,
)
from app.data.wc2026 import load_wc2026_teams


@pytest.fixture(scope="module")
def registry() -> set[str]:
    return set(load_wc2026_teams())


# ─── Coverage: all 48, no more, no less ──────────────────────────────────────

def test_every_registry_team_has_a_squad(registry):
    missing = sorted(registry - mapped_team_names())
    assert not missing, f"WC2026 teams with no squad data: {missing}"


def test_no_squad_data_for_teams_outside_the_registry(registry):
    """Guards against the legacy seed's non-national entities creeping in."""
    extra = sorted(mapped_team_names() - registry)
    assert not extra, f"squad data for non-WC2026 teams: {extra}"


def test_exactly_48_teams_are_mapped(registry):
    assert len(registry) == 48
    assert len(mapped_team_names()) == 48


def test_every_squad_has_exactly_26_players(registry):
    wrong = {t: len(squad_for_team(t)) for t in registry if len(squad_for_team(t)) != SQUAD_SIZE}
    assert not wrong, f"squads that are not {SQUAD_SIZE} players: {wrong}"


def test_all_player_rows_are_accounted_for(registry):
    assert sum(len(squad_for_team(t)) for t in registry) == len(load_players()) == 1248


def test_no_placeholder_or_legacy_entities_in_squad_teams():
    for bad in ("Central Spain", "TBD", "Asturias", "Ticino", "Yoruba Nation"):
        assert bad not in mapped_team_names()


def test_aliases_point_at_real_registry_names(registry):
    """The three renamed teams must land on names the registry actually uses."""
    for csv_name, registry_name in TEAM_ALIASES.items():
        assert registry_name in registry, f"alias {csv_name!r} -> unknown team {registry_name!r}"
    assert len(set(TEAM_ALIASES.values())) == len(TEAM_ALIASES), "two aliases collide"


def test_no_team_is_reachable_under_two_names(registry):
    """A duplicate mapping would show one squad on two different team pages."""
    counts: dict[str, int] = {}
    for t in mapped_team_names():
        counts[t] = counts.get(t, 0) + 1
    assert all(v == 1 for v in counts.values())


# ─── Captains: real, and present in the squad we render ──────────────────────

def test_every_team_has_a_captain(registry):
    missing = sorted(t for t in registry if captain_for_team(t) is None)
    assert not missing, f"teams with no captain on record: {missing}"


def test_captain_is_a_member_of_that_teams_squad(registry):
    """A captain who is not in the displayed 26 would be a fabricated pairing."""
    for team in registry:
        captain = captain_for_team(team)
        assert captain is not None
        squad_names = {p["name"] for p in squad_for_team(team)}
        assert captain["name"] in squad_names, (
            f"{team}: captain {captain['name']!r} is not in the squad shown"
        )
        assert captain["team"] == team


# ─── Honesty: absent is absent, never zero ───────────────────────────────────

def test_players_who_never_played_have_null_minutes_not_zero():
    """198 squad members have no appearances; they must not read as a real 0."""
    unplayed = [p for p in load_players() if not p["games"]]
    assert unplayed, "expected some squad members with no appearances"
    for p in unplayed:
        assert p["minutes"] is None, f"{p['name']}: minutes should be absent, got {p['minutes']}"


def test_goalkeeper_stats_only_ever_appear_on_goalkeepers():
    gk_fields = ("gk_games", "gk_minutes", "gk_saves", "gk_save_pct", "gk_clean_sheets")
    for p in load_players():
        if not p["is_goalkeeper"]:
            for f in gk_fields:
                assert p[f] is None, f"{p['name']} is not a keeper but has {f}={p[f]}"


def test_some_goalkeepers_legitimately_have_no_goalkeeping_data():
    """78 of 136 keepers never kept goal — the UI must be able to say so."""
    keepers = [p for p in load_players() if p["is_goalkeeper"]]
    assert keepers
    assert any(p["gk_saves"] is None for p in keepers)
    assert any(p["gk_saves"] is not None for p in keepers)


def test_squad_summary_totals_match_the_player_rows():
    s = team_squad_summary("Brazil")
    assert s["squad_size"] == SQUAD_SIZE
    assert s["total_goals"] == sum(p["goals"] or 0 for p in s["players"])
    assert s["total_assists"] == sum(p["assists"] or 0 for p in s["players"])
    assert s["total_minutes"] == sum(p["minutes"] or 0 for p in s["players"])
    assert s["players_with_appearances"] == sum(1 for p in s["players"] if (p["games"] or 0) > 0)


def test_goalkeepers_are_listed_first():
    """Squad ordering is stable and keeper-first, so the grid never reshuffles."""
    for team in ("Brazil", "USA", "Spain", "Japan", "Morocco", "Canada"):
        squad = squad_for_team(team)
        positions = [(p["position"] or "").split(",")[0] for p in squad]
        assert positions[0] == "GK", f"{team}: expected a goalkeeper first, got {positions[:3]}"


def test_unknown_team_returns_empty_rather_than_raising():
    assert squad_for_team("Not A Country") == []
    assert captain_for_team("Not A Country") is None
