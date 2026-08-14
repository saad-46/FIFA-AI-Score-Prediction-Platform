import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import check_rate_limit, simulation_rule
from app.core.security import get_optional_user
from app.db.database import get_db
from app.schemas.tournament import (
    TournamentSimulationRequest,
    TournamentSimulationResponse,
    TeamTournamentStats,
    Fifa2026GroupsResponse,
    Fifa2026Group,
    Fifa2026ScheduleResponse,
)
from app.schemas.wc2026 import (
    BacktestResponse,
    BracketResponse,
    StandingsResponse,
    TeamMetaResponse,
)
from app.ml.tournament_simulator import TournamentSimulator, TournamentSimulationError
from app.ml.models.predictor import MatchPredictor
from app.ml.data.loader import load_matches_dataframe
from app.data.fifa_2026 import load_groups, get_groups_as_team_codes, filter_schedule
from app.data import wc2026 as wc2026_data
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tournament", tags=["tournament"])

# Global predictor and dataframe cache for tournament simulations
_predictor_cache = None
_df_cache = None

async def _get_simulator_dependencies():
    global _predictor_cache, _df_cache
    if _predictor_cache is None:
        _predictor_cache = MatchPredictor()
        _predictor_cache.load()
    if _df_cache is None:
        _df_cache = await load_matches_dataframe()
    return _predictor_cache, _df_cache


@router.get("/2026/groups", response_model=Fifa2026GroupsResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_groups():
    """
    Get the official FIFA World Cup 2026 groups (A-L, 48 teams total).
    Public, read-only endpoint. Data is sourced from the official wallchart;
    see app/data/fifa_2026/README.md for provenance.
    """
    groups_raw = load_groups()
    groups = [
        Fifa2026Group(name=name, teams=teams)
        for name, teams in groups_raw.items()
    ]
    return Fifa2026GroupsResponse(groups=groups)


@router.get("/2026/schedule", response_model=Fifa2026ScheduleResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_schedule(
    stage: Optional[str] = Query(
        None,
        description="Filter by stage, e.g. 'group_stage', 'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final'",
    ),
    venue_city: Optional[str] = Query(None, description="Filter by host city, e.g. 'Mexico City'"),
):
    """
    Get the official FIFA World Cup 2026 match schedule (104 fixtures).
    Optionally filter by stage and/or venue_city.
    Public, read-only endpoint. Data is sourced from the official wallchart;
    see app/data/fifa_2026/README.md for provenance.
    """
    matches = filter_schedule(stage=stage, venue_city=venue_city)
    return Fifa2026ScheduleResponse(matches=matches)


@router.get("/2026/bracket", response_model=BracketResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_bracket():
    """
    Full WC2026 bracket: all 104 matches with real results, the frozen model's
    pre-tournament prediction for each, and the progression wiring
    (`home_source`/`away_source`/`feeds_winner_to`/`feeds_loser_to`) from the
    canonical tournament graph.

    Public, read-only. The graph is the source of truth for bracket shape — a
    client should never hardcode these relationships. Not rate limited: this
    is a cached file read, unlike `/simulate`.
    """
    return wc2026_data.build_bracket()


@router.get("/2026/standings", response_model=StandingsResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_standings():
    """
    Final group tables (A-L) computed from the canonical group-stage results.

    Public, read-only. Ordered by points, goal difference, then goals for; see
    ``app/data/wc2026`` for why the full FIFA tiebreak chain is not reproduced.
    """
    return {"groups": wc2026_data.build_standings()}


@router.get("/2026/teams", response_model=TeamMetaResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_team_meta():
    """
    Pre-tournament reference data for the 48 WC2026 teams (code, confederation,
    group, FIFA ranking, Elo), keyed by canonical team name.

    These are the values the frozen model actually saw, so they are consistent
    with the predictions served alongside them.
    """
    return {"teams": wc2026_data.load_wc2026_teams()}


@router.get("/2026/backtest", response_model=BacktestResponse, status_code=status.HTTP_200_OK)
async def get_fifa_2026_backtest():
    """
    How the frozen model (`v2.1.0-historical-optimized`) actually did across
    all 104 WC2026 matches, broken down by stage.

    This is a **historical evaluation**, not a forecast: the model was frozen
    before any 2026 result was compared against it, and this scorecard never
    fed back into it. Clients must label it as a backtest.
    """
    return wc2026_data.build_backtest()


@router.post("/simulate", response_model=TournamentSimulationResponse, status_code=status.HTTP_200_OK)
async def simulate_tournament(
    payload: TournamentSimulationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Run Monte Carlo simulations for a FIFA 2026 World Cup tournament.
    Supports 48 teams in 12 groups with Round of 32 knockout.
    Public endpoint, rate limited far more strictly than /predictions/predict —
    a single call is several seconds of multi-process CPU (see
    app/core/rate_limit.py::simulation_rule).
    """
    await check_rate_limit(db, simulation_rule(), request, user)

    predictor, df = await _get_simulator_dependencies()
    
    if not predictor.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictor model is not loaded. Cannot run simulation."
        )

    # Convert groups list to dict. If the caller asked for the official FIFA 2026
    # groups, use the reference data instead of the client-submitted groups.
    if payload.use_fifa_2026_groups:
        groups_dict = get_groups_as_team_codes()
    else:
        groups_dict = {group.name: group.teams for group in payload.groups}

    # Real completed-match substitution only makes sense against the real
    # FIFA 2026 bracket (team codes) — custom/hypothetical groups use
    # caller-defined labels that can never coincide with a real fixture, so
    # forcing it off there avoids doing pointless lookup work.
    use_real_results = payload.use_real_results and payload.use_fifa_2026_groups
    simulator = TournamentSimulator(predictor, df, use_real_results=use_real_results)

    # Run CPU bound simulation in a threadpool
    try:
        raw_probs = await asyncio.to_thread(
            simulator.simulate_tournament,
            groups_dict,
            payload.n_simulations
        )
    except TournamentSimulationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Simulation could not produce trustworthy results: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Tournament simulation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Simulation failed. Please try again later.",
        )
        
    # Map to schema (lowercase keys from Phase 3 rewrite)
    formatted_probs = {}
    for team, stats in raw_probs.items():
        formatted_probs[team] = TeamTournamentStats(
            group=stats.get("group", 1.0),
            r32=stats.get("r32", 0.0),
            r16=stats.get("r16", 0.0),
            qf=stats.get("qf", 0.0),
            sf=stats.get("sf", 0.0),
            third_place=stats.get("third_place", 0.0),
            final=stats.get("final", 0.0),
            winner=stats.get("winner", 0.0),
        )

    return TournamentSimulationResponse(probabilities=formatted_probs)

