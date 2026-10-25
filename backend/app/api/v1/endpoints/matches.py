from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.schemas.match import (
    PaginatedMatchResponse,
    MatchDetailResponse,
    TournamentStatsResponse,
    ScorelineFrequency,
)
from app.services.match_service import (
    get_matches,
    get_match_by_id,
    get_tournaments,
    get_tournament_stats,
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
    from_date: Optional[date_type] = None,
    to_date: Optional[date_type] = None,
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


@router.get("/analytics/scorelines", response_model=list[ScorelineFrequency])
async def scoreline_frequency(tournament: Optional[str] = None):
    """Get most common scorelines."""
    return await get_scoreline_frequency(tournament)


@router.get("/{match_id}", response_model=MatchDetailResponse)
async def get_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get match detail by id, including per-team box-score stats
    (possession/shots/corners/etc.) from team_statistics when available.
    Registered last among GET routes so it doesn't shadow the more specific
    /tournaments, /tournaments/{tournament}/stats, and /analytics/* paths.
    """
    match = await get_match_by_id(db, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match
