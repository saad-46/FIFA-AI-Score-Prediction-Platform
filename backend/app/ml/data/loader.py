"""
Data loader — caches the match DataFrame in memory for fast feature engineering.
Refreshes every 6 hours.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
from sqlalchemy import text
from app.db.database import engine
from app.ml.features.feature_engineering import compute_dynamic_elo

logger = logging.getLogger(__name__)

_cache: Optional[pd.DataFrame] = None
_cache_time: Optional[datetime] = None
CACHE_TTL_HOURS = 6


async def load_matches_dataframe(force_refresh: bool = False) -> pd.DataFrame:
    """
    Load all completed matches into a pandas DataFrame.
    Cached in memory with a 6-hour TTL.
    """
    global _cache, _cache_time

    now = datetime.now(timezone.utc)
    if (
        not force_refresh
        and _cache is not None
        and _cache_time is not None
        and (now - _cache_time) < timedelta(hours=CACHE_TTL_HOURS)
    ):
        return _cache

    logger.info("Loading match data from database...")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    m.date,
                    ht.name AS home_team,
                    at.name AS away_team,
                    m.home_score,
                    m.away_score,
                    m.tournament,
                    m.neutral_venue,
                    m.city,
                    m.country,
                    m.stage
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.id
                JOIN teams at ON m.away_team_id = at.id
                WHERE m.status = 'completed'
                ORDER BY m.date ASC
            """)
        )
        rows = result.fetchall()

    df = pd.DataFrame(
        rows,
        columns=[
            "date", "home_team", "away_team",
            "home_score", "away_score",
            "tournament", "neutral_venue",
            "city", "country", "stage",
        ],
    )
    df["date"] = pd.to_datetime(df["date"])
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")

    # ── Elo enrichment (bug fix) ──────────────────────────────────────────────
    # Training (train.py::build_training_dataset) calls compute_dynamic_elo(df)
    # before building features, so home_elo/away_elo/elo_difference columns
    # exist and carry real signal at train time. The live request path used to
    # skip this step entirely: build_feature_vector()'s Elo lookup reads those
    # columns off the DataFrame it's given and silently falls back to
    # BASE_ELO (1500.0) for both teams when the columns are absent, so
    # elo_difference was a constant 0.0 for every served prediction even
    # though the model was trained to weight real Elo gaps. Running the same
    # compute_dynamic_elo() here — once per 6h cache refresh, not per request —
    # closes that train/serve skew for both the predictor and the tournament
    # simulator (both consume this same cached, function-enriched DataFrame).
    df = compute_dynamic_elo(df)

    _cache = df
    _cache_time = now
    logger.info(f"Loaded {len(df)} matches into cache (Elo ratings computed)")
    return df


def get_cached_dataframe() -> Optional[pd.DataFrame]:
    return _cache

