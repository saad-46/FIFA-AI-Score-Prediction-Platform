"""
FIFA AI Score Prediction API
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.api.v1.router import api_router
from app.ml.models.predictor import get_predictor
from app.ml.data.loader import load_matches_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("Starting FIFA AI API...")

    # Load ML models — a missing/failed model is non-fatal: the predictor has a
    # documented fallback path, so we warn loudly but keep serving.
    predictor = get_predictor()
    if predictor.is_loaded:
        logger.info("ML models loaded successfully")
    else:
        logger.warning(
            "ML models not loaded (MODEL_PATH=%s) — using fallback predictions",
            settings.MODEL_PATH,
        )

    # Pre-warm data cache / verify DB connectivity. Unlike the model, the DB is a
    # hard dependency for almost every endpoint, so a misconfigured DATABASE_URL
    # (e.g. "Missing Database") must fail startup loudly instead of leaving the
    # app reporting healthy while every DB-backed route 500s later.
    try:
        df = await load_matches_dataframe()
        logger.info(f"Data cache warmed: {len(df)} matches")
    except Exception as e:
        logger.error(f"Database connectivity check failed at startup: {e}", exc_info=True)
        raise RuntimeError(
            "Failed to connect to the database during startup. "
            "Check DATABASE_URL and database availability."
        ) from e

    yield

    logger.info("Shutting down FIFA AI API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered FIFA match score prediction API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Exception Handlers ───────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        error_dict = {
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type"),
        }
        errors.append(error_dict)
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "details": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "Internal server error"},
    )

# ─── Routes ───────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for deployment monitoring."""
    predictor = get_predictor()
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "model_loaded": predictor.is_loaded,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
