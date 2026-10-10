"""
Chronological team-state engine: the single source of every pre-match feature.

``RatingEngine`` walks matches in date order. For each one it can do two things,
and it always does them in this order:

    snapshot(...)   read the two teams' state as it stood BEFORE the match
    advance(...)    update that state with the result

Training rows are the snapshots taken during the walk; a live prediction is a
snapshot taken after the walk. Same method, same state, same arithmetic --
there is no second feature implementation for inference to drift from, and a
result can never influence its own features because the snapshot for a match is
taken before ``advance`` sees its score.

State kept per team
-------------------
* Elo rating (World Football Elo form: importance-weighted K, goal-difference
  multiplier, home advantage; shoot-outs count as draws).
* Attack and defence ratings -- an online Poisson model. Expected goals are
  ``exp(mu + attack_a - defence_b + home)``; after each match every parameter
  takes one gradient step on the Poisson log-likelihood, ``goals - expected``.
  That is the incremental analogue of Dixon & Coles' time-weighted fit: recent
  matches dominate because old information is progressively overwritten.
* Exponentially weighted form (points, goal difference), match count, date of
  last match, a short Elo history for momentum, and pairwise head-to-head totals.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any, Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EloConfig:
    initial: float = 1500.0
    k_scale: float = 1.0          # multiplies the tier weight (60/50/40/30/20)
    home_advantage: float = 100.0  # Elo points added to the home side's rating
    use_margin: bool = True        # goal-difference multiplier
    provisional_matches: int = 30  # a team's first N matches...
    provisional_boost: float = 0.5  # ...move its rating (1 + boost) times faster
    # Online attack/defence model
    ad_lr: float = 0.05            # step size per match at tier weight 40 (tuned)
    ad_home: float = 0.25          # log-goals home advantage (initial; learned online)
    ad_mu: float = 0.20            # log mean goals per team at a neutral venue (initial)
    ad_shrink: float = 0.0005      # per-match pull of attack/defence toward 0
    form_halflife: float = 12.0    # matches (tuned)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def elo_expected(diff: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def margin_multiplier(goal_diff: int) -> float:
    g = abs(goal_diff)
    if g <= 1:
        return 1.0
    if g == 2:
        return 1.5
    return (11.0 + g) / 8.0


class RatingEngine:
    def __init__(self, cfg: EloConfig | None = None):
        self.cfg = cfg or EloConfig()
        c = self.cfg
        self.elo: dict[str, float] = defaultdict(lambda: c.initial)
        self.n: dict[str, int] = defaultdict(int)
        self.last_date: dict[str, pd.Timestamp] = {}
        self.attack: dict[str, float] = defaultdict(float)
        self.defence: dict[str, float] = defaultdict(float)
        self.form_pts: dict[str, float] = defaultdict(lambda: 1.35)   # long-run points/match
        self.form_gd: dict[str, float] = defaultdict(float)
        self.elo_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
        self.recent_dates: dict[str, deque] = defaultdict(lambda: deque(maxlen=40))
        # head-to-head, keyed by sorted pair; goal difference from the first name's view
        self.h2h_n: dict[tuple[str, str], int] = defaultdict(int)
        self.h2h_gd: dict[tuple[str, str], float] = defaultdict(float)
        self.mu = c.ad_mu
        self.home = c.ad_home
        self._decay = 0.5 ** (1.0 / c.form_halflife)
        self.matches_seen = 0
        self.last_match_date: pd.Timestamp | None = None

    # ── read ────────────────────────────────────────────────────────────────

    def expected_goals(self, a: str, b: str, venue: int) -> tuple[float, float]:
        """Online-Poisson expectation; venue is +1 (a home), 0, or -1 (b home)."""
        la = math.exp(self.mu + self.attack[a] - self.defence[b] + (self.home if venue == 1 else 0.0))
        lb = math.exp(self.mu + self.attack[b] - self.defence[a] + (self.home if venue == -1 else 0.0))
        return la, lb

    def snapshot(self, a: str, b: str, date: pd.Timestamp, venue: int, tier: int) -> dict[str, float]:
        """
        Pre-match features for ``a`` v ``b``. Pure read: calling it never changes
        state, and swapping (a, b, venue) -> (b, a, -venue) returns the mirror
        image exactly, which is what makes order-invariance testable.
        """
        c = self.cfg
        ea, eb = self.elo[a], self.elo[b]
        la, lb = self.expected_goals(a, b, venue)

        def rest(t: str) -> float:
            d = self.last_date.get(t)
            return 365.0 if d is None else float(min(max((date - d).days, 0), 365))

        def played_last_year(t: str) -> float:
            cutoff = date - pd.Timedelta(days=365)
            return float(sum(1 for d in self.recent_dates[t] if d >= cutoff))

        def momentum(t: str) -> float:
            h = self.elo_hist[t]
            return float(self.elo[t] - h[0]) if h else 0.0

        key = (a, b) if a <= b else (b, a)
        n_h2h = self.h2h_n[key]
        gd_h2h = self.h2h_gd[key] * (1.0 if key[0] == a else -1.0)

        return {
            "elo_a": ea, "elo_b": eb,
            "elo_diff": ea - eb,
            "elo_diff_venue": ea - eb + c.home_advantage * venue,
            "venue": float(venue),
            "attack_a": self.attack[a], "defence_a": self.defence[a],
            "attack_b": self.attack[b], "defence_b": self.defence[b],
            "xg_a": la, "xg_b": lb,
            "log_xg_ratio": math.log(la / lb),
            "log_xg_total": math.log(la + lb),
            "form_pts_diff": self.form_pts[a] - self.form_pts[b],
            "form_gd_diff": self.form_gd[a] - self.form_gd[b],
            "momentum_diff": momentum(a) - momentum(b),
            "log_matches_a": math.log1p(self.n[a]), "log_matches_b": math.log1p(self.n[b]),
            "rest_days_diff": rest(a) - rest(b),
            "activity_diff": played_last_year(a) - played_last_year(b),
            # Shrunk: one meeting says little, so divide by (n + 4).
            "h2h_gd_shrunk": gd_h2h / (n_h2h + 4.0),
            "tier": float(tier),
        }

    # ── write ───────────────────────────────────────────────────────────────

    def advance(self, a: str, b: str, goals_a: int, goals_b: int,
                date: pd.Timestamp, venue: int, importance: float) -> None:
        c = self.cfg
        # ---- Elo
        ea, eb = self.elo[a], self.elo[b]
        we = elo_expected(ea - eb + c.home_advantage * venue)
        w = 1.0 if goals_a > goals_b else (0.5 if goals_a == goals_b else 0.0)
        k = importance * c.k_scale
        if c.use_margin:
            k *= margin_multiplier(goals_a - goals_b)
        ka = k * (1.0 + c.provisional_boost if self.n[a] < c.provisional_matches else 1.0)
        kb = k * (1.0 + c.provisional_boost if self.n[b] < c.provisional_matches else 1.0)
        self.elo_hist[a].append(ea)
        self.elo_hist[b].append(eb)
        self.elo[a] = ea + ka * (w - we)
        self.elo[b] = eb + kb * ((1.0 - w) - (1.0 - we))

        # ---- online Poisson attack/defence
        la, lb = self.expected_goals(a, b, venue)
        lr = c.ad_lr * (importance / 40.0)
        # Cap the residual: a 31-0 must not rewrite a rating in one step.
        ra = max(min(goals_a - la, 4.0), -4.0)
        rb = max(min(goals_b - lb, 4.0), -4.0)
        s = 1.0 - c.ad_shrink
        self.attack[a] = self.attack[a] * s + lr * ra
        self.defence[b] = self.defence[b] * s - lr * ra
        self.attack[b] = self.attack[b] * s + lr * rb
        self.defence[a] = self.defence[a] * s - lr * rb
        g_lr = lr * 0.02
        self.mu += g_lr * (ra + rb)
        if venue == 1:
            self.home += g_lr * ra
        elif venue == -1:
            self.home += g_lr * rb

        # ---- form
        d = self._decay
        pa = 3.0 if goals_a > goals_b else (1.0 if goals_a == goals_b else 0.0)
        pb = 3.0 if goals_b > goals_a else (1.0 if goals_a == goals_b else 0.0)
        self.form_pts[a] = d * self.form_pts[a] + (1 - d) * pa
        self.form_pts[b] = d * self.form_pts[b] + (1 - d) * pb
        gd = float(max(min(goals_a - goals_b, 5), -5))
        self.form_gd[a] = d * self.form_gd[a] + (1 - d) * gd
        self.form_gd[b] = d * self.form_gd[b] - (1 - d) * gd

        key = (a, b) if a <= b else (b, a)
        self.h2h_n[key] += 1
        self.h2h_gd[key] += gd if key[0] == a else -gd

        for t in (a, b):
            self.n[t] += 1
            self.last_date[t] = date
            self.recent_dates[t].append(date)
        self.matches_seen += 1
        self.last_match_date = date


def walk(matches: pd.DataFrame, cfg: EloConfig | None = None,
         collect: bool = True) -> tuple[RatingEngine, pd.DataFrame | None]:
    """
    Run the engine over ``matches`` (must be date-sorted). With ``collect`` it
    returns one pre-match feature row per match, aligned to ``matches.index``.
    """
    if not matches["date"].is_monotonic_increasing:
        raise ValueError("matches must be sorted by date before the rating walk")
    eng = RatingEngine(cfg)
    rows: list[dict[str, float]] = []
    for a, b, ga, gb, date, venue, tier, imp in zip(
        matches.team_a.values, matches.team_b.values, matches.goals_a.values, matches.goals_b.values,
        matches.date, matches.venue.values, matches.tier.values, matches.importance.values,
    ):
        if collect:
            rows.append(eng.snapshot(a, b, date, int(venue), int(tier)))
        eng.advance(a, b, int(ga), int(gb), date, int(venue), float(imp))
    feats = pd.DataFrame(rows, index=matches.index) if collect else None
    return eng, feats
