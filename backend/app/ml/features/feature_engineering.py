"""
Advanced Feature Engineering Pipeline — FIFA Match Prediction
=============================================================

Features:
  - Weighted rolling form (5 / 10 / 20 match windows)
  - Dynamic Elo ratings (tournament-weighted K-factor)
  - Attack / defense strength (Dixon-Coles style)
  - Momentum scoring
  - Goal volatility
  - Rest days / fatigue proxy
  - Home-away specialisation
  - Head-to-head record
  - Exponential time-decay weighting
  - Derived differential features
  - FIFA ranking (pre-tournament) + rank differential (complementary to Elo)
  - Same-confederation flag
  - Knockout-stage experience count

Performance notes:
  - Elo ratings are pre-computed once per DataFrame (compute_dynamic_elo)
  - Team match indices are pre-built (build_team_index) to avoid repeated scans
  - Rolling stats iterate only over the tail window, not the full history
  - FIFA rankings are read once from teams_reference.csv (lru_cache) and
    looked up in O(1) per call, not recomputed per request

See RANKINGS_INTEGRATION.md (repo root) for the full design rationale behind
the ranking features, and FEATURE_ENGINEERING.md for the full feature list
with justification for every addition/exclusion.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

ROLLING_WINDOWS: list[int] = [5, 10, 20]
BASE_ELO: float = 1500.0
K_FACTOR: float = 20.0
GLOBAL_AVG_GOALS: float = 1.35          # historical international average
DECAY_HALF_LIFE_DAYS: float = 365 * 3   # 3-year half-life for time decay

TOURNAMENT_WEIGHTS: dict[str, float] = {
    "FIFA World Cup": 1.00,
    "UEFA Euro": 0.90,
    "Copa América": 0.90,
    "AFC Asian Cup": 0.85,
    "Africa Cup of Nations": 0.85,
    "World Cup qualification": 0.80,
    "UEFA Nations League": 0.75,
    "CONCACAF Gold Cup": 0.70,
    "Friendly": 0.35,
}

# Stage strings from matches_historical.csv / matches.stage that count as
# "knockout" experience (everything past the group stage).
KNOCKOUT_STAGES: frozenset[str] = frozenset({
    "round_of_32", "round_of_16", "quarter_final", "semi_final",
    "third_place", "final",
    # Human-readable variants (older seed data / CSV casing) so the feature
    # doesn't silently under-count if a different vocabulary is used upstream.
    "Round of 32", "Round of 16", "Round Of 16", "Quarter-finals", "Quarter Final",
    "Semi-finals", "Semi Final", "Third-place Match", "Third Place", "Final",
})

# ─── FIFA rankings reference (teams_reference.csv) ────────────────────────────
#
# Location resolved relative to this file, not the process CWD or app
# settings, so it works regardless of where the app is started from (same
# convention as app/data/fifa_2026/__init__.py). Only covers the 48 teams in
# the 2026 field -- see RANKINGS_INTEGRATION.md for how non-2026 historical
# opponents are handled (NaN, not fabricated).
_TEAMS_REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "teams_reference.csv"
)


@lru_cache(maxsize=1)
def _load_teams_reference() -> pd.DataFrame:
    """
    Load teams_reference.csv once (48 rows: 2026 field only) and cache it.

    Has a UTF-8 BOM (Excel-exported) -- must be read with 'utf-8-sig' or the
    first column name comes back as '\\ufeffcanonical_name' and every lookup
    silently misses.
    """
    if not _TEAMS_REFERENCE_PATH.exists():
        logger.warning(
            "teams_reference.csv not found at %s -- FIFA ranking features "
            "will be NaN for every team.",
            _TEAMS_REFERENCE_PATH,
        )
        return pd.DataFrame(
            columns=["canonical_name", "fifa_ranking_pre_tournament", "elo_rating", "confederation"]
        )
    df = pd.read_csv(_TEAMS_REFERENCE_PATH, encoding="utf-8-sig")
    return df


@lru_cache(maxsize=1)
def _fifa_ranking_lookup() -> dict[str, float]:
    """canonical_name -> fifa_ranking_pre_tournament (int, lower = better)."""
    ref = _load_teams_reference()
    if "canonical_name" not in ref.columns or "fifa_ranking_pre_tournament" not in ref.columns:
        return {}
    return dict(zip(ref["canonical_name"], ref["fifa_ranking_pre_tournament"].astype(float)))


@lru_cache(maxsize=1)
def _confederation_lookup() -> dict[str, str]:
    """canonical_name -> confederation (e.g. 'UEFA', 'CAF')."""
    ref = _load_teams_reference()
    if "canonical_name" not in ref.columns or "confederation" not in ref.columns:
        return {}
    return dict(zip(ref["canonical_name"], ref["confederation"]))


def get_fifa_ranking(team_name: str) -> float:
    """
    Return the pre-tournament FIFA ranking for team_name, or NaN if the team
    isn't in the 48-team 2026 reference set (e.g. a historical-only opponent
    from matches_historical.csv's 2002-2022 rows). Never fabricated.
    """
    return _fifa_ranking_lookup().get(team_name, np.nan)


def get_confederation(team_name: str) -> Optional[str]:
    """Return the team's confederation, or None if not in the reference set."""
    return _confederation_lookup().get(team_name, None)


