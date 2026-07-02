from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class RecentPredictionSummary(BaseModel):
    """Lightweight view of a user's saved prediction for the dashboard feed."""
    id: str
    home_team: str
    away_team: str
    predicted_home_score: int
    predicted_away_score: int
    confidence_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TopTeamSummary(BaseModel):
    """Lightweight team ranking entry for the dashboard."""
    team_id: str
    team_name: str
    win_rate: float
    matches_played: int


class UpcomingMatchSummary(BaseModel):
    """Lightweight upcoming-fixture entry for the dashboard."""
    id: str
    date: date
    home_team: str
    away_team: str
    tournament: str


class GoalsByYearPoint(BaseModel):
    year: int
    goals: int
    matches: int


class TopTournamentPoint(BaseModel):
    tournament: str
    matches: int


class GlobalAnalyticsResponse(BaseModel):
    total_matches: int
    total_goals: int
    avg_goals_per_match: float
    home_win_rate: float
    draw_rate: float
    away_win_rate: float
    goals_by_year: List[GoalsByYearPoint] = Field(default_factory=list)
    top_tournaments: List[TopTournamentPoint] = Field(default_factory=list)


class ModelMetricsResponse(BaseModel):
    accuracy: float
    mae: float
    rmse: float
    last_trained: str
    training_samples: int
    model_version: str


class DashboardStatsResponse(BaseModel):
    total_predictions: int
    accuracy_rate: float
    total_matches_analyzed: int
    total_teams: int
    recent_predictions: List[RecentPredictionSummary] = Field(default_factory=list)
    top_teams: List[TopTeamSummary] = Field(default_factory=list)
    upcoming_matches: List[UpcomingMatchSummary] = Field(default_factory=list)
