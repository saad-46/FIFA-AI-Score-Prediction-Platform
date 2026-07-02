from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.schemas.match import (
    PaginatedMatchResponse,
    TournamentStatsResponse,
    GoalDistributionPoint,
    ScorelineFrequency,
)
from app.services.match_service import (
    get_matches,
    get_tournaments,
    get_tournament_stats,
    get_goal_distribution,
    get_scoreline_frequency,
)

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=PaginatedMatchResponse)
async def list_matches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    team: Optional[str] = None,
    tournament: Optional[str] = None,
    year: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get paginated match history."""
    return await get_matches(
        db,
        page=page,
        page_size=page_size,
        team=team,
        tournament=tournament,
        year=year,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/tournaments", response_model=list[str])
async def list_tournaments(db: AsyncSession = Depends(get_db)):
    """Get all available tournament names."""
    return await get_tournaments(db)


@router.get("/tournaments/{tournament}/stats", response_model=TournamentStatsResponse)
async def tournament_stats(tournament: str):
    """Get statistics for a specific tournament."""
    return await get_tournament_stats(tournament)


@router.get("/analytics/goal-distribution", response_model=list[GoalDistributionPoint])
async def goal_distribution(tournament: Optional[str] = None):
    """Get goal distribution by minute. Currently synthetic — see GoalDistributionPoint.is_synthetic."""
    return await get_goal_distribution(tournament)


@router.get("/analytics/scorelines", response_model=list[ScorelineFrequency])
async def scoreline_frequency(tournament: Optional[str] = None):
    """Get most common scorelines."""
    return await get_scoreline_frequency(tournament)
