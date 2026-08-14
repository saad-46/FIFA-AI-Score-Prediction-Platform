import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.core.rate_limit import check_rate_limit, prediction_rule
from app.core.security import get_current_user, get_optional_user
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResult,
    SavedPredictionResponse,
    AccuracyStats,
)
from app.services.prediction_service import run_prediction, get_cached_prediction
from app.models.match import SavedPrediction
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/predict", response_model=PredictionResult, status_code=status.HTTP_200_OK)
async def predict_match(
    payload: PredictionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Run AI prediction for a match.
    Public endpoint — authentication optional, but rate limited (see
    app/core/rate_limit.py): authenticated callers are limited per account,
    anonymous callers per client IP.
    """
    # Raises 429 with Retry-After when over the limit. Deliberately before the
    # try/except below so a 429 propagates as a 429 rather than being caught
    # and re-raised as a generic 500.
    await check_rate_limit(db, prediction_rule(), request, user)

    try:
        result = await run_prediction(
            home_team=payload.home_team,
            away_team=payload.away_team,
            tournament=payload.tournament,
            neutral_venue=payload.neutral_venue,
        )
        return result
    except Exception as e:
        logger.error(f"Prediction failed for {payload.home_team} vs {payload.away_team}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed. Please try again later.",
        )


@router.post(
    "/{prediction_id}/save",
    response_model=SavedPredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_prediction(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Save a prediction to the user's account."""
    cached = get_cached_prediction(prediction_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found or expired. Re-run the prediction.",
        )

    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    saved = SavedPrediction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        prediction_id=prediction_id,
        home_team=cached.home_team,
        away_team=cached.away_team,
        predicted_home_score=cached.predicted_home_score,
        predicted_away_score=cached.predicted_away_score,
        home_win_probability=cached.home_win_probability,
        draw_probability=cached.draw_probability,
        away_win_probability=cached.away_win_probability,
        expected_home_goals=cached.expected_home_goals,
        expected_away_goals=cached.expected_away_goals,
        confidence_score=cached.confidence_score,
        model_version=cached.model_version,
    )
    try:
        db.add(saved)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Failed to save prediction {prediction_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save prediction.",
        )

    return SavedPredictionResponse.model_validate(saved)


@router.get("/saved", response_model=list[SavedPredictionResponse])
async def get_saved_predictions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get all saved predictions for the authenticated user."""
    user_id = user.get("sub")
    offset = (page - 1) * page_size

    stmt = (
        select(SavedPrediction)
        .where(SavedPrediction.user_id == user_id)
        .order_by(SavedPrediction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    predictions = result.scalars().all()
    return [SavedPredictionResponse.model_validate(p) for p in predictions]


@router.delete("/saved/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_prediction(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a saved prediction."""
    # SavedPrediction.id is a native Postgres uuid column; a malformed
    # (non-UUID) prediction_id would otherwise reach asyncpg directly and
    # raise a raw DataError, surfacing as an unhandled 500 (the same bug
    # class already guarded against in team_service.py/match_service.py).
    try:
        uuid.UUID(str(prediction_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    user_id = user.get("sub")
    stmt = select(SavedPrediction).where(
        SavedPrediction.id == prediction_id,
        SavedPrediction.user_id == user_id,
    )
    result = await db.execute(stmt)
    pred = result.scalar_one_or_none()

    if not pred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

    await db.delete(pred)


@router.get("/accuracy", response_model=AccuracyStats)
async def get_accuracy_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get prediction accuracy stats for the authenticated user."""
    user_id = user.get("sub")

    total_stmt = select(func.count()).where(
        SavedPrediction.user_id == user_id,
        SavedPrediction.was_correct.is_not(None),
    )
    correct_stmt = select(func.count()).where(
        SavedPrediction.user_id == user_id,
        SavedPrediction.was_correct == True,
    )

    total_result = await db.execute(total_stmt)
    correct_result = await db.execute(correct_stmt)

    total = total_result.scalar() or 0
    correct = correct_result.scalar() or 0

    return AccuracyStats(
        total=total,
        correct=correct,
        accuracy=correct / total if total > 0 else 0.0,
    )
