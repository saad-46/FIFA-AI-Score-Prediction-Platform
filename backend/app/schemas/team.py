from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TeamBase(BaseModel):
    name: str
    country: str
    confederation: Optional[str] = None
    fifa_ranking: Optional[int] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None
    home_stadium: Optional[str] = None


class TeamResponse(TeamBase):
    id: str
    # WC2026 ranking/Elo fields — see DATABASE_SCHEMA.md / RANKINGS_INTEGRATION.md.
    # NULL for historical-only teams not in the 2026 field (see teams_reference.csv
    # coverage gap documented there); never fabricated.
    elo_rating: Optional[int] = None
    fifa_code: Optional[str] = None
    wc2026_group: Optional[str] = None
    ranking_updated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamStatsResponse(BaseModel):
    team_id: str
    team_name: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    win_rate: float
    avg_goals_scored: float
    avg_goals_conceded: float
    clean_sheets: int
    form: List[str] = []  # Last 5 results: ["W", "D", "L", ...]


class HeadToHeadResponse(BaseModel):
    total_matches: int
    home_team_wins: int
    away_team_wins: int
    draws: int
    home_team_goals: int
    away_team_goals: int
    last_5_matches: List[dict] = []


class PerformanceTrendPoint(BaseModel):
    date: str
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
