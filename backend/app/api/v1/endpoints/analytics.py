from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import async_ttl_cache
from app.core.config import get_settings
from app.core.security import get_optional_user
from app.db.database import get_db
from app.ml.data.loader import load_matches_dataframe
from app.models.match import Match, SavedPrediction, Team
from app.schemas.analytics import (
    DashboardStatsResponse,
    GlobalAnalyticsResponse,
    ModelMetricsResponse,
    TopTeamSummary,
)
from app.schemas.wc2026 import ModelEvaluationResponse
from app.services.match_service import count_all_matches, get_upcoming_matches
from app.services.prediction_service import get_recent_predictions
from app.services.team_service import get_top_teams
from app.data import wc2026 as wc2026_data

router = APIRouter(prefix="/analytics", tags=["analytics"])
settings = get_settings()


class FeatureImportanceItem(BaseModel):
    feature:    str
    importance: float


class FeatureImportanceResponse(BaseModel):
    features:      List[FeatureImportanceItem]
    model_version: str
    total_features: int


@async_ttl_cache(ttl_seconds=60, max_size=1, ignore_args={0})
async def _global_dashboard_block(db: AsyncSession):
    """
    The part of the dashboard that is identical for every caller.

    Split out and cached because /analytics/dashboard is the product's landing
    page and was its slowest endpoint: ~1.5s median, and for an anonymous
    visitor every one of those round trips was spent re-deriving numbers that
    do not depend on who is asking. Two table counts and a fixtures lookup, all
    at ~150ms of Tokyo round trip each and single-digit milliseconds of actual
    query time.

    Only caller-independent data belongs here. Saved-prediction counts, accuracy
    and recent predictions stay uncached in the endpoint below, keyed to the
    signed-in user, so a freshly saved prediction is never served stale.
    """
    total_matches = await count_all_matches(db)
    total_teams = (await db.execute(select(func.count()).select_from(Team))).scalar() or 0
    top_teams_stats = await get_top_teams(db, limit=5)
    upcoming = await get_upcoming_matches(db, limit=5)
    return total_matches, total_teams, top_teams_stats, upcoming


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: Optional[dict] = Depends(get_optional_user),
):
    """Dashboard summary statistics."""
    total_matches, total_teams, top_teams_stats, upcoming_matches = (
        await _global_dashboard_block(db)
    )

    # User-specific stats
    total_predictions = 0
    accuracy_rate = 0.0
    recent_predictions = []

    if user:
        user_id = user.get("sub")
        pred_count_result = await db.execute(
            select(func.count()).where(SavedPrediction.user_id == user_id)
        )
        total_predictions = pred_count_result.scalar() or 0

        correct_result = await db.execute(
            select(func.count()).where(
                SavedPrediction.user_id == user_id,
                SavedPrediction.was_correct == True,
            )
        )
        correct = correct_result.scalar() or 0

        verified_result = await db.execute(
            select(func.count()).where(
                SavedPrediction.user_id == user_id,
                SavedPrediction.was_correct.is_not(None),
            )
        )
        verified = verified_result.scalar() or 0
        accuracy_rate = correct / verified if verified > 0 else 0.0

        recent_predictions = await get_recent_predictions(db, user_id, limit=5)

    # Top teams by win rate (min 10 matches played), capped to keep the payload
    # small. Both this and upcoming_matches come from the cached global block.
    top_teams = [
        TopTeamSummary(
            team_id=t.team_id,
            team_name=t.team_name,
            win_rate=t.win_rate,
            matches_played=t.matches_played,
        )
        for t in top_teams_stats
    ]

    return DashboardStatsResponse(
        total_predictions=total_predictions,
        accuracy_rate=accuracy_rate,
        total_matches_analyzed=total_matches,
        total_teams=total_teams,
        recent_predictions=recent_predictions,
        top_teams=top_teams,
        upcoming_matches=upcoming_matches,
    )


@async_ttl_cache(ttl_seconds=60, max_size=4)
async def _compute_global_analytics() -> GlobalAnalyticsResponse:
    """
    Global analytics overview (cached in-process for 60s).

    This recomputes several full-history groupby aggregations on every call
    but doesn't depend on the caller/session at all — it only reads the
    (already 6h-TTL-cached) matches DataFrame. A short TTL cache here avoids
    redoing that aggregation on every request from a busy dashboard without
    risking meaningful staleness. No Redis in this stack, hence the
    in-process cache instead of an external one.
    """
    df = await load_matches_dataframe()
    valid = df.dropna(subset=["home_score", "away_score"])

    total_goals = int(valid["home_score"].sum() + valid["away_score"].sum())
    n = len(valid)
    home_wins = int((valid["home_score"] > valid["away_score"]).sum())
    draws = int((valid["home_score"] == valid["away_score"]).sum())
    away_wins = int((valid["home_score"] < valid["away_score"]).sum())

    # Goals by year
    valid_copy = valid.copy()
    valid_copy["year"] = valid_copy["date"].dt.year
    goals_by_year = (
        valid_copy.groupby("year")
        .agg(goals=("home_score", lambda x: int(x.sum() + valid_copy.loc[x.index, "away_score"].sum())),
             matches=("home_score", "count"))
        .reset_index()
        .rename(columns={"year": "year"})
        .to_dict("records")
    )

    # Top tournaments
    top_tournaments = (
        valid_copy.groupby("tournament")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
        .rename(columns={0: "matches"})
        .to_dict("records")
    )

    return GlobalAnalyticsResponse(
        total_matches=n,
        total_goals=total_goals,
        avg_goals_per_match=round(total_goals / n, 3) if n > 0 else 0,
        home_win_rate=round(home_wins / n, 4) if n > 0 else 0,
        draw_rate=round(draws / n, 4) if n > 0 else 0,
        away_win_rate=round(away_wins / n, 4) if n > 0 else 0,
        goals_by_year=goals_by_year,
        top_tournaments=top_tournaments,
    )


