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
from app.schemas.squad import TeamSquadResponse
from app.schemas.wc2026 import WorldCupHeadToHeadResponse
from app.services.team_service import (
    search_teams,
    get_team_by_id,
    get_team_stats,
    get_head_to_head,
    get_performance_trend,
    get_top_teams,
    get_wc2026_teams,
)
from app.data import players as players_data
from app.data import wc2026 as wc2026_data

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/wc2026", response_model=list[TeamResponse])
async def wc2026_teams(db: AsyncSession = Depends(get_db)):
    """
    The 48 teams at the 2026 World Cup, alphabetically.

    Use this — not `/teams/top` — for the team directory. `/teams/top` returns
    a win-rate leaderboard capped at `limit`, and the underlying table also
    holds non-national entities from the legacy seed; see
    `team_service.get_wc2026_teams` for why scoping rather than deleting is the
    correct fix.
    """
    return await get_wc2026_teams(db)


@router.get("/world-cup-head-to-head", response_model=WorldCupHeadToHeadResponse)
async def world_cup_head_to_head(
    team_a: str = Query(..., min_length=2, description="Canonical team name, e.g. 'Spain'"),
    team_b: str = Query(..., min_length=2, description="Canonical team name, e.g. 'Argentina'"),
):
    """
    World Cup meetings between two teams across the canonical 1930-2026 corpus.

    Distinct from `/teams/head-to-head`, which reads the model-serving
    DataFrame — that population only starts in 2002 and so reported "no
    previous meetings" for pairs who met earlier (Spain v Argentina, 1966).
    Clients must render `scope_label`: the corpus is World Cup only, so zero
    meetings does not mean two teams have never played.
    """
    return wc2026_data.world_cup_head_to_head(team_a, team_b)


@router.get("/{team_id}/squad", response_model=TeamSquadResponse)
async def team_squad(team_id: str, db: AsyncSession = Depends(get_db)):
    """
    The 26-player squad, captain and squad totals for one WC2026 team.

    Deliberately one request for the whole team page: the squad, the captain and
    every per-player statistic the detail view renders come back together, so a
    26-card grid costs one call rather than 26. The player data is a cached
    in-process read of a committed CSV, so this adds no database work beyond the
    single lookup that resolves team_id to a name.

    404s when the id is unknown; 404s too when the team has no squad on record,
    which is how a non-WC2026 team from the legacy seed is rejected rather than
    returned as an empty roster.
    """
    team = await get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    summary = players_data.team_squad_summary(team.name)
    if not summary["players"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No squad on record for {team.name}",
        )

    return TeamSquadResponse(
        fifa_code=team.fifa_code,
        wc2026_group=team.wc2026_group,
        **summary,
    )


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
