"""
Match service — queries match history and analytics.
"""

import logging
import math
from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload, aliased
import pandas as pd

from app.models.match import Match, Team
from app.schemas.analytics import UpcomingMatchSummary
from app.schemas.match import (
    MatchResponse,
    TournamentStatsResponse,
    GoalDistributionPoint,
    ScorelineFrequency,
    PaginatedMatchResponse,
)
from app.ml.data.loader import load_matches_dataframe

logger = logging.getLogger(__name__)


async def get_matches(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    team: Optional[str] = None,
    tournament: Optional[str] = None,
    year: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> PaginatedMatchResponse:
    """Paginated match history with filters."""
    stmt = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .order_by(desc(Match.date))
    )

    if team:
        home_alias = aliased(Team)
        away_alias = aliased(Team)
        stmt = (
            stmt.join(home_alias, Match.home_team_id == home_alias.id)
            .join(away_alias, Match.away_team_id == away_alias.id)
            .where(or_(home_alias.name.ilike(f"%{team}%"), away_alias.name.ilike(f"%{team}%")))
        )
    if tournament:
        stmt = stmt.where(Match.tournament.ilike(f"%{tournament}%"))
    if year:
        stmt = stmt.where(func.extract("year", Match.date) == year)
    if from_date:
        stmt = stmt.where(Match.date >= from_date)
    if to_date:
        stmt = stmt.where(Match.date <= to_date)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_responses = []
    for m in matches:
        home_team = m.home_team
        away_team = m.away_team

        if home_team and away_team:
            match_responses.append(MatchResponse(
                id=m.id,
                date=m.date,
                home_team_id=m.home_team_id,
                away_team_id=m.away_team_id,
                home_team={"id": home_team.id, "name": home_team.name, "country": home_team.country},
                away_team={"id": away_team.id, "name": away_team.name, "country": away_team.country},
                home_score=m.home_score,
                away_score=m.away_score,
                tournament=m.tournament,
                stage=m.stage,
                neutral_venue=m.neutral_venue,
                city=m.city,
                country=m.country,
                status=m.status,
            ))

    return PaginatedMatchResponse(
        data=match_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


async def get_upcoming_matches(db: AsyncSession, limit: int = 5) -> list[UpcomingMatchSummary]:
    """Soonest scheduled (not yet played) matches, for the dashboard feed."""
    stmt = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.status == "scheduled", Match.date >= date.today())
        .order_by(Match.date.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()
    return [
        UpcomingMatchSummary(
            id=m.id,
            date=m.date,
            home_team=m.home_team.name if m.home_team else "",
            away_team=m.away_team.name if m.away_team else "",
            tournament=m.tournament,
        )
        for m in matches
    ]


async def get_tournaments(db: AsyncSession) -> list[str]:
    """Get all distinct tournament names."""
    stmt = select(Match.tournament).distinct().order_by(Match.tournament)
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def get_tournament_stats(tournament: str) -> TournamentStatsResponse:
    """Aggregate stats for a tournament."""
    df = await load_matches_dataframe()
    t_df = df[df["tournament"] == tournament].dropna(subset=["home_score", "away_score"])

    if len(t_df) == 0:
        return TournamentStatsResponse(
            tournament=tournament,
            total_matches=0,
            total_goals=0,
            avg_goals_per_match=0.0,
            home_win_rate=0.0,
            draw_rate=0.0,
            away_win_rate=0.0,
        )

    total_goals = int(t_df["home_score"].sum() + t_df["away_score"].sum())
    home_wins = (t_df["home_score"] > t_df["away_score"]).sum()
    draws = (t_df["home_score"] == t_df["away_score"]).sum()
    away_wins = (t_df["home_score"] < t_df["away_score"]).sum()
    n = len(t_df)

    # Top scoring team
    home_goals = t_df.groupby("home_team")["home_score"].sum()
    away_goals = t_df.groupby("away_team")["away_score"].sum()
    all_goals = home_goals.add(away_goals, fill_value=0)
    top_team = all_goals.idxmax() if len(all_goals) > 0 else None

    return TournamentStatsResponse(
        tournament=tournament,
        total_matches=n,
        total_goals=total_goals,
        avg_goals_per_match=total_goals / n,
        home_win_rate=home_wins / n,
        draw_rate=draws / n,
        away_win_rate=away_wins / n,
        top_scoring_team=top_team,
        most_goals_in_match=int((t_df["home_score"] + t_df["away_score"]).max()),
    )


async def get_goal_distribution(
    tournament: Optional[str] = None,
) -> list[GoalDistributionPoint]:
    """
    Goal distribution by 15-minute intervals.
    Note: Requires goal_minute data in the database.
    This returns a synthetic distribution based on known football patterns.
    """
    # KNOWN LIMITATION: matches table has no goal-minute/event-level data (see database/schema.sql) — this is a hardcoded placeholder, not derived from real data, pending a schema change owned by the DB engineer.
    distribution = [
        GoalDistributionPoint(minute=0, goals=850),
        GoalDistributionPoint(minute=15, goals=1100),
        GoalDistributionPoint(minute=30, goals=1050),
        GoalDistributionPoint(minute=45, goals=1200),
        GoalDistributionPoint(minute=60, goals=1150),
        GoalDistributionPoint(minute=75, goals=1300),
        GoalDistributionPoint(minute=90, goals=1450),
    ]
    return distribution


async def get_scoreline_frequency(
    tournament: Optional[str] = None,
) -> list[ScorelineFrequency]:
    """Most common scorelines."""
    df = await load_matches_dataframe()

    if tournament:
        df = df[df["tournament"] == tournament]

    df = df.dropna(subset=["home_score", "away_score"])
    df["scoreline"] = df["home_score"].astype(int).astype(str) + "-" + df["away_score"].astype(int).astype(str)

    counts = df["scoreline"].value_counts().head(15)
    total = len(df)

    return [
        ScorelineFrequency(
            scoreline=scoreline,
            count=int(count),
            percentage=round(count / total * 100, 2),
        )
        for scoreline, count in counts.items()
    ]
