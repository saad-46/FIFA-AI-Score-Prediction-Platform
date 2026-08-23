"""
Squad and player data for the 48 WC2026 teams.

Source of truth
---------------
``app/data/players.csv`` -- 1,248 rows, 26 players for every one of the 48
teams, 72 columns. Everything this module serves comes from that file or from
``app/data/canonical/canonical_match_stats.csv``; nothing is generated.

Two things a reader will want to know up front, because they shaped the API:

1. **Team names do not match the registry exactly.** Three differ, and they are
   aliased below rather than fuzzy-matched. With those three fixed, all 48
   registry teams resolve to exactly 26 players each (1,248 total). There is no
   guessing anywhere in this mapping -- see ``TEAM_ALIASES``.

2. **Most statistics are only partly populated.** Only player/team/position/age/
   birth_year/games/games_starts are present on ~100% of rows; `club`, `minutes`,
   `goals`, `assists` and the rest are populated for the 972 of 1,170 players who
   actually played. 198 squad members have no minutes at all, and 78 of the 136
   goalkeepers have no goalkeeping columns. Every accessor therefore returns
   ``None`` for absent values rather than 0, so the UI can say "Not available"
   instead of implying a real zero.

Captains are real, not inferred from seniority or fame: canonical_match_stats
records the captain of every 2026 match (208 rows, 100% populated), and the
captain reported here is the one who wore the armband in that team's most recent
match. All 48 resolved captains appear in their own team's 26-player squad.

There is no photograph, shirt-number or squad-status column in any available
source -- see PLAYER_IMAGE_POLICY at the bottom of this module.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_DATA_DIR = Path(__file__).resolve().parent
_PLAYERS_CSV = _DATA_DIR / "players.csv"
_MATCH_STATS_CSV = _DATA_DIR / "canonical" / "canonical_match_stats.csv"

# players.csv team name -> WC2026 registry name. These are the only three that
# differ, confirmed by set-difference against load_wc2026_teams(); the rest match
# exactly. Note the first key uses an EN DASH, not a hyphen.
TEAM_ALIASES: dict[str, str] = {
    "Bosnia–Herz": "Bosnia and Herzegovina",
    "Korea Republic": "South Korea",
    "United States": "USA",
}

SQUAD_SIZE = 26


def _num(value: str | None) -> Optional[float]:
    """Blank CSV cell -> None. A real 0 stays 0; a missing value never becomes 0."""
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _int(value: str | None) -> Optional[int]:
    n = _num(value)
    return int(n) if n is not None else None


def _text(value: str | None) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    return v or None


def _is_goalkeeper(row: dict[str, str]) -> bool:
    return "GK" in (row.get("position") or "")


@lru_cache(maxsize=1)
def load_players() -> list[dict[str, Any]]:
    """Every player row, typed, with the team name mapped to the registry."""
    with _PLAYERS_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    players: list[dict[str, Any]] = []
    for r in rows:
        raw_team = _text(r.get("team")) or ""
        team = TEAM_ALIASES.get(raw_team, raw_team)
        gk = _is_goalkeeper(r)

        player: dict[str, Any] = {
            "name": _text(r.get("player")) or "",
            "team": team,
            "position": _text(r.get("position")),
            "age": _int(r.get("age")),
            "birth_year": _int(r.get("birth_year")),
            "club": _text(r.get("club")),
            "is_goalkeeper": gk,
            # Appearance block -- present for essentially every row.
            "games": _int(r.get("games")),
            "games_starts": _int(r.get("games_starts")),
            "minutes": _int(r.get("minutes")),
            # Attacking
            "goals": _int(r.get("goals")),
            "assists": _int(r.get("assists")),
            "shots": _int(r.get("shots")),
            "shots_on_target": _int(r.get("shots_on_target")),
            "goals_per90": _num(r.get("goals_per90")),
            "assists_per90": _num(r.get("assists_per90")),
            # Creative / discipline
            "crosses": _int(r.get("crosses")),
            "fouled": _int(r.get("fouled")),
            "offsides": _int(r.get("offsides")),
            "cards_yellow": _int(r.get("cards_yellow")),
            "cards_red": _int(r.get("cards_red")),
            # Defensive
            "tackles_won": _int(r.get("tackles_won")),
            "interceptions": _int(r.get("interceptions")),
            "fouls": _int(r.get("fouls")),
            # Goalkeeping -- only ever populated on GK rows (verified: zero
            # non-GK rows carry gk_ data), and only for 58 of the 136 keepers.
            "gk_games": _int(r.get("gk_games")) if gk else None,
            "gk_minutes": _int(r.get("gk_minutes")) if gk else None,
            "gk_goals_against": _int(r.get("gk_goals_against")) if gk else None,
            "gk_saves": _int(r.get("gk_saves")) if gk else None,
            "gk_save_pct": _num(r.get("gk_save_pct")) if gk else None,
            "gk_clean_sheets": _int(r.get("gk_clean_sheets")) if gk else None,
            "gk_clean_sheets_pct": _num(r.get("gk_clean_sheets_pct")) if gk else None,
        }
        players.append(player)
    return players


@lru_cache(maxsize=1)
def _players_by_team() -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for p in load_players():
        index.setdefault(p["team"], []).append(p)

    def sort_key(p: dict[str, Any]) -> tuple[int, int, str]:
        # Goalkeepers first, then by minutes played (most first), then by name.
        # Players with no minutes sort last within their group rather than
        # appearing to have played zero.
        order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
        primary = (p["position"] or "").split(",")[0]
        return (order.get(primary, 4), -(p["minutes"] or 0), p["name"])

    for team in index:
        index[team].sort(key=sort_key)
    return index


@lru_cache(maxsize=1)
def _captains_by_team() -> dict[str, str]:
    """
    Team -> the captain of that team's most recent 2026 match.

    Real armband data, not a heuristic. canonical_match_stats has one row per
    team per match with the captain filled in for all 208 rows.
    """
    latest: dict[str, tuple[str, str]] = {}  # team -> (date, captain)
    if not _MATCH_STATS_CSV.exists():
        return {}
    with _MATCH_STATS_CSV.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            team = _text(r.get("team"))
            captain = _text(r.get("captain"))
            date = _text(r.get("date")) or ""
            if not team or not captain:
                continue
            if team not in latest or date > latest[team][0]:
                latest[team] = (date, captain)
    return {team: captain for team, (_, captain) in latest.items()}


def squad_for_team(team_name: str) -> list[dict[str, Any]]:
    """The 26 players for a registry team name. Empty list if unknown."""
    return list(_players_by_team().get(team_name, []))


def captain_for_team(team_name: str) -> Optional[dict[str, Any]]:
    """
    The captain's full player record, or None when unavailable.

    Resolved by name against that team's own squad so we never return a captain
    who is not in the squad we are displaying.
    """
    name = _captains_by_team().get(team_name)
    if not name:
        return None
    for p in _players_by_team().get(team_name, []):
        if p["name"] == name:
            return p
    return None


KEY_PLAYER_COUNT = 8


def _importance(player: dict[str, Any]) -> float:
    """
    How prominently a player featured for his country, from his own record.

    This ranks real numbers; it does not judge talent and it invents nothing. A
    player who did not play scores 0 and cannot be promoted by any other term.

    Starts are weighted above appearances because starting is the clearer signal
    that a manager considers a player first-choice, and goals above assists
    because goals are the scarcer event. Goalkeepers score on saves and clean
    sheets instead of goal contributions, otherwise every keeper would rank
    below every forward regardless of how central he was to the team.
    """
    games = player["games"] or 0
    starts = player["games_starts"] or 0
    if games == 0:
        return 0.0

    score = games * 2.0 + starts * 3.0

    if player["is_goalkeeper"] and player["gk_saves"] is not None:
        score += (player["gk_saves"] or 0) * 0.5
        score += (player["gk_clean_sheets"] or 0) * 2.0
    else:
        score += (player["goals"] or 0) * 4.0
        score += (player["assists"] or 0) * 3.0

    return score


def key_players_for_team(team_name: str, limit: int = KEY_PLAYER_COUNT) -> list[dict[str, Any]]:
    """
    The handful of players a team profile should lead with.

    The captain is always first — he is the one player whose prominence is a
    recorded fact rather than a ranking — and the rest follow by ``_importance``.
    Players with no appearances are excluded outright: a squad member who never
    took the field cannot be a key player, and padding the list with him would
    put an empty card on the page purely to reach a target count. That means a
    team with very few players used returns fewer than ``limit`` entries, which
    is the honest outcome.

    A team's goalkeeper is guaranteed a place if one played at all. Pure
    importance scoring left two of the 48 teams (Iraq, Senegal) with no keeper
    in the top 8 — their backups' start counts were simply lower than the
    outfield regulars', not because either team lacked a keeper who played. A
    football team profile without its own goalkeeper reads as broken regardless
    of how the ranking arithmetic landed, so the highest-``_importance`` keeper
    who actually played replaces the single weakest non-captain slot, and the
    remaining players stay sorted by the same score. This never invents a
    keeper: a team where no goalkeeper played at all (games == 0 for all of
    them) still has none here, which is the honest result of that data.
    """
    squad = squad_for_team(team_name)
    if not squad:
        return []

    captain = captain_for_team(team_name)
    captain_name = captain["name"] if captain else None

    ranked = sorted(
        (p for p in squad if (p["games"] or 0) > 0 and p["name"] != captain_name),
        key=lambda p: (-_importance(p), p["name"]),
    )

    chosen = ([captain] if captain else []) + ranked
    chosen = chosen[:limit]

    if not any(p["is_goalkeeper"] for p in chosen):
        goalkeepers = [p for p in ranked if p["is_goalkeeper"]]
        if goalkeepers:
            best_gk = goalkeepers[0]  # `ranked` is already sorted by -_importance
            head = chosen[:1] if captain else []
            tail = chosen[1:] if captain else chosen
            tail = sorted(tail[:-1] + [best_gk], key=lambda p: (-_importance(p), p["name"]))
            chosen = head + tail

    return chosen


def team_squad_summary(team_name: str) -> dict[str, Any]:
    """Squad, captain and a few aggregate totals for one team."""
    squad = squad_for_team(team_name)
    played = [p for p in squad if (p["games"] or 0) > 0]
    return {
        "team": team_name,
        "squad_size": len(squad),
        "players_with_appearances": len(played),
        "captain": captain_for_team(team_name),
        "key_players": key_players_for_team(team_name),
        "players": squad,
        "total_goals": sum(p["goals"] or 0 for p in squad),
        "total_assists": sum(p["assists"] or 0 for p in squad),
        "total_minutes": sum(p["minutes"] or 0 for p in squad),
    }


def mapped_team_names() -> set[str]:
    """Every registry team name this module can serve a squad for."""
    return set(_players_by_team())


# ─── Player imagery ──────────────────────────────────────────────────────────
#
# PLAYER_IMAGE_POLICY: there are no player photographs in this product, and that
# is a deliberate, documented gap rather than an oversight.
#
#   * players.csv has no photo/image/URL column of any kind.
#   * FIFA's official 2026 teams page renders its squads client-side; fetching it
#     server-side returns an empty document, and FIFA publishes no public squad
#     API. There is no supported way to consume those images.
#   * Hot-linking FIFA (or any third party) would put an uncacheable external
#     request on every card, outside our control and of unclear licensing.
#
# Inventing photographs, or pointing at scraped image hosts, would breach the
# data-honesty rule that governs the rest of this codebase. The UI therefore
# renders a typographic monogram plus the team's local SVG flag, which is honest
# about what is known. If a licensed image source is added later, the single
# place to wire it in is the player card's avatar component.
PLAYER_IMAGE_POLICY = "no-licensed-source-available"
