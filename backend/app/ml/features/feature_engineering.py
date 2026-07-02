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

Performance notes:
  - Elo ratings are pre-computed once per DataFrame (compute_dynamic_elo)
  - Team match indices are pre-built (build_team_index) to avoid repeated scans
  - Rolling stats iterate only over the tail window, not the full history
"""

from __future__ import annotations

import logging
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
    total_weight = 0.0
    weighted_points = 0.0
    weighted_goals_scored = 0.0
    weighted_goals_conceded = 0.0
    clean_sheets = 0.0
    momentum_score = 0.0
    attack_momentum = 0.0
    defense_momentum = 0.0
    goal_list: list[float] = []
    win_streak = 0
    unbeaten_streak = 0
    scoring_streak = 0
    conceding_streak = 0
    max_win_streak = 0
    max_unbeaten_streak = 0
    opponent_elo_total = 0.0
    home_advantage_points = 0.0
    tournament_experience = 0
    upset_score = 0.0
    high_scoring_matches = 0

    for idx, (_, row) in enumerate(recent.iterrows()):
        tournament_w = get_match_weight(row.get("tournament", ""))
        recency_w = (idx + 1) / n_recent
        decay_w = time_decay_weight(row["date"], as_of_date)
        weight = tournament_w * recency_w * decay_w
        total_weight += weight

        if row["home_team"] == team_name:
            gs, gc = float(row["home_score"]), float(row["away_score"])
            opp_elo = float(row.get("away_elo", BASE_ELO))
            played_home = True
        else:
            gs, gc = float(row["away_score"]), float(row["home_score"])
            opp_elo = float(row.get("home_elo", BASE_ELO))
            played_home = False

        if np.isnan(gs) or np.isnan(gc):
            continue

        opponent_elo_total += opp_elo * weight
        weighted_goals_scored += gs * weight
        weighted_goals_conceded += gc * weight
        attack_momentum += gs * weight
        defense_momentum += gc * weight
        momentum_score += (gs - gc) * weight
        goal_list.append(gs)

        if gc == 0:
            clean_sheets += weight
        if tournament_w >= 0.80:
            tournament_experience += 1
        if (gs + gc) >= 4:
            high_scoring_matches += 1

        if gs > gc:
            points = 3.0
            win_streak += 1
            unbeaten_streak += 1
            max_win_streak = max(max_win_streak, win_streak)
            max_unbeaten_streak = max(max_unbeaten_streak, unbeaten_streak)
            if opp_elo > BASE_ELO + 100:
                upset_score += 1.5 * weight
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
        f"{prefix}_attack_momentum_{window}":          attack_momentum / n,
        f"{prefix}_defense_momentum_{window}":         defense_momentum / n,
        f"{prefix}_clean_sheet_rate_{window}":         clean_sheets / n,
        f"{prefix}_goal_volatility_{window}":          volatility,
        f"{prefix}_max_win_streak_{window}":           float(max_win_streak),
        f"{prefix}_max_unbeaten_streak_{window}":      float(max_unbeaten_streak),
        f"{prefix}_current_scoring_streak_{window}":   float(scoring_streak),
        f"{prefix}_current_conceding_streak_{window}": float(conceding_streak),
        f"{prefix}_avg_opponent_elo_{window}":         avg_opp_elo,
        f"{prefix}_tournament_experience_{window}":    float(tournament_experience),
        f"{prefix}_home_advantage_strength_{window}":  home_advantage_points / n,
        f"{prefix}_upset_score_{window}":              upset_score / n,
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

    home_wins = 0
    total_goals = 0.0
    for _, row in h2h.iterrows():
        if row["home_team"] == home_team:
            hg, ag = float(row["home_score"]), float(row["away_score"])
        else:
            hg, ag = float(row["away_score"]), float(row["home_score"])
        total_goals += hg + ag
        if hg > ag:
            home_wins += 1

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

    # ── Rolling windows ──────────────────────────────────────────────────────
    for window in ROLLING_WINDOWS:
        features.update(_rolling_stats(home_team, True, window))
        features.update(_rolling_stats(away_team, False, window))

    # ── Rest days ─────────────────────────────────────────────────────────────
    features["home_rest_days"] = _rest_days(home_team)
    features["away_rest_days"] = _rest_days(away_team)

    # ── Head-to-head ──────────────────────────────────────────────────────────
    features.update(compute_head_to_head(df, home_team, away_team, match_date, team_index=team_index))

    # ── Neutral venue ─────────────────────────────────────────────────────────
    features["neutral_venue"] = float(neutral_venue)

    # ── Tournament weight ─────────────────────────────────────────────────────
    features["tournament_weight"] = get_match_weight(tournament or "")

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

    # ── Derived differential features ────────────────────────────────────────
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
        features[f"momentum_diff_{w}"] = (
            features.get(f"home_momentum_{w}", 0.0)
            - features.get(f"away_momentum_{w}", 0.0)
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
        f"{prefix}_attack_momentum_{window}":          1.20,
        f"{prefix}_defense_momentum_{window}":         1.20,
        f"{prefix}_clean_sheet_rate_{window}":         0.25,
        f"{prefix}_goal_volatility_{window}":          0.00,
        f"{prefix}_max_win_streak_{window}":           0.00,
        f"{prefix}_max_unbeaten_streak_{window}":      0.00,
        f"{prefix}_current_scoring_streak_{window}":   0.00,
        f"{prefix}_current_conceding_streak_{window}": 0.00,
        f"{prefix}_avg_opponent_elo_{window}":         BASE_ELO,
        f"{prefix}_tournament_experience_{window}":    0.00,
        f"{prefix}_home_advantage_strength_{window}":  0.00,
        f"{prefix}_upset_score_{window}":              0.00,
        f"{prefix}_high_scoring_rate_{window}":        0.00,
        f"{prefix}_matches_played_{window}":           0.00,
    }
