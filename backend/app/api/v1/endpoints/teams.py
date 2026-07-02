from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.schemas.team import (
    TeamResponse,
    TeamStatsResponse,
    HeadToHeadResponse,
    PerformanceTrendPoint,
)
from app.services.team_service import (
    search_teams,
    get_team_by_id,
    get_team_stats,
    get_head_to_head,
    get_performance_trend,
    get_top_teams,
)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/search", response_model=list[TeamResponse])
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """Search teams by name."""
    return await search_teams(db, q)


@router.get("/top", response_model=list[TeamStatsResponse])
async def top_teams(
    limit: int = Query(10, ge=1, le=50),
    tournament: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get top teams by win rate."""
    return await get_top_teams(db, limit=limit, tournament=tournament)


@router.get("/head-to-head", response_model=HeadToHeadResponse)
async def head_to_head(
    home_team_id: str,
    away_team_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Head-to-head stats between two teams."""
    return await get_head_to_head(db, home_team_id, away_team_id)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get team by ID."""
    team = await get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.get("/{team_id}/stats", response_model=TeamStatsResponse)
async def team_stats(
    team_id: str,
    tournament: Optional[str] = None,
    years: Optional[int] = Query(None, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get team statistics."""
    stats = await get_team_stats(db, team_id, tournament=tournament, years=years)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return stats


@router.get("/{team_id}/trend", response_model=list[PerformanceTrendPoint])
async def performance_trend(
    team_id: str,
    months: int = Query(24, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
):
    """Get team performance trend over time."""
    return await get_performance_trend(db, team_id, months=months)
