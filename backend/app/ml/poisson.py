"""
Poisson Probability Engine
==========================

Converts expected goals (xG) into a full score probability matrix and
derives match outcome probabilities + top scorelines.

Usage
-----
    from app.ml.poisson import PoissonEngine

    engine = PoissonEngine()
    result = engine.predict(home_xg=1.82, away_xg=1.11)
    # result.home_win_probability  → 0.54
    # result.most_likely_score     → "2-1"
    # result.top_scorelines        → [{"score": "2-1", "probability": 0.16}, ...]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
from scipy.stats import poisson


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Scoreline:
    score: str          # e.g. "2-1"
    probability: float  # e.g. 0.1623


@dataclass
class PoissonResult:
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    most_likely_score: str
    top_scorelines: List[Scoreline] = field(default_factory=list)
    score_matrix: np.ndarray = field(default_factory=lambda: np.array([]))

    # Convenience
    @property
    def home_xg(self) -> float:
        return self._home_xg

    @property
    def away_xg(self) -> float:
        return self._away_xg


# ─── Engine ───────────────────────────────────────────────────────────────────

class PoissonEngine:
    """
    Poisson-based score probability engine.

    The score probability for (i, j) is:
        P(home=i) * P(away=j)  where P(k) = Poisson(k; lambda)

    Win/draw/loss probabilities are derived by summing the appropriate
    triangles of the score matrix.
    """

    def __init__(self, max_goals: int = 8, top_n: int = 10) -> None:
        """
        Parameters
        ----------
        max_goals : Maximum goals per team to consider (0..max_goals inclusive).
                    8 covers >99.9% of international match outcomes.
        top_n     : Number of top scorelines to return.
        """
        self.max_goals = max_goals
        self.top_n = top_n

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(
        self,
        home_xg: float,
        away_xg: float,
    ) -> PoissonResult:
        """
        Generate full match probability output from expected goals.

        Parameters
        ----------
        home_xg : Expected goals for the home team (λ_home).
        away_xg : Expected goals for the away team (λ_away).

        Returns
        -------
        PoissonResult with probabilities, most likely score, and top scorelines.
        """
        # Clamp to sensible range
        home_xg = float(np.clip(home_xg, 0.05, 9.0))
        away_xg = float(np.clip(away_xg, 0.05, 9.0))

        matrix = self._score_matrix(home_xg, away_xg)

        home_win, draw, away_win = self._outcome_probs(matrix)
        most_likely = self._most_likely_score(matrix)
        top = self._top_scorelines(matrix)

        result = PoissonResult(
            home_win_probability=round(home_win, 4),
            draw_probability=round(draw, 4),
            away_win_probability=round(away_win, 4),
            most_likely_score=most_likely,
            top_scorelines=top,
            score_matrix=matrix,
        )
        # Attach xG for reference
        result._home_xg = home_xg  # type: ignore[attr-defined]
        result._away_xg = away_xg  # type: ignore[attr-defined]
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _score_matrix(self, home_xg: float, away_xg: float) -> np.ndarray:
        """
        Build (max_goals+1) × (max_goals+1) probability matrix.
        matrix[i, j] = P(home scores i) * P(away scores j).
        """
        goals = np.arange(self.max_goals + 1)
        home_pmf = poisson.pmf(goals, home_xg)   # shape (max_goals+1,)
        away_pmf = poisson.pmf(goals, away_xg)   # shape (max_goals+1,)
        return np.outer(home_pmf, away_pmf)       # shape (max_goals+1, max_goals+1)

    def _outcome_probs(
        self, matrix: np.ndarray
    ) -> tuple[float, float, float]:
        """
        Derive home win / draw / away win probabilities from the score matrix.

        home_win : sum of lower triangle  (home > away)
        draw     : trace                  (home == away)
        away_win : sum of upper triangle  (away > home)
        """
        home_win = float(np.tril(matrix, k=-1).sum())
        draw     = float(np.trace(matrix))
        away_win = float(np.triu(matrix, k=1).sum())

        # Normalise to handle floating-point truncation
        total = home_win + draw + away_win
        if total <= 0:
            return 1 / 3, 1 / 3, 1 / 3
        return home_win / total, draw / total, away_win / total

    def _most_likely_score(self, matrix: np.ndarray) -> str:
        """Return the scoreline with the highest probability."""
        idx = np.unravel_index(matrix.argmax(), matrix.shape)
        return f"{idx[0]}-{idx[1]}"

    def _top_scorelines(self, matrix: np.ndarray) -> list[Scoreline]:
        """Return the top-N most probable scorelines, sorted descending."""
        flat = matrix.flatten()
        top_indices = np.argsort(flat)[::-1][: self.top_n]
        results: list[Scoreline] = []
        for flat_idx in top_indices:
            h, a = divmod(int(flat_idx), self.max_goals + 1)
            results.append(
                Scoreline(
                    score=f"{h}-{a}",
                    probability=round(float(flat[flat_idx]), 4),
                )
            )
        return results


# ─── Module-level singleton ───────────────────────────────────────────────────

_engine: PoissonEngine | None = None


def get_poisson_engine() -> PoissonEngine:
    """Return the shared PoissonEngine instance (lazy init)."""
    global _engine
    if _engine is None:
        _engine = PoissonEngine()
    return _engine
