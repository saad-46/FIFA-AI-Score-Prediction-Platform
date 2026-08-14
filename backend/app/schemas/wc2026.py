"""
Schemas for the read-only WC2026 tournament-structure endpoints.

Kept in their own module rather than appended to ``schemas/tournament.py`` so
the pre-existing simulation/wallchart contracts stay untouched — nothing here
modifies a shape the frontend already depends on.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MatchSource(BaseModel):
    """Where a fixture's participant comes from, per the tournament graph."""

    type: str = Field(
        ...,
        description="'group_fixture', 'group_qualification', 'winner_of' or 'loser_of'",
    )
    match_number: Optional[int] = Field(
        None, description="Feeder match, set when type is winner_of/loser_of"
    )


class BracketMatchPrediction(BaseModel):
    """The frozen model's pre-tournament call for this fixture."""

    predicted_winner: Optional[str] = None
    home_win_probability: Optional[float] = None
    draw_probability: Optional[float] = None
    away_win_probability: Optional[float] = None
    predicted_home_goals: Optional[float] = None
    predicted_away_goals: Optional[float] = None
    most_likely_score: Optional[str] = None
    model_version: Optional[str] = None


class BracketNode(BaseModel):
    match_number: int = Field(..., description="Match number, 1-104")
    stage: str
    is_knockout: bool
    group: Optional[str] = Field(None, description="e.g. 'Group A', group stage only")
    date: Optional[str] = None
    kickoff_time_et: Optional[str] = None
    venue: Optional[str] = None
    city: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_score: Optional[int] = Field(None, description="Full-time score")
    away_score: Optional[int] = Field(None, description="Full-time score")
    home_score_et: Optional[int] = Field(
        None, description="Score after extra time (total, not ET-only goals)"
    )
    away_score_et: Optional[int] = None
    home_penalties: Optional[int] = None
    away_penalties: Optional[int] = None
    result_method: Optional[str] = Field(
        None, description="'Normal Time', 'Extra Time', 'Penalties' or 'Draw'"
    )
    winner_team: Optional[str] = None
    status: str = Field(..., description="'completed' or 'scheduled'")
    home_source: Optional[MatchSource] = None
    away_source: Optional[MatchSource] = None
    feeds_winner_to: Optional[int] = None
    feeds_loser_to: Optional[int] = None
    prediction: Optional[BracketMatchPrediction] = None


class StageRange(BaseModel):
    stage: str
    first: int
    last: int


class BracketResponse(BaseModel):
    format: Optional[str] = None
    stage_ranges: List[StageRange] = Field(
        ..., description="Match-number span of each stage, in playing order"
    )
    nodes: List[BracketNode] = Field(..., description="All 104 matches")


class StandingRow(BaseModel):
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    position: int


class GroupStanding(BaseModel):
    group: str = Field(..., description="Group letter, 'A'-'L'")
    standings: List[StandingRow]


class StandingsResponse(BaseModel):
    groups: List[GroupStanding]


class BacktestStageAccuracy(BaseModel):
    stage: str
    correct: int
    total: int
    accuracy: float


class BacktestMatch(BaseModel):
    match_number: Optional[int] = None
    match: Optional[str] = None
    stage: str
    predicted: Optional[str] = None
    actual: Optional[str] = None
    correct: bool
    home_win_probability: Optional[float] = None
    draw_probability: Optional[float] = None
    away_win_probability: Optional[float] = None
    predicted_score: Optional[str] = None
    actual_score: Optional[str] = None


class BacktestResponse(BaseModel):
    """A historical evaluation of a model frozen before any 2026 result was
    seen — never a forecast. Field names and the note deliberately keep that
    framing so the UI cannot present it as one."""

    model_version: Optional[str] = None
    n_matches_scored: Optional[int] = None
    accuracy: Optional[float] = None
    correct: int
    by_stage: List[BacktestStageAccuracy]
    actual_champion: Optional[str] = None
    predicted_champion: Optional[str] = None
    note: Optional[str] = None
    matches: List[BacktestMatch]

    model_config = {"protected_namespaces": ()}


class TeamMetaResponse(BaseModel):
    """Per-team WC2026 reference data, keyed by canonical team name."""

    teams: Dict[str, Any]
