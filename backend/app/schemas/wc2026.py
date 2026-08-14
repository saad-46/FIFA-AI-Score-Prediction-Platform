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


class WorldCupMeeting(BaseModel):
    date: Optional[str] = None
    year: Optional[int] = None
    stage: Optional[str] = None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    display_score: Optional[str] = Field(
        None, description="Score annotated with (aet) / (x-y pens) where applicable"
    )
    winner_team: Optional[str] = None
    result_method: Optional[str] = None


class WorldCupHeadToHeadResponse(BaseModel):
    """World Cup meetings between two teams over the full canonical corpus.

    ``scope_label`` is not decoration: the corpus is World Cup matches only, so
    a client showing a bare "no previous meetings" for two sides who have met
    often in friendlies would be stating something false. Render the label.
    """

    team_a: str
    team_b: str
    scope: str
    scope_label: str
    total_matches: int
    team_a_wins: int
    team_b_wins: int
    draws: int
    team_a_goals: int
    team_b_goals: int
    meetings: List[WorldCupMeeting]


class ModelEvaluationResponse(BaseModel):
    """What the shipped model is actually known to score, and on what.

    Split into a headline evaluation and the dataset it was measured on so the
    UI cannot render a bare "Model Accuracy" percentage — the previous card did
    exactly that with a stale legacy number.
    """

    model_version: str
    evaluation_name: str = Field(..., description="e.g. 'WC2026 Backtest'")
    evaluation_description: str
    accuracy: Optional[float] = None
    correct: Optional[int] = None
    total: Optional[int] = None
    is_out_of_sample: bool
    by_stage: List[BacktestStageAccuracy] = []
    legacy: Optional[Dict[str, Any]] = Field(
        None,
        description="Superseded legacy v1 training metrics, retained and labelled rather than shown as current",
    )

    model_config = {"protected_namespaces": ()}


class TeamMetaResponse(BaseModel):
    """Per-team WC2026 reference data, keyed by canonical team name."""

    teams: Dict[str, Any]
