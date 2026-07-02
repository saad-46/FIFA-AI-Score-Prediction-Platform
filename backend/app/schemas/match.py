from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class MatchResponse(BaseModel):
    id: str
    date: date
    home_team_id: str
    away_team_id: str
    home_team: dict
    away_team: dict
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    tournament: str
    stage: Optional[str] = None
    neutral_venue: bool
    city: Optional[str] = None
    country: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


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