@router.get("/global", response_model=GlobalAnalyticsResponse)
async def global_analytics(db: AsyncSession = Depends(get_db)):
    """Global analytics overview."""
    return await _compute_global_analytics()


@router.get("/model-metrics", response_model=ModelMetricsResponse)
async def model_metrics():
    """ML model performance metrics. Reads from metrics.json generated by training pipeline."""
    model_dir = Path(settings.MODEL_PATH).parent
    metrics_path = model_dir / "metrics.json"
    report_path = model_dir / "training_report.json"

    accuracy = 0.0
    mae = 0.0
    rmse = 0.0
    last_trained = "unknown"
    training_samples = 0

    if metrics_path.exists():
        with open(metrics_path) as f:
            data = json.load(f)
        accuracy = data.get("classifier_adjusted_accuracy", data.get("classifier_raw_accuracy", 0.0))
        mae = data.get("home_mae", 0.0)
        rmse = data.get("home_rmse", 0.0)

    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        last_trained = report.get("trained_at", "unknown")
        training_samples = report.get("n_training_samples", 0)

    return ModelMetricsResponse(
        accuracy=accuracy,
        mae=mae,
        rmse=rmse,
        last_trained=last_trained,
        training_samples=training_samples,
        model_version=settings.MODEL_VERSION,
    )


@router.get("/model-evaluation", response_model=ModelEvaluationResponse)
async def model_evaluation():
    """
    What the shipped V2 model actually scored, and on which evaluation.

    Replaces `/model-metrics` as the number a UI should headline. That endpoint
    reads `app/ml/models/metrics.json` — the **legacy v1.0.0** model trained
    2026-07-03 on 376 samples, whose `classifier_adjusted_accuracy` of 0.289 is
    a draw-boosted holdout figure (raw accuracy was 0.474; a 1.05 draw boost
    pushed draw recall to 1.0 and destroyed accuracy). Rendering that as
    "Model Accuracy" materially misstates the product.

    The honest headline is the frozen v2.1.0 WC2026 backtest: an out-of-sample
    evaluation of a model frozen before any 2026 result was compared against
    it. The legacy numbers are still returned, under `legacy`, so the UI can
    label them as superseded rather than silently dropping them.
    """
    backtest = wc2026_data.build_backtest()

    legacy: Optional[dict] = None
    model_dir = Path(settings.MODEL_PATH).parent
    metrics_path = model_dir / "metrics.json"
    report_path = model_dir / "training_report.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            data = json.load(f)
        legacy = {
            "model_version": "1.0.0",
            "label": "Legacy v1 model (superseded)",
            "classifier_raw_accuracy": data.get("classifier_raw_accuracy"),
            "classifier_adjusted_accuracy": data.get("classifier_adjusted_accuracy"),
            "home_mae": data.get("home_mae"),
            "note": (
                "Holdout metrics from the pre-V2 model. The adjusted accuracy is "
                "depressed by a draw-boost that forced draw recall to 1.0. Retained "
                "for provenance; not representative of the current model."
            ),
        }
        if report_path.exists():
            with open(report_path) as f:
                report = json.load(f)
            legacy["training_samples"] = report.get("n_training_samples")
            legacy["trained_at"] = report.get("trained_at")

    return ModelEvaluationResponse(
        model_version=backtest.get("model_version") or "v2.1.0-historical-optimized",
        evaluation_name="WC2026 Backtest",
        evaluation_description=(
            "Out-of-sample evaluation on all 104 WC2026 matches. The model was frozen "
            "before any 2026 result was compared against it."
        ),
        accuracy=backtest.get("accuracy"),
        correct=backtest.get("correct"),
        total=backtest.get("n_matches_scored"),
        is_out_of_sample=True,
        by_stage=backtest.get("by_stage", []),
        legacy=legacy,
    )


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
async def feature_importance():
    """
    Return sorted feature importance from the last training run.
    Reads feature_importance.json saved by the training pipeline.
    """
    fi_path = Path(settings.FEATURE_IMPORTANCE_PATH)
    if not fi_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Feature importance file not found. "
                "Run the training pipeline first: python -m app.ml.train"
            ),
        )

    with open(fi_path) as fh:
        data = json.load(fh)

    features = [
        FeatureImportanceItem(feature=item["feature"], importance=item["importance"])
        for item in data
    ]

    return FeatureImportanceResponse(
        features=features,
        model_version=settings.MODEL_VERSION,
        total_features=len(features),
    )
