"""
Prediction Service
==================

Orchestrates:
  1. Load match data (cached)
  2. Run ML prediction (xG + result classifier + Poisson)
  3. Compute head-to-head stats
  4. Generate AI insights
  5. Return structured PredictionResult
"""

from __future__ import annotations

import logging
import uuid
import time
from collections import OrderedDict
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ml.data.loader import load_matches_dataframe
from app.ml.models.predictor import get_predictor
from app.models.match import SavedPrediction
from app.schemas.analytics import RecentPredictionSummary
from app.schemas.prediction import (
    HeadToHeadStats,
    PredictionInsight,
    PredictionResult,
    ScoреlineProb,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── TTL-based LRU Prediction Cache ──────────────────────────────────────────
_CACHE_MAX_SIZE = 500
_CACHE_TTL_SECONDS = 3600  # 1 hour

class _PredictionCache:
    """Thread-safe LRU cache with TTL eviction for prediction results."""

    def __init__(self, max_size: int = _CACHE_MAX_SIZE, ttl: int = _CACHE_TTL_SECONDS):
        self._store: OrderedDict[str, tuple[float, PredictionResult]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> Optional[PredictionResult]:
        if key not in self._store:
            return None
        ts, result = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return result

    def put(self, key: str, result: PredictionResult) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.time(), result)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

_prediction_cache = _PredictionCache()


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

async def run_prediction(
    home_team:     str,
    away_team:     str,
    tournament:    Optional[str] = None,
    neutral_venue: bool = False,
) -> PredictionResult:
    """
    Full prediction pipeline.

    Returns a PredictionResult with:
      - expected goals
      - W/D/L probabilities (blended Poisson + classifier)
      - most likely score + top scorelines
      - AI insights
      - head-to-head stats
    """
    df        = await load_matches_dataframe()
    predictor = get_predictor()

    # ── ML prediction ─────────────────────────────────────────────────────────
    pred = predictor.predict(
        df=df,
        home_team=home_team,
        away_team=away_team,
        tournament=tournament,
        neutral_venue=neutral_venue,
    )

    # ── Head-to-head ──────────────────────────────────────────────────────────
    h2h = _compute_h2h(df, home_team, away_team)

    # ── Insights ──────────────────────────────────────────────────────────────
    insights = _generate_insights(df, home_team, away_team, pred, h2h, neutral_venue)

    # ── Parse top scorelines from predictor output ────────────────────────────
    top_scorelines = [
        ScoреlineProb(score=s["score"], probability=s["probability"])
        for s in pred.get("top_scorelines", [])
    ]

    # ── Derive most likely score as integers ──────────────────────────────────
    most_likely = pred.get("most_likely_score", "1-1")
    try:
        h_score, a_score = (int(x) for x in most_likely.split("-"))
    except (ValueError, AttributeError):
        h_score, a_score = 1, 1

    result = PredictionResult(
        prediction_id=str(uuid.uuid4()),
        home_team=home_team,
        away_team=away_team,
        predicted_home_score=h_score,
        predicted_away_score=a_score,
        expected_home_goals=pred["expected_home_goals"],
        expected_away_goals=pred["expected_away_goals"],
        home_win_probability=pred["home_win_probability"],
        draw_probability=pred["draw_probability"],
        away_win_probability=pred["away_win_probability"],
        most_likely_score=most_likely,
        top_scorelines=top_scorelines,
        confidence_score=pred["confidence_score"],
        model_version=pred.get("model_version", settings.MODEL_VERSION),
        insights=insights,
        head_to_head=h2h,
    )

    _prediction_cache.put(result.prediction_id, result)
    return result


def get_cached_prediction(prediction_id: str) -> Optional[PredictionResult]:
    return _prediction_cache.get(prediction_id)


async def get_recent_predictions(
    db: AsyncSession,
    user_id: str,
    limit: int = 5,
) -> list[RecentPredictionSummary]:
    """Most recent saved predictions for a user, for the dashboard feed."""
    stmt = (
        select(SavedPrediction)
        .where(SavedPrediction.user_id == user_id)
        .order_by(SavedPrediction.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    predictions = result.scalars().all()
    return [RecentPredictionSummary.model_validate(p) for p in predictions]


# ═══════════════════════════════════════════════════════════════════════════════
# Head-to-head
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_h2h(
    df: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> HeadToHeadStats:
    mask = (
        ((df["home_team"] == home_team) & (df["away_team"] == away_team))
        | ((df["home_team"] == away_team) & (df["away_team"] == home_team))
    )
    h2h_df = df[mask].dropna(subset=["home_score", "away_score"])

    if len(h2h_df) == 0:
        return HeadToHeadStats(
            total_matches=0,
            home_team_wins=0,
            away_team_wins=0,
            draws=0,
            home_team_goals=0,
            away_team_goals=0,
        )

    home_wins = away_wins = draws = 0
    home_goals = away_goals = 0

    for _, row in h2h_df.iterrows():
        if row["home_team"] == home_team:
            hg, ag = int(row["home_score"]), int(row["away_score"])
        else:
            hg, ag = int(row["away_score"]), int(row["home_score"])

        home_goals += hg
        away_goals += ag

        if hg > ag:
            home_wins += 1
        elif hg == ag:
            draws += 1
        else:
            away_wins += 1

    return HeadToHeadStats(
        total_matches=len(h2h_df),
        home_team_wins=home_wins,
        away_team_wins=away_wins,
        draws=draws,
        home_team_goals=home_goals,
        away_team_goals=away_goals,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AI Insights
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_insights(
    df: pd.DataFrame,
    home_team: str,
    away_team: str,
    pred: dict,
    h2h: HeadToHeadStats,
    neutral_venue: bool = False,
) -> list[PredictionInsight]:
    """Generate up to 5 natural-language insights from prediction data."""
    insights: list[PredictionInsight] = []

    # ── Home advantage ────────────────────────────────────────────────────────
    # Use the caller's actual request flag, not pred["neutral_venue"] — the
    # predictor's output dict never includes that key (see predictor.py
    # PredictionOutput.to_dict()), so reading it back out always defaulted to
    # False and this insight never suppressed itself for neutral-venue matches.
    if not neutral_venue:
        home_home = df[df["home_team"] == home_team].dropna(
            subset=["home_score", "away_score"]
        )
        if len(home_home) >= 5:
            home_win_rate = (
                home_home["home_score"] > home_home["away_score"]
            ).mean()
            if home_win_rate > 0.55:
                insights.append(
                    PredictionInsight(
                        type="advantage",
                        title=f"{home_team} strong at home",
                        description=(
                            f"{home_team} wins {home_win_rate:.0%} of home "
                            "matches historically."
                        ),
                        impact="high",
                    )
                )

    # ── Recent form ───────────────────────────────────────────────────────────
    home_recent = df[
        (df["home_team"] == home_team) | (df["away_team"] == home_team)
    ].tail(5).dropna(subset=["home_score", "away_score"])

    away_recent = df[
        (df["home_team"] == away_team) | (df["away_team"] == away_team)
    ].tail(5).dropna(subset=["home_score", "away_score"])

    if len(home_recent) >= 3 and len(away_recent) >= 3:
        home_form = _form_score(home_recent, home_team)
        away_form = _form_score(away_recent, away_team)

        if home_form > away_form + 0.20:
            insights.append(
                PredictionInsight(
                    type="advantage",
                    title=f"{home_team} in better form",
                    description=(
                        f"{home_team} has stronger recent results "
                        f"than {away_team}."
                    ),
                    impact="medium",
                )
            )
        elif away_form > home_form + 0.20:
            insights.append(
                PredictionInsight(
                    type="warning",
                    title=f"{away_team} in better form",
                    description=f"{away_team} has been performing better recently.",
                    impact="medium",
                )
            )

    # ── H2H dominance ─────────────────────────────────────────────────────────
    if h2h.total_matches >= 5:
        if h2h.home_team_wins > h2h.away_team_wins * 2:
            insights.append(
                PredictionInsight(
                    type="advantage",
                    title=f"{home_team} dominates head-to-head",
                    description=(
                        f"{home_team} has won {h2h.home_team_wins} of "
                        f"{h2h.total_matches} meetings."
                    ),
                    impact="medium",
                )
            )
        elif h2h.away_team_wins > h2h.home_team_wins * 2:
            insights.append(
                PredictionInsight(
                    type="warning",
                    title=f"{away_team} leads head-to-head",
                    description=(
                        f"{away_team} has won {h2h.away_team_wins} of "
                        f"{h2h.total_matches} meetings."
                    ),
                    impact="medium",
                )
            )

    # ── High-scoring indicator ────────────────────────────────────────────────
    total_xg = pred["expected_home_goals"] + pred["expected_away_goals"]
    if total_xg > 3.0:
        insights.append(
            PredictionInsight(
                type="neutral",
                title="High-scoring match expected",
                description=(
                    f"Combined xG of {total_xg:.1f} suggests an open, "
                    "attacking game."
                ),
                impact="low",
            )
        )

    # ── Low confidence warning ────────────────────────────────────────────────
    if pred["confidence_score"] < 0.50:
        insights.append(
            PredictionInsight(
                type="warning",
                title="Limited historical data",
                description=(
                    "Fewer historical matches available for these teams "
                    "reduces prediction confidence."
                ),
                impact="high",
            )
        )

    return insights[:5]


def _form_score(matches: pd.DataFrame, team: str) -> float:
    """Simple form score: W=1, D=0.5, L=0."""
    score = 0.0
    n = 0
    for _, row in matches.iterrows():
        if row["home_team"] == team:
            gs, gc = row["home_score"], row["away_score"]
        else:
            gs, gc = row["away_score"], row["home_score"]
        if gs > gc:
            score += 1.0
        elif gs == gc:
            score += 0.5
        n += 1
    return score / n if n > 0 else 0.5
