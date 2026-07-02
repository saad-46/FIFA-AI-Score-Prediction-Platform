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
                    m.country
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
            "city", "country",
        ],
    )
    df["date"] = pd.to_datetime(df["date"])
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")

    _cache = df
    _cache_time = now
    logger.info(f"Loaded {len(df)} matches into cache")
    return df


def get_cached_dataframe() -> Optional[pd.DataFrame]:
    return _cache

