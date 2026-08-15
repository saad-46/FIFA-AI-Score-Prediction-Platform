"""
Match service — queries match history and analytics.
"""

import logging
import math
import uuid as uuid_module
from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import selectinload, joinedload, aliased

from app.models.match import Match, Team, TeamStatistics
from app.schemas.analytics import UpcomingMatchSummary
from app.schemas.match import (
    MatchResponse,
    MatchDetailResponse,
    TeamStatisticsResponse,
    TournamentStatsResponse,
    GoalDistributionPoint,
    ScorelineFrequency,
    PaginatedMatchResponse,
)
from app.ml.data.loader import load_matches_dataframe
from app.core.cache import async_ttl_cache

logger = logging.getLogger(__name__)


def _is_valid_uuid(value: str) -> bool:
    """See app.services.team_service._is_valid_uuid — same rationale: match_id
    is a native Postgres uuid column, and an invalid-format string would
    otherwise reach asyncpg and raise a raw DataError (unhandled 500)."""
    try:
        uuid_module.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


@async_ttl_cache(ttl_seconds=60, max_size=256, ignore_args={0})
async def get_matches(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    team: Optional[str] = None,
    tournament: Optional[str] = None,
    year: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> PaginatedMatchResponse:
    """
    Paginated match history with filters.

    Cached in-process for 60s (keyed on page/filters, not the DB session) —
    same rationale as ``get_top_teams`` below: this issues two sequential
    round trips to the DB per call (count + select) with no query-plan cost
    (~14ms server-side per EXPLAIN ANALYZE), so observed latency here is
    almost entirely network RTT to the DB. A short in-process TTL avoids
    paying that RTT twice per unique page/filter combo within a request
    burst, without risking meaningful staleness (match data changes
    infrequently; see load_matches_dataframe's own 6h refresh cadence).
    """
    # joinedload, not selectinload. Both return identical objects, but
    # selectinload resolves each relationship with its own follow-up SELECT, so
    # one page cost four sequential round trips (count, page, home teams, away
    # teams). Measured against this Supabase instance the round trip is ~120ms
    # while the queries themselves execute in 0.05-10ms server-side (EXPLAIN
    # ANALYZE; every one is an index-only scan), so latency here is round-trip
    # count, not row count. joinedload folds both teams into the page query as
    # LEFT OUTER JOINs -- 4 round trips become 2. It stays an outer join, so the
    # nullable away_team_id (TBD knockout opponents) still comes back as None
    # rather than dropping the row.
    # Match.id is a tiebreaker, not decoration. `date` is a DATE column and is
    # nowhere near unique: 49,389 rows share 16,441 distinct dates (~3 per date,
    # up to 66 on 2012-02-29). ORDER BY date DESC alone therefore isn't a total
    # order, and OFFSET/LIMIT over a non-total order is only stable for as long
    # as the plan is. Today it happens to be stable (six identical runs, zero
    # duplicates across six pages), but any plan change -- new statistics, a
    # parallel scan, a Postgres upgrade -- can reshuffle tied rows and make a
    # visitor paging through the archive see one match twice and miss another.
    # Appending the primary key costs nothing and makes the order total.
    stmt = (
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(desc(Match.date), Match.id)
    )

    if team:
        home_alias = aliased(Team)
        away_alias = aliased(Team)
        stmt = (
            stmt.join(home_alias, Match.home_team_id == home_alias.id)
            # outerjoin: away_team_id is nullable (TBD knockout opponent —
            # see DATABASE_SCHEMA.md). An inner join here would silently
            # exclude every such match from a `team` search even when the
            # *home* team matches the filter (e.g. searching "Canada" would
            # drop the Canada-vs-TBD Round-of-16 fixture entirely).
            .outerjoin(away_alias, Match.away_team_id == away_alias.id)
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

        # home_team is always required (home_team_id is NOT NULL), but
        # away_team can be genuinely absent (away_team_id is nullable — see
        # DATABASE_SCHEMA.md, TBD knockout-stage opponents). Previously this
        # required both to be truthy, which silently dropped every such
        # match from the paginated list entirely (and skewed `total` vs.
        # what was actually returned). Now only home_team is required.
        if home_team:
            match_responses.append(MatchResponse(
                id=m.id,
                date=m.date,
                home_team_id=m.home_team_id,
                away_team_id=m.away_team_id,
                home_team={"id": home_team.id, "name": home_team.name, "country": home_team.country},
                away_team=(
                    {"id": away_team.id, "name": away_team.name, "country": away_team.country}
                    if away_team else None
                ),
                home_score=m.home_score,
                away_score=m.away_score,
                tournament=m.tournament,
                stage=m.stage,
                stage_id=m.stage_id,
                tournament_year=m.tournament_year,
                neutral_venue=m.neutral_venue,
                city=m.city,
                country=m.country,
                home_xg=float(m.home_xg) if m.home_xg is not None else None,
                away_xg=float(m.away_xg) if m.away_xg is not None else None,
                status=m.status,
            ))

    return PaginatedMatchResponse(
        data=match_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


async def get_match_by_id(db: AsyncSession, match_id: str) -> Optional[MatchDetailResponse]:
    """
    Match detail, including per-team box-score stats from team_statistics
    when available (see DATABASE_SCHEMA.md — 10 completed 2026 matches have
    no stats rows, a documented source gap; team_statistics is simply empty
    for those, never fabricated).
    """
    if not _is_valid_uuid(match_id):
        return None

    stmt = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.id == match_id)
    )
    result = await db.execute(stmt)
    m = result.scalar_one_or_none()
    if not m or not m.home_team:
        return None

    stats_stmt = (
        select(TeamStatistics)
        .options(selectinload(TeamStatistics.team))
        .where(TeamStatistics.match_id == match_id)
    )
    stats_result = await db.execute(stats_stmt)
    stats_rows = stats_result.scalars().all()

    team_statistics = [
        TeamStatisticsResponse(
            team_id=s.team_id,
            team_name=s.team.name if s.team else "",
            possession_pct=s.possession_pct,
            total_shots=s.total_shots,
            shots_on_target=s.shots_on_target,
            corners=s.corners,
            fouls=s.fouls,
            offsides=s.offsides,
            saves=s.saves,
            player_of_the_match=s.player_of_the_match,
        )
        for s in stats_rows
    ]

    away_team = m.away_team
    return MatchDetailResponse(
        id=m.id,
        date=m.date,
        home_team_id=m.home_team_id,
        away_team_id=m.away_team_id,
        home_team={"id": m.home_team.id, "name": m.home_team.name, "country": m.home_team.country},
        away_team=(
            {"id": away_team.id, "name": away_team.name, "country": away_team.country}
            if away_team else None
        ),
        home_score=m.home_score,
        away_score=m.away_score,
        tournament=m.tournament,
        stage=m.stage,
        stage_id=m.stage_id,
        tournament_year=m.tournament_year,
        neutral_venue=m.neutral_venue,
        city=m.city,
        country=m.country,
        home_xg=float(m.home_xg) if m.home_xg is not None else None,
        away_xg=float(m.away_xg) if m.away_xg is not None else None,
        status=m.status,
        team_statistics=team_statistics,
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


@async_ttl_cache(ttl_seconds=300, max_size=1, ignore_args={0})
async def get_tournaments(db: AsyncSession) -> list[str]:
    """
    Get all distinct tournament names.

    Cached for 5 minutes. The /matches page loads this alongside every match
    page to populate the tournament filter, and it was the single most
    expensive call on that screen (~1.6s per request end to end) despite the
    query itself running in ~10ms server-side on an index-only scan of
    idx_matches_tournament -- the cost is the round trip, paid on every visit.
    The result is a fixed list of seven World Cup names that only changes when
    a new tournament is imported, so a short TTL is safe; the ttl is longer
    than get_matches' 60s because this is even more static.
    """
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
