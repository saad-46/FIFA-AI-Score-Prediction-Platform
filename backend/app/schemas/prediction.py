"""
Prediction schemas — Pydantic v2
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FeatureImpact(BaseModel):
    feature: str
    impact: float

class PredictionExplanation(BaseModel):
    predicted_outcome: str
    confidence: float
    top_positive_features: List[FeatureImpact]
    top_negative_features: List[FeatureImpact]


# ─── Request ──────────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    home_team:     str           = Field(..., min_length=2, max_length=100)
    away_team:     str           = Field(..., min_length=2, max_length=100)
    tournament:    Optional[str] = Field(None, max_length=200)
    neutral_venue: bool          = Field(False)

    @field_validator("home_team", "away_team")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("away_team")
    @classmethod
    def teams_must_differ(cls, v: str, info) -> str:
        if info.data.get("home_team") and v.lower() == info.data["home_team"].lower():
            raise ValueError("Home and away teams must be different")
        return v


# ─── Scoreline ────────────────────────────────────────────────────────────────

class ScoреlineProb(BaseModel):
    """A single scoreline with its probability."""
    score:       str   = Field(..., examples=["2-1"])
    probability: float = Field(..., ge=0.0, le=1.0)


# ─── Insight ──────────────────────────────────────────────────────────────────

class PredictionInsight(BaseModel):
    type:        Literal["advantage", "warning", "neutral"]
    title:       str
    description: str
    impact:      Literal["high", "medium", "low"]


# ─── H2H ─────────────────────────────────────────────────────────────────────

class HeadToHeadStats(BaseModel):
    total_matches:   int
    home_team_wins:  int
    away_team_wins:  int
    draws:           int
    home_team_goals: int
    away_team_goals: int


# ─── Full prediction result ───────────────────────────────────────────────────

class PredictionResult(BaseModel):
    prediction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    home_team: str
    away_team: str

    # Regression outputs
    predicted_home_score: int
    predicted_away_score: int
    expected_home_goals: float = Field(..., ge=0.0)
    expected_away_goals: float = Field(..., ge=0.0)

    # Outcome probabilities
    home_win_probability: float = Field(..., ge=0.0, le=1.0)
    draw_probability: float = Field(..., ge=0.0, le=1.0)
    away_win_probability: float = Field(..., ge=0.0, le=1.0)

    # Score distribution
    most_likely_score: str = Field(default="")
    top_scorelines: List[ScoреlineProb] = Field(default_factory=list)

    # SHAP Explainability
    prediction_explanation: Optional[PredictionExplanation] = Field(
        default=None,
        description="SHAP-based feature attributions explaining the predicted outcome"
    )

    # Meta
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    model_version: str

    # Enrichment
    insights: List[PredictionInsight] = Field(default_factory=list)
    head_to_head: Optional[HeadToHeadStats] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

# ─── Saved prediction ─────────────────────────────────────────────────────────

class SavePredictionRequest(BaseModel):
    prediction_id: str


class SavedPredictionResponse(BaseModel):
    id:                   str
    user_id:              str
    prediction_id:        str
    home_team:            str
    away_team:            str
    predicted_home_score: int
    predicted_away_score: int
    home_win_probability: float
    draw_probability:     float
    away_win_probability: float
    expected_home_goals: float
    expected_away_goals: float
    confidence_score: float
    model_version: str
    prediction_explanation: Optional[PredictionExplanation] = None
    actual_home_score:    Optional[int]  = None
    actual_away_score:    Optional[int]  = None
    was_correct:          Optional[bool] = None
    created_at:           datetime

    model_config = {"from_attributes": True}


# ─── Accuracy stats ───────────────────────────────────────────────────────────

class AccuracyStats(BaseModel):
    total:    int
    correct:  int
    accuracy: float
