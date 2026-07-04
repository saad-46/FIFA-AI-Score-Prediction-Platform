"""
Team service — queries and aggregates team statistics.
"""

import logging
import uuid as uuid_module
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pandas as pd

from app.models.match import Team
from app.schemas.team import TeamResponse, TeamStatsResponse, HeadToHeadResponse, PerformanceTrendPoint
from app.ml.data.loader import load_matches_dataframe
from app.core.cache import async_ttl_cache

logger = logging.getLogger(__name__)


def _is_valid_uuid(value: str) -> bool:
    """
    team_id/home_team_id/away_team_id are native Postgres uuid columns.
    A non-UUID string (e.g. from a bad client request) would otherwise reach
    asyncpg and raise a raw DataError, surfacing as an unhandled 500. Callers
    should treat an invalid format the same as "not found".
    """
    try:
        uuid_module.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


async def search_teams(db: AsyncSession, query: str, limit: int = 10) -> list[TeamResponse]:
    """Full-text search on team name."""
    stmt = (
        select(Team)
        .where(Team.name.ilike(f"%{query}%"))
        .order_by(Team.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    teams = result.scalars().all()
    return [TeamResponse.model_validate(t) for t in teams]


async def get_team_by_id(db: AsyncSession, team_id: str) -> Optional[TeamResponse]:
    if not _is_valid_uuid(team_id):
        return None
    stmt = select(Team).where(Team.id == team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    if not team:
        return None
    return TeamResponse.model_validate(team)


async def get_team_stats(
    db: AsyncSession,
    team_id: str,
    tournament: Optional[str] = None,
    years: Optional[int] = None,
) -> Optional[TeamStatsResponse]:
    """Compute team statistics from match history."""
    if not _is_valid_uuid(team_id):
        return None

    # Get team name
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        return None

    df = await load_matches_dataframe()

    # Filter
    mask = (df["home_team"] == team.name) | (df["away_team"] == team.name)
    if tournament:
        mask &= df["tournament"] == tournament
    if years:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        mask &= df["date"] >= cutoff

    team_df = df[mask].dropna(subset=["home_score", "away_score"])

    if len(team_df) == 0:
        return TeamStatsResponse(
            team_id=team_id,
            team_name=team.name,
            matches_played=0,
            wins=0, draws=0, losses=0,
            goals_scored=0, goals_conceded=0,
            goal_difference=0, win_rate=0.0,
            avg_goals_scored=0.0, avg_goals_conceded=0.0,
            clean_sheets=0, form=[],
        )

    wins, draws, losses = 0, 0, 0
    goals_scored, goals_conceded, clean_sheets = 0, 0, 0
    form = []

    for _, row in team_df.iterrows():
        if row["home_team"] == team.name:
            gs, gc = int(row["home_score"]), int(row["away_score"])
        else:
            gs, gc = int(row["away_score"]), int(row["home_score"])

        goals_scored += gs
        goals_conceded += gc
        if gc == 0:
            clean_sheets += 1

        if gs > gc:
            wins += 1
            form.append("W")
        elif gs == gc:
            draws += 1
            form.append("D")
        else:
            losses += 1
            form.append("L")

    n = len(team_df)
    return TeamStatsResponse(
        team_id=team_id,
        team_name=team.name,
        matches_played=n,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_scored=goals_scored,
        goals_conceded=goals_conceded,
        goal_difference=goals_scored - goals_conceded,
        win_rate=wins / n,
        avg_goals_scored=goals_scored / n,
        avg_goals_conceded=goals_conceded / n,
        clean_sheets=clean_sheets,
        form=form[-5:],
    )


async def get_head_to_head(
    db: AsyncSession,
    home_team_id: str,
    away_team_id: str,
) -> HeadToHeadResponse:
    """Head-to-head stats between two teams."""
    if not _is_valid_uuid(home_team_id) or not _is_valid_uuid(away_team_id):
        return HeadToHeadResponse(
            total_matches=0, home_team_wins=0, away_team_wins=0,
            draws=0, home_team_goals=0, away_team_goals=0,
        )

    # Get team names
    home_result = await db.execute(select(Team).where(Team.id == home_team_id))
    away_result = await db.execute(select(Team).where(Team.id == away_team_id))
    home_team = home_result.scalar_one_or_none()
    away_team = away_result.scalar_one_or_none()

    if not home_team or not away_team:
        return HeadToHeadResponse(
            total_matches=0, home_team_wins=0, away_team_wins=0,
            draws=0, home_team_goals=0, away_team_goals=0,
        )

    df = await load_matches_dataframe()
    h2h = df[
        (
            ((df["home_team"] == home_team.name) & (df["away_team"] == away_team.name))
            | ((df["home_team"] == away_team.name) & (df["away_team"] == home_team.name))
        )
    ].dropna(subset=["home_score", "away_score"])

    home_wins, away_wins, draws = 0, 0, 0
    home_goals, away_goals = 0, 0
    last_5 = []

    for _, row in h2h.iterrows():
        if row["home_team"] == home_team.name:
            hg, ag = int(row["home_score"]), int(row["away_score"])
        else:
            hg, ag = int(row["away_score"]), int(row["home_score"])

        home_goals += hg
        away_goals += ag

        if hg > ag:
            home_wins += 1
        elif hg == ag:
            draws += 1
        else:
            away_wins += 1

    # Last 5 matches
    for _, row in h2h.tail(5).iterrows():
        last_5.append({
            "date": str(row["date"].date()),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
            "tournament": row["tournament"],
        })

    return HeadToHeadResponse(
        total_matches=len(h2h),
        home_team_wins=home_wins,
        away_team_wins=away_wins,
        draws=draws,
        home_team_goals=home_goals,
        away_team_goals=away_goals,
        last_5_matches=last_5,
    )


async def get_performance_trend(
    db: AsyncSession,
    team_id: str,
    months: int = 24,
) -> list[PerformanceTrendPoint]:
    """Monthly performance trend."""
    if not _is_valid_uuid(team_id):
        return []

    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        return []

    df = await load_matches_dataframe()
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
    mask = (
        ((df["home_team"] == team.name) | (df["away_team"] == team.name))
        & (df["date"] >= cutoff)
    )
    team_df = df[mask].dropna(subset=["home_score", "away_score"]).copy()
    team_df["month"] = team_df["date"].dt.to_period("M")

    trend = []
    for period, group in team_df.groupby("month"):
        wins, draws, losses = 0, 0, 0
        goals_scored, goals_conceded = 0, 0
        for _, row in group.iterrows():
            if row["home_team"] == team.name:
                gs, gc = int(row["home_score"]), int(row["away_score"])
            else:
                gs, gc = int(row["away_score"]), int(row["home_score"])
            goals_scored += gs
            goals_conceded += gc
            if gs > gc:
                wins += 1
            elif gs == gc:
                draws += 1
            else:
                losses += 1
        trend.append(PerformanceTrendPoint(
            date=str(period),
            wins=wins,
            draws=draws,
            losses=losses,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
        ))

    return trend


def _compute_all_team_stats(
    df: pd.DataFrame,
    team_names: list[str],
    tournament: Optional[str] = None,
) -> dict[str, dict]:
    """
    Compute win/draw/loss/goals stats for many teams in a single vectorised
    pass, instead of one full-DataFrame scan + Python loop per team.

    Used by get_top_teams(), which previously called get_team_stats() (one
    DB round-trip + one full-history .iterrows() scan) once per team —
    O(200) DB queries and O(200) O(n) scans for a single request. This
    builds one "long form" frame (two rows per match: one per team) and
    aggregates with a single groupby, giving every team's stats in one pass.

    Returns
    -------
    dict[team_name, {"matches_played", "wins", "draws", "losses",
                      "goals_scored", "goals_conceded", "clean_sheets"}]
    """
    valid = df.dropna(subset=["home_score", "away_score"])
    if tournament:
        valid = valid[valid["tournament"] == tournament]
    if len(valid) == 0:
        return {}

    home_rows = pd.DataFrame({
        "team": valid["home_team"].values,
        "gs": valid["home_score"].values,
        "gc": valid["away_score"].values,
    })
    away_rows = pd.DataFrame({
        "team": valid["away_team"].values,
        "gs": valid["away_score"].values,
        "gc": valid["home_score"].values,
    })
    long_df = pd.concat([home_rows, away_rows], ignore_index=True)
    long_df = long_df[long_df["team"].isin(team_names)]

    if len(long_df) == 0:
        return {}

    long_df["win"] = (long_df["gs"] > long_df["gc"]).astype(int)
    long_df["draw"] = (long_df["gs"] == long_df["gc"]).astype(int)
    long_df["loss"] = (long_df["gs"] < long_df["gc"]).astype(int)
    long_df["clean_sheet"] = (long_df["gc"] == 0).astype(int)

    grouped = long_df.groupby("team", sort=False).agg(
        matches_played=("team", "count"),
        wins=("win", "sum"),
        draws=("draw", "sum"),
        losses=("loss", "sum"),
        goals_scored=("gs", "sum"),
        goals_conceded=("gc", "sum"),
        clean_sheets=("clean_sheet", "sum"),
    )

    return {
        team: {
            "matches_played": int(row["matches_played"]),
            "wins": int(row["wins"]),
            "draws": int(row["draws"]),
            "losses": int(row["losses"]),
            "goals_scored": int(row["goals_scored"]),
            "goals_conceded": int(row["goals_conceded"]),
            "clean_sheets": int(row["clean_sheets"]),
        }
        for team, row in grouped.iterrows()
    }


@async_ttl_cache(ttl_seconds=60, max_size=64, ignore_args={0})
async def get_top_teams(
    db: AsyncSession,
    limit: int = 10,
    tournament: Optional[str] = None,
) -> list[TeamStatsResponse]:
    """
    Get top teams by win rate.

    Cached in-process for 60s (keyed on limit/tournament, not the DB
    session) — this is a read-heavy endpoint (dashboard + /teams/top) whose
    underlying data (the matches table) doesn't change within a request
    burst, and the source DataFrame itself is already only refreshed every
    6h. No Redis in this stack (see requirements.txt), so a short in-process
    TTL is the appropriate tradeoff: it caps recompute frequency without
    risking long-lived staleness.
    """
    stmt = select(Team).order_by(Team.name).limit(200)
    result = await db.execute(stmt)
    teams = result.scalars().all()

    df = await load_matches_dataframe()
    stats_by_name = _compute_all_team_stats(df, [t.name for t in teams], tournament=tournament)

    stats_list = []
    for team in teams:
        s = stats_by_name.get(team.name)
        # Threshold lowered from 10 (calibrated for the old, superseded
        # broad "all competitions" dataset, where 10+ matches per team was
        # a low bar) to 2 -- the live matches table is now correctly scoped
        # to the WC-only corpus (see loader.py's data_source filter), where
        # a team playing in a single World Cup only has 3-7 matches total.
        # A threshold of 10 was unreachable for every team post-fix, making
        # this endpoint always return an empty list.
        if not s or s["matches_played"] < 2:
            continue
        n = s["matches_played"]
        stats_list.append(
            TeamStatsResponse(
                team_id=team.id,
                team_name=team.name,
                matches_played=n,
                wins=s["wins"],
                draws=s["draws"],
                losses=s["losses"],
                goals_scored=s["goals_scored"],
                goals_conceded=s["goals_conceded"],
                goal_difference=s["goals_scored"] - s["goals_conceded"],
                win_rate=s["wins"] / n,
                avg_goals_scored=s["goals_scored"] / n,
                avg_goals_conceded=s["goals_conceded"] / n,
                clean_sheets=s["clean_sheets"],
                form=[],
            )
        )

    stats_list.sort(key=lambda s: s.win_rate, reverse=True)
    return stats_list[:limit]
