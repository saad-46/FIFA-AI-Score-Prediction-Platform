from fastapi import APIRouter
from app.api.v1.endpoints import (
    predictions,
    teams,
    matches,
    analytics,
    tournament,
    feedback,
)

api_router = APIRouter()

api_router.include_router(predictions.router)
api_router.include_router(teams.router)
api_router.include_router(matches.router)
api_router.include_router(analytics.router)
api_router.include_router(tournament.router)
api_router.include_router(feedback.router)