# ─── Tournament weight lookup ─────────────────────────────────────────────────

def get_match_weight(tournament: str) -> float:
    """Return importance weight for a tournament name."""
    if pd.isna(tournament):
        return 0.50
    t = str(tournament).strip()
    for key, w in TOURNAMENT_WEIGHTS.items():
        if key.lower() in t.lower():
            return w
    return 0.50


# ─── Time-decay weight ────────────────────────────────────────────────────────

def time_decay_weight(
    match_date: pd.Timestamp,
    reference_date: pd.Timestamp,
    half_life_days: float = DECAY_HALF_LIFE_DAYS,
) -> float:
    """
    Exponential decay: weight = 2^(-age_days / half_life_days).
    A match played exactly half_life_days ago gets weight 0.5.
    A match played today gets weight 1.0.
    """
    age_days = max((reference_date - match_date).days, 0)
    return float(2.0 ** (-age_days / half_life_days))


# ─── Elo system ───────────────────────────────────────────────────────────────

def _elo_expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _elo_update(
    elo_a: float,
    elo_b: float,
    score_a: float,
    score_b: float,
    tournament_weight: float = 1.0,
) -> float:
    """Return updated Elo for team A after a match against team B."""
    expected_a = _elo_expected(elo_a, elo_b)
    if score_a > score_b:
        actual_a = 1.0
    elif score_a == score_b:
        actual_a = 0.5
    else:
        actual_a = 0.0
    return elo_a + (K_FACTOR * tournament_weight) * (actual_a - expected_a)


