from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class MatchResponse(BaseModel):
    id: str
    date: date
    home_team_id: str
    # Nullable: a small number of knockout-stage fixtures have a genuinely
    # unresolved opponent slot (e.g. WC2026 Round-of-16 TBD advancement) —
    # see DATABASE_SCHEMA.md. away_team/away_team_id are None in that case,
    # not a fabricated placeholder.
    away_team_id: Optional[str] = None
    home_team: dict
    away_team: Optional[dict] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    tournament: str
    stage: Optional[str] = None
    stage_id: Optional[int] = None
    tournament_year: Optional[int] = None
    neutral_venue: bool
    city: Optional[str] = None
    country: Optional[str] = None
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
    status: str

    model_config = {"from_attributes": True}


class TeamStatisticsResponse(BaseModel):
    """Per-team box-score stats for one match. See DATABASE_SCHEMA.md
    (team_statistics) — grain is (match_id, team_id), one row per team."""
    team_id: str
    team_name: str
    possession_pct: Optional[int] = None
    total_shots: Optional[int] = None
    shots_on_target: Optional[int] = None
    corners: Optional[int] = None
    fouls: Optional[int] = None
    offsides: Optional[int] = None
    saves: Optional[int] = None
    player_of_the_match: Optional[str] = None

    model_config = {"from_attributes": True}


class MatchDetailResponse(MatchResponse):
    """Match detail, extending MatchResponse with per-team box-score stats
    from team_statistics when available (not all matches have rows there —
    see DATABASE_SCHEMA.md's documented source gap for 10 completed 2026
    matches)."""
    team_statistics: List[TeamStatisticsResponse] = Field(default_factory=list)


class TournamentStatsResponse(BaseModel):
    tournament: str
    total_matches: int
    total_goals: int
    avg_goals_per_match: float
    home_win_rate: float
    draw_rate: float
    away_win_rate: float
    top_scoring_team: Optional[str] = None
    most_goals_in_match: Optional[int] = None


class GoalDistributionPoint(BaseModel):
    minute: int
    goals: int
    # True until the DB stores goal-minute events; see match_service.get_goal_distribution.
    is_synthetic: bool = True


class ScorelineFrequency(BaseModel):
    scoreline: str
    count: int
    percentage: float


class PaginatedMatchResponse(BaseModel):
    data: List[MatchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