def compute_dynamic_elo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pre-compute Elo ratings for every row in df (sorted by date).
    Adds columns: home_elo, away_elo, elo_difference.
    Must be called ONCE on the full dataset before feature engineering.
    """
    df = df.sort_values("date").reset_index(drop=True)
    ratings: dict[str, float] = {}
    home_elos: list[float] = []
    away_elos: list[float] = []

    for _, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        h_elo = ratings.get(home, BASE_ELO)
        a_elo = ratings.get(away, BASE_ELO)
        home_elos.append(h_elo)
        away_elos.append(a_elo)

        if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")):
            continue

        w = get_match_weight(row.get("tournament", ""))
        ratings[home] = _elo_update(h_elo, a_elo, row["home_score"], row["away_score"], w)
        ratings[away] = _elo_update(a_elo, h_elo, row["away_score"], row["home_score"], w)

    df["home_elo"] = home_elos
    df["away_elo"] = away_elos
    df["elo_difference"] = df["home_elo"] - df["away_elo"]
    return df


# ─── Team index (performance optimisation) ────────────────────────────────────

def build_team_index(df: pd.DataFrame) -> dict[str, list[int]]:
    """
    Build a mapping: team_name → sorted list of row indices where the team played.
    Avoids repeated full-DataFrame scans during feature engineering.

    Vectorised via groupby instead of a Python-level ``iterrows()`` loop —
    on a ~45k row history this is ~50-100x faster (seconds -> tens of ms),
    which matters because every ``predict()`` call rebuilds this index
    unless the caller caches it (see ``predictor.py``'s ``_team_index_cache``).
    """
    # groupby().indices gives {team_name: ndarray of positional indices} in
    # a single vectorised pass. df.index may not be a simple RangeIndex, so
    # use positional indices via reset_index-free groupby on the label arrays
    # and then map back through df.index for callers that rely on df.at[i, ...].
    home_groups = df.groupby("home_team", sort=False).indices
    away_groups = df.groupby("away_team", sort=False).indices

    index: dict[str, list[int]] = {}
    all_teams = set(home_groups.keys()) | set(away_groups.keys())
    idx_values = df.index.values
    for team in all_teams:
        pos = np.concatenate([
            home_groups.get(team, np.empty(0, dtype=np.int64)),
            away_groups.get(team, np.empty(0, dtype=np.int64)),
        ])
        pos.sort()
        index[team] = idx_values[pos].tolist()
    return index


def _latest_elo_for_team(
    df: pd.DataFrame,
    team_index: dict[str, list[int]],
    team_name: str,
    as_of_date: pd.Timestamp,
) -> float:
    """
    Return the team's Elo rating as of the most recent match strictly before
    ``as_of_date``, using the pre-built (chronologically ordered) team_index
    to avoid a full-DataFrame scan.
    """
    candidate_idx = team_index.get(team_name, [])
    if not candidate_idx:
        return BASE_ELO
    # team_index entries are chronologically ordered (df is date-sorted), so
    # scan backwards from the end for the first match before as_of_date.
    for i in reversed(candidate_idx):
        row_date = df.at[i, "date"]
        if row_date < as_of_date:
            row = df.loc[i]
            return float(
                row.get("home_elo", BASE_ELO)
                if row["home_team"] == team_name
                else row.get("away_elo", BASE_ELO)
            )
    return BASE_ELO


# ─── Rolling stats ────────────────────────────────────────────────────────────

def compute_team_rolling_stats(
    df: pd.DataFrame,
    team_name: str,
    as_of_date: pd.Timestamp,
    is_home: bool,
    window: int = 10,
    team_index: Optional[dict[str, list[int]]] = None,
) -> dict[str, float]:
    """
    Compute weighted rolling statistics for a team up to (not including) as_of_date.

    Weights combine:
      - Tournament importance
      - Recency (linear within window)
      - Time decay (exponential, 3-year half-life)
    """
    # Retrieve relevant row indices
    if team_index is not None:
        candidate_idx = team_index.get(team_name, [])
        team_matches = df.loc[
            [i for i in candidate_idx if df.at[i, "date"] < as_of_date]
        ].sort_values("date")
    else:
        team_matches = df[
            ((df["home_team"] == team_name) | (df["away_team"] == team_name))
            & (df["date"] < as_of_date)
        ].sort_values("date")

    # Drop rows with missing scores (e.g. unplayed/incomplete matches that
    # slipped through upstream filtering) *before* windowing, so they can't
    # dilute total_weight / n_recent without contributing to any numerator.
    team_matches = team_matches.dropna(subset=["home_score", "away_score"])

    if len(team_matches) == 0:
        return _empty_team_stats(is_home, window)

    recent = team_matches.tail(window)
    n_recent = len(recent)

    # Accumulators
    #
    # NOTE: attack_momentum/defense_momentum/tournament_experience/upset_score
    # accumulators were removed from this function (empirical feature-pruning
    # pass, ML Engineering wave -- see FEATURE_ENGINEERING.md "Empirical
    # feature pruning" section for the full writeup with numbers):
    #   - attack_momentum was mathematically IDENTICAL to weighted_goals_scored
    #     (both accumulate `gs * weight`) -- the emitted
    #     `{prefix}_attack_momentum_{w}` column was a byte-for-byte duplicate
    #     of `{prefix}_avg_goals_scored_{w}` (corr=1.0 on the retrained
    #     dataset), same for defense_momentum vs avg_goals_conceded.
    #   - tournament_experience (count of matches with tournament_w >= 0.80)
    #     was identical to matches_played on this WC-only corpus, since every
    #     row's tournament weight is 1.00 ("FIFA World Cup") -- always
    #     >= 0.80, so the count degenerates to a plain match count (corr=1.0).
    #   - upset_score had zero XGBoost gain importance in both hyperparameter
    #     configurations tested, and >=98% of rows evaluate to exactly 0.0 in
    #     this ~400-row corpus (upsets -- beating a 100+-Elo-higher opponent --
    #     are rare events in a small sample), i.e. near-zero variance.
    total_weight = 0.0
    weighted_points = 0.0
    weighted_goals_scored = 0.0
    weighted_goals_conceded = 0.0
    clean_sheets = 0.0
    momentum_score = 0.0
    goal_list: list[float] = []
    win_streak = 0
    unbeaten_streak = 0
    scoring_streak = 0
    conceding_streak = 0
    max_win_streak = 0
    max_unbeaten_streak = 0
    opponent_elo_total = 0.0
    home_advantage_points = 0.0
    high_scoring_matches = 0

    # Pull columns once as plain numpy/python values instead of iterating
    # with DataFrame.iterrows(), which constructs a new pandas Series (with
    # dtype inference across mixed column types) for every row -- measured
    # as the dominant per-call cost of this function (profiled: ~85% of
    # compute_team_rolling_stats's time went into iterrows()/Series
    # construction on a 419-row corpus; this matters more at tournament-
    # simulation scale, where it's called once per team per window during
    # matchup precompute). Semantics are unchanged: same per-row values,
    # same order, same accumulation logic.
    home_teams  = recent["home_team"].to_numpy()
    home_scores = recent["home_score"].to_numpy(dtype=float)
    away_scores = recent["away_score"].to_numpy(dtype=float)
    dates       = recent["date"].to_numpy()
    tournaments = recent["tournament"].to_numpy() if "tournament" in recent.columns else np.full(n_recent, "", dtype=object)
    home_elos   = recent["home_elo"].to_numpy(dtype=float) if "home_elo" in recent.columns else np.full(n_recent, BASE_ELO)
    away_elos   = recent["away_elo"].to_numpy(dtype=float) if "away_elo" in recent.columns else np.full(n_recent, BASE_ELO)
    as_of_ts = pd.Timestamp(as_of_date)

    for idx in range(n_recent):
        tournament_w = get_match_weight(tournaments[idx])
        recency_w = (idx + 1) / n_recent
        decay_w = time_decay_weight(pd.Timestamp(dates[idx]), as_of_ts)
        weight = tournament_w * recency_w * decay_w
        total_weight += weight

        if home_teams[idx] == team_name:
            gs, gc = home_scores[idx], away_scores[idx]
            opp_elo = away_elos[idx]
            played_home = True
        else:
            gs, gc = away_scores[idx], home_scores[idx]
            opp_elo = home_elos[idx]
            played_home = False

        if np.isnan(gs) or np.isnan(gc):
            continue

        opponent_elo_total += opp_elo * weight
        weighted_goals_scored += gs * weight
        weighted_goals_conceded += gc * weight
        momentum_score += (gs - gc) * weight
        goal_list.append(gs)

        if gc == 0:
            clean_sheets += weight
        if (gs + gc) >= 4:
            high_scoring_matches += 1

        if gs > gc:
            points = 3.0
            win_streak += 1
            unbeaten_streak += 1
            max_win_streak = max(max_win_streak, win_streak)
            max_unbeaten_streak = max(max_unbeaten_streak, unbeaten_streak)
        elif gs == gc:
            points = 1.0
            win_streak = 0
            unbeaten_streak += 1
            max_unbeaten_streak = max(max_unbeaten_streak, unbeaten_streak)
        else:
            points = 0.0
            win_streak = 0
            unbeaten_streak = 0

        weighted_points += points * weight
        scoring_streak = scoring_streak + 1 if gs > 0 else 0
        conceding_streak = conceding_streak + 1 if gc > 0 else 0

        if played_home and gs > gc:
            home_advantage_points += weight

    n = max(total_weight, 1e-9)
    prefix = "home" if is_home else "away"

    avg_gs = weighted_goals_scored / n
    avg_gc = weighted_goals_conceded / n
    attack_strength = avg_gs / GLOBAL_AVG_GOALS
    defense_strength = avg_gc / GLOBAL_AVG_GOALS
    volatility = float(np.std(goal_list)) if len(goal_list) > 1 else 0.0
    avg_opp_elo = opponent_elo_total / n
    high_scoring_rate = high_scoring_matches / max(n_recent, 1)

    return {
        f"{prefix}_weighted_points_{window}":          weighted_points / n,
        f"{prefix}_avg_goals_scored_{window}":         avg_gs,
        f"{prefix}_avg_goals_conceded_{window}":       avg_gc,
        f"{prefix}_attack_strength_{window}":          attack_strength,
        f"{prefix}_defense_strength_{window}":         defense_strength,
        f"{prefix}_momentum_{window}":                 momentum_score / n,
        f"{prefix}_clean_sheet_rate_{window}":         clean_sheets / n,
        f"{prefix}_goal_volatility_{window}":          volatility,
        f"{prefix}_max_win_streak_{window}":           float(max_win_streak),
        f"{prefix}_max_unbeaten_streak_{window}":      float(max_unbeaten_streak),
        f"{prefix}_current_scoring_streak_{window}":   float(scoring_streak),
        f"{prefix}_current_conceding_streak_{window}": float(conceding_streak),
        f"{prefix}_avg_opponent_elo_{window}":         avg_opp_elo,
        f"{prefix}_home_advantage_strength_{window}":  home_advantage_points / n,
        f"{prefix}_high_scoring_rate_{window}":        high_scoring_rate,
        f"{prefix}_matches_played_{window}":           float(n_recent),
    }


# ─── Rest days ────────────────────────────────────────────────────────────────

def compute_rest_days(
    df: pd.DataFrame,
    team_name: str,
    as_of_date: pd.Timestamp,
    team_index: Optional[dict[str, list[int]]] = None,
) -> float:
    """Days since the team's last match before as_of_date."""
    if team_index is not None:
        candidate_idx = team_index.get(team_name, [])
        past = df.loc[
            [i for i in candidate_idx if df.at[i, "date"] < as_of_date]
        ]
    else:
        past = df[
            ((df["home_team"] == team_name) | (df["away_team"] == team_name))
            & (df["date"] < as_of_date)
        ]

    if len(past) == 0:
        return 30.0
    last_date = past["date"].max()
    return float(max((as_of_date - last_date).days, 0))


# ─── Knockout experience ──────────────────────────────────────────────────────

def compute_knockout_experience(
    df: pd.DataFrame,
    team_name: str,
    as_of_date: pd.Timestamp,
    team_index: Optional[dict[str, list[int]]] = None,
) -> float:
    """
    Count of the team's prior knockout-stage matches (Round of 32 onward,
    per KNOCKOUT_STAGES) strictly before as_of_date.

    Requires a 'stage' column on df; returns 0.0 (not NaN) if the column is
    absent so callers on older DataFrames degrade gracefully rather than
    raising. See FEATURE_ENGINEERING.md for why this is a plain count (not
    time-decayed like rolling form) -- knockout pedigree is treated as a
    slowly-accumulating, non-decaying property of a footballing nation.
    """
    if "stage" not in df.columns:
        return 0.0

    if team_index is not None:
        candidate_idx = team_index.get(team_name, [])
        past = df.loc[
            [i for i in candidate_idx if df.at[i, "date"] < as_of_date]
        ]
    else:
        past = df[
            ((df["home_team"] == team_name) | (df["away_team"] == team_name))
            & (df["date"] < as_of_date)
        ]

    if len(past) == 0:
        return 0.0
    return float(past["stage"].isin(KNOCKOUT_STAGES).sum())


# ─── Head-to-head ─────────────────────────────────────────────────────────────

def compute_head_to_head(
    df: pd.DataFrame,
    home_team: str,
    away_team: str,
    as_of_date: pd.Timestamp,
    window: int = 10,
    team_index: Optional[dict[str, list[int]]] = None,
) -> dict[str, float]:
    """H2H record between home_team and away_team before as_of_date."""
    if team_index is not None:
        # Narrow to home_team's matches first (via the pre-built index) before
        # filtering for away_team + date — avoids a full-DataFrame scan with
        # four boolean comparisons on every call.
        candidate_idx = team_index.get(home_team, [])
        if candidate_idx:
            candidates = df.loc[candidate_idx]
            mask = (
                (
                    ((candidates["home_team"] == home_team) & (candidates["away_team"] == away_team))
                    | ((candidates["home_team"] == away_team) & (candidates["away_team"] == home_team))
                )
                & (candidates["date"] < as_of_date)
            )
            filtered = candidates[mask]
        else:
            filtered = df.iloc[0:0]
    else:
        mask = (
            (
                ((df["home_team"] == home_team) & (df["away_team"] == away_team))
                | ((df["home_team"] == away_team) & (df["away_team"] == home_team))
            )
            & (df["date"] < as_of_date)
        )
        filtered = df[mask]

    # Exclude rows with missing scores (e.g. scheduled-but-unplayed matches
    # that slipped through upstream filtering) so they can't silently
    # poison the aggregate with NaN.
    h2h = (
        filtered
        .dropna(subset=["home_score", "away_score"])
        .sort_values("date")
        .tail(window)
    )

    if len(h2h) == 0:
        return {"h2h_home_win_rate": 0.33, "h2h_avg_goals": 2.40}

    # Vectorised replacement for the previous per-row iterrows() loop --
    # this function is called once per (home_team, away_team) pair with no
    # cross-pair memoisation (unlike rolling stats/rest-days/Elo, which use
    # team_stats_cache), so it runs on every one of the O(teams^2) pairs
    # during tournament precompute. No sequential/streak state is needed
    # here, so it fully vectorises.
    is_home_perspective = (h2h["home_team"].to_numpy() == home_team)
    home_scores = h2h["home_score"].to_numpy(dtype=float)
    away_scores = h2h["away_score"].to_numpy(dtype=float)
    hg = np.where(is_home_perspective, home_scores, away_scores)
    ag = np.where(is_home_perspective, away_scores, home_scores)

    home_wins = int(np.sum(hg > ag))
    total_goals = float(np.sum(hg + ag))

    return {
        "h2h_home_win_rate": home_wins / len(h2h),
        "h2h_avg_goals":     total_goals / len(h2h),
    }


# ─── Main feature vector ──────────────────────────────────────────────────────

def build_feature_vector(
    df: pd.DataFrame,
    home_team: str,
    away_team: str,
    match_date: pd.Timestamp,
    tournament: Optional[str] = None,
    neutral_venue: bool = False,
    team_index: Optional[dict[str, list[int]]] = None,
    team_stats_cache: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Build a single-row feature DataFrame for one match.

    Parameters
    ----------
    df          : Full match history DataFrame (with Elo columns pre-computed).
    home_team   : Home team name.
    away_team   : Away team name.
    match_date  : Date of the match (features use only data BEFORE this date).
    tournament  : Tournament name (optional, used for tournament weight feature).
    neutral_venue : Whether the match is at a neutral venue.
    team_index  : Pre-built team→row-index mapping for speed (optional).
    team_stats_cache : Optional dict used to memoise per-team rolling-stats /
        rest-days / Elo lookups across repeated calls that share the same
        ``match_date`` (e.g. tournament matchup precompute, which calls this
        once per pair but each team's own stats "as of now" don't depend on
        the opponent). Pass the same dict across a batch of calls with a
        fixed match_date to skip redundant recomputation; leave as None for
        single-call usage (default, unchanged behaviour).
    """
    features: dict[str, float] = {}

    def _rolling_stats(team_name: str, is_home: bool, window: int) -> dict[str, float]:
        if team_stats_cache is None:
            return compute_team_rolling_stats(df, team_name, match_date, is_home, window, team_index)
        cache_key = ("rolling", team_name, is_home, window)
        if cache_key not in team_stats_cache:
            team_stats_cache[cache_key] = compute_team_rolling_stats(
                df, team_name, match_date, is_home, window, team_index
            )
        return team_stats_cache[cache_key]

    def _rest_days(team_name: str) -> float:
        if team_stats_cache is None:
            return compute_rest_days(df, team_name, match_date, team_index)
        cache_key = ("rest", team_name)
        if cache_key not in team_stats_cache:
            team_stats_cache[cache_key] = compute_rest_days(df, team_name, match_date, team_index)
        return team_stats_cache[cache_key]

    def _knockout_experience(team_name: str) -> float:
        if team_stats_cache is None:
            return compute_knockout_experience(df, team_name, match_date, team_index)
        cache_key = ("knockout", team_name)
        if cache_key not in team_stats_cache:
            team_stats_cache[cache_key] = compute_knockout_experience(
                df, team_name, match_date, team_index
            )
        return team_stats_cache[cache_key]

    # ── Rolling windows ──────────────────────────────────────────────────────
    for window in ROLLING_WINDOWS:
        features.update(_rolling_stats(home_team, True, window))
        features.update(_rolling_stats(away_team, False, window))

    # ── Rest days ─────────────────────────────────────────────────────────────
    features["home_rest_days"] = _rest_days(home_team)
    features["away_rest_days"] = _rest_days(away_team)

    # ── Head-to-head ──────────────────────────────────────────────────────────
    features.update(compute_head_to_head(df, home_team, away_team, match_date, team_index=team_index))

    # NOTE: `neutral_venue` and `tournament_weight` columns were REMOVED from
    # the emitted feature vector (empirical feature-pruning pass, ML
    # Engineering wave -- see FEATURE_ENGINEERING.md for the full writeup).
    # Both had exactly 0.0 XGBoost gain importance across every model in two
    # different hyperparameter configurations tested on the retrained
    # WC-only corpus, because both are CONSTANT across the entire ~400-row
    # training set: `train.py::load_data()` hardcodes every training row's
    # `tournament="FIFA World Cup"` (neutral_venue=True) since
    # matches_historical.csv is WC-only by explicit design decision (it
    # replaced the old broad "all competitions" dataset). A feature with
    # zero variance in training data cannot be split on by a tree model, so
    # keeping it costs two dead columns for no benefit.
    #   Caveat: `build_feature_vector()`'s `tournament`/`neutral_venue`
    # PARAMETERS are kept (not removed) because `predictions.py`'s API
    # accepts user-supplied tournament/neutral_venue values per request --
    # removing the parameters would be a breaking API-adjacent change out of
    # this pass's scope. The parameters are simply no longer projected into
    # the feature vector: a live request that passes a different tournament
    # or neutral_venue value has no way to influence this model's output via
    # this pathway, since the model was never trained on any variation in
    # either value. If a future retrain reintroduces non-WC matches (varying
    # tournament weight) or venue variation, both features should be added
    # back -- the removal here is a property of the current WC-only training
    # corpus, not a permanent judgement that these signals are worthless.

    # ── Elo ratings ───────────────────────────────────────────────────────────
    # Uses team_index (when available) to avoid a full-DataFrame date scan on
    # every call: team_index lists are chronologically ordered (df is sorted
    # by date ascending upstream), so the most recent match strictly before
    # match_date is found by scanning from the end of each team's index list
    # instead of re-filtering the whole history.
    if team_index is not None:
        if team_stats_cache is None:
            features["home_elo"] = _latest_elo_for_team(df, team_index, home_team, match_date)
            features["away_elo"] = _latest_elo_for_team(df, team_index, away_team, match_date)
        else:
            for team_name, feat_key in ((home_team, "home_elo"), (away_team, "away_elo")):
                cache_key = ("elo", team_name)
                if cache_key not in team_stats_cache:
                    team_stats_cache[cache_key] = _latest_elo_for_team(df, team_index, team_name, match_date)
                features[feat_key] = team_stats_cache[cache_key]
    else:
        past = df[df["date"] < match_date]
        if len(past) > 0:
            home_past = past[
                (past["home_team"] == home_team) | (past["away_team"] == home_team)
            ]
            away_past = past[
                (past["home_team"] == away_team) | (past["away_team"] == away_team)
            ]

            if len(home_past) > 0:
                r = home_past.iloc[-1]
                features["home_elo"] = float(
                    r.get("home_elo", BASE_ELO)
                    if r["home_team"] == home_team
                    else r.get("away_elo", BASE_ELO)
                )
            else:
                features["home_elo"] = BASE_ELO

            if len(away_past) > 0:
                r = away_past.iloc[-1]
                features["away_elo"] = float(
                    r.get("home_elo", BASE_ELO)
                    if r["home_team"] == away_team
                    else r.get("away_elo", BASE_ELO)
                )
            else:
                features["away_elo"] = BASE_ELO
        else:
            features["home_elo"] = BASE_ELO
            features["away_elo"] = BASE_ELO

    features["elo_difference"] = features["home_elo"] - features["away_elo"]

    # ── FIFA ranking (complementary to Elo, NOT a replacement) ────────────────
    # fifa_ranking_pre_tournament is lower-is-better (rank 1 = best), the
    # opposite polarity of Elo (higher-is-better) and goal-based features --
    # left as raw ranks (not inverted) so the model can learn its own
    # polarity/shape rather than us assuming linearity. NaN (not a fabricated
    # default) when a team isn't in the 48-team 2026 reference set -- see
    # RANKINGS_INTEGRATION.md. XGBoost handles NaN natively (it learns a
    # default split direction for missing values), so leaving these as NaN
    # here and letting downstream .fillna(0.0) in predictor.py / the training
    # matrix handle final imputation is intentional, not an oversight.
    home_rank = get_fifa_ranking(home_team)
    away_rank = get_fifa_ranking(away_team)
    features["home_fifa_rank"] = home_rank
    features["away_fifa_rank"] = away_rank
    features["fifa_rank_diff"] = home_rank - away_rank

    # ── Confederation (categorical, available in teams_reference.csv) ────────
    # Raw confederation strings aren't numeric-model-friendly, so the only
    # feature emitted here is a derived binary flag; see FEATURE_ENGINEERING.md
    # for why this is preferred over one-hot columns per confederation
    # (6 confederations x low marginal signal beyond what Elo/ranking/rest-days
    # already encode about cross-continental matchups).
    home_conf = get_confederation(home_team)
    away_conf = get_confederation(away_team)
    if home_conf is not None and away_conf is not None:
        features["same_confederation"] = float(home_conf == away_conf)
    else:
        features["same_confederation"] = np.nan

    # ── Knockout-stage experience ─────────────────────────────────────────────
    features["home_knockout_experience"] = _knockout_experience(home_team)
    features["away_knockout_experience"] = _knockout_experience(away_team)
    features["knockout_experience_diff"] = (
        features["home_knockout_experience"] - features["away_knockout_experience"]
    )

    # ── Derived differential features ────────────────────────────────────────
    # NOTE: `momentum_diff_{w}` was REMOVED (empirical feature-pruning pass,
    # ML Engineering wave -- see FEATURE_ENGINEERING.md). It is algebraically
    # IDENTICAL to `goal_diff_diff_{w}`, not merely correlated with it:
    # `home_momentum_w - away_momentum_w`
    #   = sum((gs-gc)*weight)/n_home - sum((gs-gc)*weight)/n_away
    #   = (home_avg_goals_scored_w - home_avg_goals_conceded_w)
    #     - (away_avg_goals_scored_w - away_avg_goals_conceded_w)
    #   = goal_diff_diff_w
    # Verified numerically on the retrained corpus: max |goal_diff_diff_w -
    # momentum_diff_w| across all 376 training rows was ~1e-15 (floating
    # point noise), for all three windows -- a duplicate column, not a
    # separate signal. `goal_diff_diff_{w}` is kept (equal-or-higher gain
    # importance than momentum_diff_{w} in the retrained model, and a
    # clearer name for what it measures).
    for w in ROLLING_WINDOWS:
        features[f"goal_diff_diff_{w}"] = (
            features.get(f"home_avg_goals_scored_{w}", 1.2)
            - features.get(f"home_avg_goals_conceded_{w}", 1.2)
            - features.get(f"away_avg_goals_scored_{w}", 1.2)
            + features.get(f"away_avg_goals_conceded_{w}", 1.2)
        )
        features[f"attack_diff_{w}"] = (
            features.get(f"home_attack_strength_{w}", 1.0)
            - features.get(f"away_attack_strength_{w}", 1.0)
        )
        features[f"defense_diff_{w}"] = (
            features.get(f"home_defense_strength_{w}", 1.0)
            - features.get(f"away_defense_strength_{w}", 1.0)
        )

    # ── Draw-predictive interaction features ──────────────────────────────────
    # Elo closeness: how similar are the teams? Higher = more likely draw
    features["elo_closeness"] = 1.0 / (1.0 + abs(features["elo_difference"]))
    features["elo_abs_diff"] = abs(features["elo_difference"])

    for w in ROLLING_WINDOWS:
        # Both teams defensive: product of defense strengths (high = both concede few)
        h_def = features.get(f"home_defense_strength_{w}", 1.0)
        a_def = features.get(f"away_defense_strength_{w}", 1.0)
        features[f"both_defensive_{w}"] = (2.0 - h_def) * (2.0 - a_def)

        # Both teams low-scoring: product of low attack strengths
        h_att = features.get(f"home_attack_strength_{w}", 1.0)
        a_att = features.get(f"away_attack_strength_{w}", 1.0)
        features[f"both_low_scoring_{w}"] = (2.0 - h_att) * (2.0 - a_att)

        # Form convergence: how similar is their recent form?
        h_pts = features.get(f"home_weighted_points_{w}", 1.0)
        a_pts = features.get(f"away_weighted_points_{w}", 1.0)
        features[f"form_convergence_{w}"] = 1.0 / (1.0 + abs(h_pts - a_pts))

        # Total expected goals (low total = more likely draw)
        h_gs = features.get(f"home_avg_goals_scored_{w}", 1.2)
        a_gs = features.get(f"away_avg_goals_scored_{w}", 1.2)
        features[f"expected_total_goals_{w}"] = h_gs + a_gs

    # Rest day difference (fatigue asymmetry)
    features["rest_day_diff"] = features["home_rest_days"] - features["away_rest_days"]

    return pd.DataFrame([features])


# ─── Default stats (no history) ───────────────────────────────────────────────

def _empty_team_stats(is_home: bool, window: int) -> dict[str, float]:
    """Return neutral default stats when a team has no match history."""
    prefix = "home" if is_home else "away"
    return {
        f"{prefix}_weighted_points_{window}":          1.00,
        f"{prefix}_avg_goals_scored_{window}":         1.20,
        f"{prefix}_avg_goals_conceded_{window}":       1.20,
        f"{prefix}_attack_strength_{window}":          1.00,
        f"{prefix}_defense_strength_{window}":         1.00,
        f"{prefix}_momentum_{window}":                 0.00,
        f"{prefix}_clean_sheet_rate_{window}":         0.25,
        f"{prefix}_goal_volatility_{window}":          0.00,
        f"{prefix}_max_win_streak_{window}":           0.00,
        f"{prefix}_max_unbeaten_streak_{window}":      0.00,
        f"{prefix}_current_scoring_streak_{window}":   0.00,
        f"{prefix}_current_conceding_streak_{window}": 0.00,
        f"{prefix}_avg_opponent_elo_{window}":         BASE_ELO,
        f"{prefix}_home_advantage_strength_{window}":  0.00,
        f"{prefix}_high_scoring_rate_{window}":        0.00,
        f"{prefix}_matches_played_{window}":           0.00,
    }
