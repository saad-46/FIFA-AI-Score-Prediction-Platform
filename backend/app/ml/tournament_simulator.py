"""
FIFA AI — World Cup Tournament Simulator
========================================

Monte Carlo simulation engine for World Cup-style tournaments (FIFA 2026 Format).

Features
--------
- 48 Teams, 12 Groups (A-L).
- Top 2 from each group + Best 8 3rd-placed teams advance to Round of 32.
- Deterministic R32 bracket generator preventing same-group matchups.
- Pre-computes all possible matchups (O(N^2)) to ensure fast Monte Carlo loops.
- Group Stage: Round-robin (3 pts win, 1 pt draw).
- Tiebreakers: Points → GD → GF → H2H Pts → H2H GD → H2H GF → Random.
- Knockout Stage: Single elimination from Round of 32.
- Extra Time: Handles draws in knockouts with 33% scaled xG.
- Penalties: Weighted probability based on model's win prediction.
- Multiprocessing: ProcessPoolExecutor for scalable simulations.
"""

from __future__ import annotations

import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from functools import lru_cache
from itertools import combinations
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional

# ── Project root on path ──────────────────────────────────────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logger = logging.getLogger(__name__)

# ── Processed reference data (Data Engineering wave outputs) ─────────────────
# Read-only inputs: this module never writes to these files. They live under
# app/data/processed/, sourced from the same team-name<->fifa_code bridge
# (teams_reference.csv) used to reconcile matches_historical.csv's canonical
# team names with groups.json/schedule.json's 3-letter fifa_codes.
_PROCESSED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
_TEAMS_REFERENCE_PATH = _PROCESSED_DATA_DIR / "teams_reference.csv"
_MATCHES_HISTORICAL_PATH = _PROCESSED_DATA_DIR / "matches_historical.csv"


class TournamentSimulationError(RuntimeError):
    """Raised when too many simulation batches fail to produce a trustworthy result."""


@lru_cache(maxsize=1)
def _load_name_to_code_map() -> Dict[str, str]:
    """
    Map ``teams_reference.csv``'s canonical team names to FIFA 3-letter codes
    (the vocabulary used by ``groups.json`` / ``schedule.json`` and therefore
    by ``TournamentSimulator`` internally). Returns {} if the reference file
    isn't present (keeps the simulator usable in stripped-down test/dev
    environments that don't ship the processed data directory).
    """
    if not _TEAMS_REFERENCE_PATH.exists():
        return {}
    try:
        teams_df = pd.read_csv(_TEAMS_REFERENCE_PATH, encoding="utf-8-sig")
        return dict(zip(teams_df["canonical_name"], teams_df["fifa_code"]))
    except Exception:
        logger.warning("Failed to load teams_reference.csv for name->code mapping.", exc_info=True)
        return {}


@lru_cache(maxsize=1)
def _load_team_elo_ratings() -> Dict[str, float]:
    """
    Load each 2026 team's pre-tournament Elo rating from ``teams_reference.csv``,
    keyed by FIFA code. Used as a prior for teams whose match history in the
    predictor's own DataFrame is too sparse for its own dynamic Elo to have
    converged on anything meaningful (e.g. first-time-qualified nations like
    Curaçao, Jordan, Iraq, Uzbekistan — see DATA_QUALITY_REPORT.md).
    """
    if not _TEAMS_REFERENCE_PATH.exists():
        return {}
    try:
        teams_df = pd.read_csv(_TEAMS_REFERENCE_PATH, encoding="utf-8-sig")
        name_to_code = dict(zip(teams_df["canonical_name"], teams_df["fifa_code"]))
        return {
            name_to_code[name]: float(elo)
            for name, elo in zip(teams_df["canonical_name"], teams_df["elo_rating"])
        }
    except Exception:
        logger.warning("Failed to load elo_rating from teams_reference.csv.", exc_info=True)
        return {}


@lru_cache(maxsize=1)
def _load_completed_2026_results() -> Dict[Tuple[str, str], Tuple[int, int, str]]:
    """
    Load real, already-played 2026 World Cup results from
    ``matches_historical.csv``, keyed by an order-independent pair of FIFA
    codes -> (goals_for_first_code, goals_for_second_code, winner_code_or_draw).

    Only rows with ``tournament_year == 2026`` and ``status == "Completed"``
    are included — matches still marked "Scheduled" (including the
    still-undetermined Round-of-16 slot for Canada's opponent, recorded as
    "Unknown" in the source data) are intentionally excluded so they keep
    going through real Monte Carlo simulation rather than ever being treated
    as known results.

    Team names in matches_historical.csv are in teams_reference.csv's
    "canonical_name" convention (e.g. "South Korea", "Bosnia and
    Herzegovina"), not groups.json's fifa_codes — every name is translated
    through ``_load_name_to_code_map()`` before being used as a key so
    lookups from the simulator (which works in fifa_codes throughout) work
    directly. Rows for either team that don't resolve to a known code
    (e.g. a data error or an unmapped name) are skipped defensively rather
    than raising, so a single bad row can't break the whole tournament sim.
    """
    if not _MATCHES_HISTORICAL_PATH.exists():
        return {}

    name_to_code = _load_name_to_code_map()
    if not name_to_code:
        return {}

    try:
        df = pd.read_csv(_MATCHES_HISTORICAL_PATH, encoding="utf-8-sig")
    except Exception:
        logger.warning("Failed to load matches_historical.csv for completed-results lookup.", exc_info=True)
        return {}

    results: Dict[Tuple[str, str], Tuple[int, int, str]] = {}
    real_2026 = df[(df.get("tournament_year") == 2026) & (df.get("status") == "Completed")]

    for _, row in real_2026.iterrows():
        home_name = row.get("home_team")
        away_name = row.get("away_team")
        home_code = name_to_code.get(home_name)
        away_code = name_to_code.get(away_name)
        if not home_code or not away_code:
            # e.g. the "Unknown" TBD-opponent placeholder, or an unmapped name.
            continue

        try:
            home_goals = int(row["home_score"])
            away_goals = int(row["away_score"])
        except (KeyError, TypeError, ValueError):
            continue

        if home_goals > away_goals:
            winner = home_code
        elif away_goals > home_goals:
            winner = away_code
        else:
            winner = "Draw"

        key = tuple(sorted([home_code, away_code]))
        # Store goals in the same (sorted-key) order so callers can map them
        # back to whichever of the two codes they asked about.
        if key[0] == home_code:
            results[key] = (home_goals, away_goals, winner)
        else:
            results[key] = (away_goals, home_goals, winner)

    return results


@lru_cache(maxsize=1)
def _load_real_r32_bracket() -> List[Tuple[str, str]]:
    """
    Load the actual Round-of-32 pairings from ``schedule.json`` (via
    ``app.data.fifa_2026.filter_schedule``), as a list of (team1, team2)
    FIFA-code tuples.

    Why this matters: the group stage is now fully complete in reality (see
    DATA_QUALITY_REPORT.md), so every simulation's group standings should
    reproduce the exact same 12 winners / 12 runners-up / 8 best-thirds as
    real life. But ``_run_simulation_batch``'s own Pot1/Pot2 pairing
    heuristic (pairing each Pot1 team with the first available different-
    group Pot2 team, in list-iteration order) is a simplification of FIFA's
    actual seeded draw procedure and does NOT reliably reproduce the real
    R32 pairings even when the qualified teams are identical — e.g. it may
    pair South Africa against a different Pot2 opponent than the real
    Canada match. Since schedule.json's Round of 32 entries are already
    resolved to real fifa_codes (not W##/L## placeholders — verified against
    real group results, see DATA_QUALITY_REPORT.md section (d)), using them
    directly here means real R32 results actually get consulted every time
    the group stage resolves to the real-world outcome, instead of only
    coincidentally when the heuristic pairing happens to line up.

    Returns [] if the reference schedule can't be loaded (defensive; callers
    fall back to the existing heuristic pairing in that case).
    """
    try:
        from app.data.fifa_2026 import filter_schedule
        r32_matches = filter_schedule(stage="round_of_32")
        return [(m["home_team"], m["away_team"]) for m in r32_matches]
    except Exception:
        logger.warning("Failed to load real Round-of-32 bracket from schedule.json.", exc_info=True)
        return []


def _simulate_match_static(
    team1: str,
    team2: str,
    is_knockout: bool,
    matchup_cache: Dict[str, Dict[str, Any]],
    real_results: Optional[Dict[Tuple[str, str], Tuple[int, int, str]]] = None,
) -> tuple[int, int, str]:
    """
    Simulates a single match using Poisson sampling from predicted xG.
    Returns: (team1_goals, team2_goals, winner_name_or_draw)

    If ``real_results`` is provided and this exact matchup has already been
    played in the real 2026 tournament (per matches_historical.csv, status ==
    "Completed"), the REAL recorded score is used instead of a simulated one
    — the Monte Carlo model never overwrites a known result. Matches that
    haven't been played yet (status == "Scheduled", including the
    still-undetermined Round-of-16 slot for Canada's opponent) are not in
    this dict and always fall through to genuine simulation below.

    Group-stage matches are recorded goals-and-all in matches_historical.csv
    (draws stand as draws — 1 point each, no knockout implications), so
    those are returned outright. Knockout matches, however, can never
    actually end in a draw (extra time + penalties always produce a real
    winner) — but matches_historical.csv only carries the regulation-time
    scoreline, not who won a penalty shootout. So for a knockout match whose
    real recorded score is level, we use the REAL regulation goals as the
    base (rather than fresh Poisson samples) but still resolve extra
    time/penalties the normal simulated way below, since who actually
    advanced isn't data we have.
    """
    sorted_key = tuple(sorted([team1, team2]))
    real_result = real_results.get(sorted_key) if real_results is not None else None

    key = "|".join(sorted([team1, team2]))
    pred = matchup_cache[key]

    if pred["home_team"] == team1:
        xg1 = pred["expected_home_goals"]
        xg2 = pred["expected_away_goals"]
        win_prob1 = pred["home_win_probability"]
        win_prob2 = pred["away_win_probability"]
    else:
        xg1 = pred["expected_away_goals"]
        xg2 = pred["expected_home_goals"]
        win_prob1 = pred["away_win_probability"]
        win_prob2 = pred["home_win_probability"]

    if real_result is not None:
        g_sorted1, g_sorted2, winner_code = real_result
        if sorted_key[0] == team1:
            g1, g2 = g_sorted1, g_sorted2
        else:
            g1, g2 = g_sorted2, g_sorted1

        if winner_code != "Draw":
            # Real, already-decided result (group stage draw/win, or a
            # knockout match that had a winner in regulation) — use it as-is.
            return g1, g2, winner_code
        if not is_knockout:
            return g1, g2, "Draw"
        # Knockout match, real regulation score was level: we know the real
        # goals but not the real shootout/extra-time winner, so fall through
        # to simulated extra time + penalties using these real regulation
        # goals as the starting score instead of fresh Poisson samples.
    else:
        # Poisson sampling for regulation score
        g1 = np.random.poisson(xg1)
        g2 = np.random.poisson(xg2)

    if g1 > g2:
        return g1, g2, team1
    elif g2 > g1:
        return g1, g2, team2
    else:
        # Draw in regulation
        if not is_knockout:
            return g1, g2, "Draw"
        
        # Extra time (33% of xG)
        et_g1 = np.random.poisson(xg1 * 0.33)
        et_g2 = np.random.poisson(xg2 * 0.33)
        
        g1 += et_g1
        g2 += et_g2
        
        if g1 > g2:
            return g1, g2, team1
        elif g2 > g1:
            return g1, g2, team2
        else:
            # Penalties: Weighted by model win probability
            total_prob = win_prob1 + win_prob2 + 1e-9
            if np.random.random() < (win_prob1 / total_prob):
                return g1, g2, team1
            else:
                return g1, g2, team2


def _run_simulation_batch(
    groups: Dict[str, List[str]],
    matchup_cache: Dict[str, Dict[str, Any]],
    batch_size: int,
    real_results: Optional[Dict[Tuple[str, str], Tuple[int, int, str]]] = None,
    real_r32_bracket: Optional[List[Tuple[str, str]]] = None,
) -> List[Dict[str, Dict[str, int]]]:
    """Runs a batch of simulations and returns the raw counts.

    ``real_results`` (optional): already-played 2026 matches (FIFA-code pair
    -> real score/winner), keyed the same way as
    ``_load_completed_2026_results()``. When a matchup in this batch has
    already been played for real, every simulation in the batch uses that
    real result instead of a fresh Monte Carlo draw — since the group stage
    is genuinely in progress, this keeps completed fixtures fixed while
    still-unplayed fixtures (including knockout matches, which by
    construction can never be in ``real_results`` since their participants
    are only known once earlier rounds are simulated) are simulated as
    before.

    ``real_r32_bracket`` (optional): the actual Round-of-32 pairings from
    schedule.json (see ``_load_real_r32_bracket()``). The group stage is now
    fully complete in reality, so every simulation reproduces the same 12
    winners/12 runners-up/8 best-thirds as real life — but this function's
    own Pot1/Pot2 pairing heuristic doesn't reliably reproduce the *same
    pairings* FIFA's actual draw produced even when the qualified teams
    match. When provided, and the simulated qualifiers for this run are
    exactly the 32 teams appearing in the real bracket, the real pairings
    are used directly instead of the heuristic — so real R32 results (from
    ``real_results``) actually get consulted on every simulation rather than
    only when the heuristic coincidentally lines up. Falls back to the
    heuristic pairing whenever the qualifier set doesn't match (e.g. a
    simulated group produces a different qualifier than reality, or custom
    non-2026 groups are being simulated).
    """

    all_teams = []
    group_names_map = {}
    for g_name, g_teams in groups.items():
        all_teams.extend(g_teams)
        for t in g_teams:
            group_names_map[t] = g_name

    batch_stats = {
        team: {"group": 0, "r32": 0, "r16": 0, "qf": 0, "sf": 0, "third_place": 0, "final": 0, "winner": 0}
        for team in all_teams
    }

    for _ in range(batch_size):
        group_standings = {}
        third_placed_teams = []
        runners_up_ranked = []

        # --- GROUP STAGE ---
        for group_name, group_teams in groups.items():
            points = {t: 0 for t in group_teams}
            gd = {t: 0 for t in group_teams}
            gf = {t: 0 for t in group_teams}
            h2h_pts = defaultdict(int)
            h2h_gd = defaultdict(int)
            h2h_gf = defaultdict(int)

            for t1, t2 in combinations(group_teams, 2):
                g1, g2, winner = _simulate_match_static(
                    t1, t2, is_knockout=False, matchup_cache=matchup_cache, real_results=real_results
                )

                gf[t1] += g1
                gf[t2] += g2
                gd[t1] += (g1 - g2)
                gd[t2] += (g2 - g1)

                if winner == t1:
                    points[t1] += 3
                    h2h_pts[f"{t1}|{t2}"] += 3
                    h2h_gd[f"{t1}|{t2}"] += (g1 - g2)
                    h2h_gf[f"{t1}|{t2}"] += g1
                    h2h_gd[f"{t2}|{t1}"] += (g2 - g1)
                    h2h_gf[f"{t2}|{t1}"] += g2
                elif winner == t2:
                    points[t2] += 3
                    h2h_pts[f"{t2}|{t1}"] += 3
                    h2h_gd[f"{t2}|{t1}"] += (g2 - g1)
                    h2h_gf[f"{t2}|{t1}"] += g2
                    h2h_gd[f"{t1}|{t2}"] += (g1 - g2)
                    h2h_gf[f"{t1}|{t2}"] += g1
                else:
                    points[t1] += 1
                    points[t2] += 1
                    h2h_pts[f"{t1}|{t2}"] += 1
                    h2h_pts[f"{t2}|{t1}"] += 1
                    h2h_gf[f"{t1}|{t2}"] += g1
                    h2h_gf[f"{t2}|{t1}"] += g2

            # Sort group: Points -> GD -> GF -> H2H -> Random
            def sort_key(t):
                # H2H metrics sum against all teams (simplified for 4-team groups)
                t_h2h_pts = sum(h2h_pts[f"{t}|{other}"] for other in group_teams if other != t)
                t_h2h_gd = sum(h2h_gd[f"{t}|{other}"] for other in group_teams if other != t)
                t_h2h_gf = sum(h2h_gf[f"{t}|{other}"] for other in group_teams if other != t)
                return (points[t], gd[t], gf[t], t_h2h_pts, t_h2h_gd, t_h2h_gf, np.random.random())

            ranked_teams = sorted(group_teams, key=sort_key, reverse=True)
            group_standings[group_name] = ranked_teams

            # Record the 2nd placed (runner-up) and 3rd placed team, along with
            # the sort_key used to rank them, so they can be compared across groups.
            if len(ranked_teams) >= 2:
                t2 = ranked_teams[1]
                runners_up_ranked.append((t2, sort_key(t2)))
            if len(ranked_teams) >= 3:
                t3 = ranked_teams[2]
                third_placed_teams.append((t3, sort_key(t3)))

        for t in all_teams:
            batch_stats[t]["group"] += 1

        # --- RANK THIRD-PLACED TEAMS ---
        # Sort by the exact same group metrics
        third_placed_teams.sort(key=lambda x: x[1], reverse=True)
        best_8_thirds = [x[0] for x in third_placed_teams[:8]]

        # --- QUALIFIED TEAMS ---
        winners = [group_standings[g][0] for g in groups.keys()]

        # --- R32 BRACKET GENERATION (Pot 1 vs Pot 2) ---
        # Pot 1: 12 Winners + 4 Best Runners-Up (ranked by points -> GD -> GF -> H2H)
        # Pot 2: 8 Remaining Runners-Up + 8 Best Thirds
        runners_up_ranked.sort(key=lambda x: x[1], reverse=True)
        best_4_runners_up = [x[0] for x in runners_up_ranked[:4]]
        remaining_runners_up = [x[0] for x in runners_up_ranked[4:]]

        pot1 = winners + best_4_runners_up
        pot2 = remaining_runners_up + best_8_thirds

        r32_bracket = None
        if real_r32_bracket:
            qualified = set(pot1) | set(pot2)
            real_bracket_teams = {t for pair in real_r32_bracket for t in pair}
            if qualified == real_bracket_teams:
                # This simulation's qualifiers are exactly the real world's
                # R32 field — use the real pairings so real_results actually
                # gets consulted, instead of a heuristic pairing that may
                # send these same 32 teams into different matchups.
                r32_bracket = list(real_r32_bracket)

        if r32_bracket is None:
            # Pair them up avoiding same group (heuristic fallback — used
            # whenever the simulated qualifiers diverge from the real bracket,
            # or no real bracket was supplied at all, e.g. custom groups).
            r32_bracket = []
            unpaired_pot2 = list(pot2)

            for p1_team in pot1:
                p1_group = group_names_map[p1_team]
                paired = False
                for p2_team in unpaired_pot2:
                    if group_names_map[p2_team] != p1_group:
                        r32_bracket.append((p1_team, p2_team))
                        unpaired_pot2.remove(p2_team)
                        paired = True
                        break
                if not paired:
                    # Fallback if constraint impossible
                    r32_bracket.append((p1_team, unpaired_pot2.pop(0)))

        # Play R32 — the only knockout round where a matchup could already
        # have a real result (per matches_historical.csv). R16-onward
        # participants are only known once earlier rounds are resolved in
        # this simulated bracket, so those pairings can never coincide with
        # an already-played real fixture; real_results is still threaded
        # through for consistency and so a future round that does start
        # partially-resolved doesn't need new plumbing.
        r16_teams = []
        for t1, t2 in r32_bracket:
            batch_stats[t1]["r32"] += 1
            batch_stats[t2]["r32"] += 1
            _, _, winner = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )
            r16_teams.append(winner)

        # Play R16
        qf_teams = []
        for i in range(0, len(r16_teams) - 1, 2):
            t1, t2 = r16_teams[i], r16_teams[i+1]
            batch_stats[t1]["r16"] += 1
            batch_stats[t2]["r16"] += 1
            _, _, winner = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )
            qf_teams.append(winner)

        # Play QF
        sf_teams = []
        for i in range(0, len(qf_teams) - 1, 2):
            t1, t2 = qf_teams[i], qf_teams[i+1]
            batch_stats[t1]["qf"] += 1
            batch_stats[t2]["qf"] += 1
            _, _, winner = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )
            sf_teams.append(winner)

        # Play SF
        final_teams = []
        third_place_teams = []
        for i in range(0, len(sf_teams) - 1, 2):
            t1, t2 = sf_teams[i], sf_teams[i+1]
            batch_stats[t1]["sf"] += 1
            batch_stats[t2]["sf"] += 1
            _, _, winner = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )
            final_teams.append(winner)
            third_place_teams.append(t1 if winner == t2 else t2)

        # Play Third Place
        if len(third_place_teams) == 2:
            t1, t2 = third_place_teams[0], third_place_teams[1]
            batch_stats[t1]["third_place"] += 1
            batch_stats[t2]["third_place"] += 1
            _, _, _ = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )

        # Play Final
        if len(final_teams) == 2:
            t1, t2 = final_teams[0], final_teams[1]
            batch_stats[t1]["final"] += 1
            batch_stats[t2]["final"] += 1
            _, _, winner = _simulate_match_static(
                t1, t2, is_knockout=True, matchup_cache=matchup_cache, real_results=real_results
            )
            batch_stats[winner]["winner"] += 1

    return batch_stats


class TournamentSimulator:
    def __init__(self, predictor, df: pd.DataFrame, use_real_results: bool = True):
        """
        Parameters
        ----------
        predictor : MatchPredictor
        df        : Full historical match DataFrame passed to the predictor.
        use_real_results : If True (default), matchups that have already been
            played in the real 2026 tournament (per matches_historical.csv,
            status == "Completed") use the REAL recorded score instead of a
            simulated one — see ``_load_completed_2026_results()``. Matches
            still marked "Scheduled" always go through genuine Monte Carlo
            simulation regardless of this flag; it only ever suppresses
            *re-simulating* a fact that's already known, never fabricates a
            result for an unplayed match. Set False to simulate the entire
            tournament hypothetically from a blank slate (e.g. for what-if
            scenarios with custom groups that don't correspond to the real
            2026 bracket).
        """
        self.predictor = predictor
        self.df = df
        self.matchup_cache: Dict[str, Dict[str, Any]] = {}
        self.use_real_results = use_real_results
        self.real_results: Dict[Tuple[str, str], Tuple[int, int, str]] = (
            _load_completed_2026_results() if use_real_results else {}
        )
        self.real_r32_bracket: List[Tuple[str, str]] = (
            _load_real_r32_bracket() if use_real_results else []
        )
        self.team_elo_ratings: Dict[str, float] = _load_team_elo_ratings()

    def _get_matchup_key(self, team1: str, team2: str) -> str:
        return "|".join(sorted([team1, team2]))

    def _elo_fallback_prediction(self, team1: str, team2: str) -> Dict[str, Any]:
        """
        Last-resort matchup estimate for when the trained model's prediction
        call itself raises (e.g. a transient error) — used only inside the
        per-pair fallback loop in ``_precompute_matchups``, after the batched
        predict_batch() call already failed.

        Previously this was a flat 1.0/1.0 xG, 33/33/34 guess that ignored
        team strength entirely, regardless of how mismatched the two teams
        actually are. Now it's informed by ``teams_reference.csv``'s
        pre-tournament Elo ratings (``self.team_elo_ratings``, keyed by FIFA
        code) when both teams have one — the same Elo formula the feature
        pipeline itself uses (``_elo_expected``) converts the rating gap into
        a win-probability estimate, and goals are split around a neutral
        1.35 average total proportionally to that probability. Falls back to
        the previous flat neutral estimate if either team's rating is
        unavailable (e.g. team codes not present in teams_reference.csv).
        """
        elo1 = self.team_elo_ratings.get(team1)
        elo2 = self.team_elo_ratings.get(team2)

        if elo1 is None or elo2 is None:
            return {
                "home_team": team1,
                "away_team": team2,
                "expected_home_goals": 1.0,
                "expected_away_goals": 1.0,
                "home_win_probability": 0.33,
                "away_win_probability": 0.33,
                "draw_probability": 0.34,
            }

        # Standard Elo expected-score formula (matches
        # app.ml.features.feature_engineering._elo_expected).
        expected1 = 1.0 / (1.0 + 10.0 ** ((elo2 - elo1) / 400.0))
        draw_probability = 0.26  # roughly the historical international-match draw rate
        home_win_probability = expected1 * (1 - draw_probability)
        away_win_probability = (1 - expected1) * (1 - draw_probability)

        # Split a neutral total-goals expectation proportionally to relative
        # strength, keeping both teams' xG within a sane floor/ceiling.
        total_goals = 2.6
        expected_home_goals = float(np.clip(total_goals * expected1, 0.4, 4.0))
        expected_away_goals = float(np.clip(total_goals * (1 - expected1), 0.4, 4.0))

        return {
            "home_team": team1,
            "away_team": team2,
            "expected_home_goals": expected_home_goals,
            "expected_away_goals": expected_away_goals,
            "home_win_probability": round(home_win_probability, 4),
            "away_win_probability": round(away_win_probability, 4),
            "draw_probability": round(draw_probability, 4),
        }

    def _precompute_matchups(self, teams: List[str]) -> None:
        """
        Pre-computes all pairwise matchups.

        Uses MatchPredictor.predict_batch() to build feature vectors for all
        pairs and run model inference in a small number of vectorised batch
        calls, rather than calling predict() once per pair sequentially.
        For 48 teams that's 1128 pairs — at ~200ms/call (dominated by SHAP
        + per-call model round-trips), the old sequential loop cost minutes;
        batching removes the per-pair SHAP cost entirely (unused here) and
        collapses the model inference into O(1) calls, cutting this step to
        roughly the cost of feature-vector construction alone.

        Falls back to a per-pair predict_batch call (still batched, just a
        batch of one) if the whole-batch call fails for any reason, so a
        single bad pair can't take down the entire precompute step.
        """
        pairs = [
            (t1, t2) for t1, t2 in combinations(teams, 2)
            if self._get_matchup_key(t1, t2) not in self.matchup_cache
        ]
        if not pairs:
            return

        logger.info("Pre-computing predictions for %d potential matchups...", len(pairs))
        match_date = pd.Timestamp.now()

        # The simulator works in FIFA codes ("BRA"); the predictor's match
        # history is keyed by team name ("Brazil"). Asking the predictor about
        # a code it has never seen returns a no-history default, and "USA" is
        # the only code that is also a name -- which made it the only real team
        # in the tournament. Translate for the predictor; keep the simulator's
        # own labels everywhere else. Labels that are not FIFA codes (custom
        # groups) pass through unchanged.
        code_to_name = {code: name for name, code in _load_name_to_code_map().items()}

        def history_name(team: str) -> str:
            return code_to_name.get(team, team)

        try:
            batch_results = self.predictor.predict_batch(
                df=self.df,
                pairs=[(history_name(t1), history_name(t2)) for t1, t2 in pairs],
                tournament="World Cup",
                neutral_venue=True,
                match_date=match_date,
            )
            batch_results = list(batch_results)
            if len(batch_results) != len(pairs):
                raise ValueError(
                    f"predict_batch returned {len(batch_results)} results for "
                    f"{len(pairs)} pairs"
                )
            for (t1, t2), pred in zip(pairs, batch_results):
                key = self._get_matchup_key(t1, t2)
                self.matchup_cache[key] = {
                    "home_team": t1,
                    "away_team": t2,
                    "expected_home_goals": pred["expected_home_goals"],
                    "expected_away_goals": pred["expected_away_goals"],
                    "home_win_probability": pred["home_win_probability"],
                    "away_win_probability": pred["away_win_probability"],
                    "draw_probability": pred["draw_probability"],
                }
            return
        except Exception as e:
            logger.warning(
                f"Batch matchup prediction failed ({e}); falling back to per-pair prediction."
            )

        for t1, t2 in pairs:
            key = self._get_matchup_key(t1, t2)
            if key in self.matchup_cache:
                continue

            try:
                pred = self.predictor.predict(
                    df=self.df,
                    home_team=history_name(t1),
                    away_team=history_name(t2),
                    tournament="World Cup",
                    neutral_venue=True,
                    match_date=match_date
                )

                # Make sure the prediction dict is fully JSON serializable and decoupled from models

                self.matchup_cache[key] = {
                    "home_team": t1,
                    "away_team": t2,
                    "expected_home_goals": pred["expected_home_goals"],
                    "expected_away_goals": pred["expected_away_goals"],
                    "home_win_probability": pred["home_win_probability"],
                    "away_win_probability": pred["away_win_probability"],
                    "draw_probability": pred["draw_probability"],
                }
            except Exception as e:
                logger.warning(
                    f"Prediction failed for {t1} vs {t2}: {e}. "
                    "Falling back to an Elo-informed neutral estimate."
                )
                self.matchup_cache[key] = self._elo_fallback_prediction(t1, t2)

    def simulate_tournament(self, groups: Dict[str, List[str]], n_simulations: int = 10000) -> Dict[str, Dict[str, float]]:
        """
        Run Monte Carlo simulations of the FIFA 2026 tournament.
        Supports multiprocessing for extreme speed.

        If ``self.use_real_results`` is True (the default), any matchup that
        has already been played in the real, in-progress 2026 tournament
        uses its real recorded score in every simulation instead of a fresh
        Monte Carlo draw (see ``_load_completed_2026_results()``); matches
        that haven't been played yet are always genuinely simulated.
        """
        all_teams = []
        for g_teams in groups.values():
            all_teams.extend(g_teams)

        if len(all_teams) != 48:
            logger.warning(f"FIFA 2026 requires 48 teams. Found {len(all_teams)}.")

        if self.use_real_results and self.real_results:
            logger.info(
                "Using %d real completed 2026 result(s) instead of simulating them; "
                "remaining fixtures are Monte Carlo simulated as usual.",
                len(self.real_results),
            )

        # 1. Pre-compute
        self._precompute_matchups(all_teams)

        # 2. Divide into batches for multiprocessing
        n_workers = max(1, multiprocessing.cpu_count() - 1)
        batch_size = max(1, n_simulations // n_workers)
        batches = [batch_size] * n_workers
        
        # Handle remainder
        remainder = n_simulations - sum(batches)
        if remainder > 0:
            batches[-1] += remainder

        aggregated_stats = {
            team: {"group": 0, "r32": 0, "r16": 0, "qf": 0, "sf": 0, "third_place": 0, "final": 0, "winner": 0}
            for team in all_teams
        }

        # 3. Execute in parallel
        logger.info(f"Running {n_simulations} simulations across {n_workers} processes...")
        completed_simulations = 0
        failed_batches: List[int] = []
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            future_to_batch_size = {
                executor.submit(
                    _run_simulation_batch,
                    groups,
                    self.matchup_cache,
                    b,
                    self.real_results,
                    self.real_r32_bracket,
                ): b
                for b in batches
            }

            for future in as_completed(future_to_batch_size):
                batch_size_for_future = future_to_batch_size[future]
                try:
                    batch_res = future.result()
                    for t, stats in batch_res.items():
                        for stage, count in stats.items():
                            aggregated_stats[t][stage] += count
                    completed_simulations += batch_size_for_future
                except Exception:
                    failed_batches.append(batch_size_for_future)
                    logger.exception(
                        "Simulation batch of size %d failed and was excluded from results.",
                        batch_size_for_future,
                    )

        total_batches = len(batches)
        if failed_batches:
            failed_simulations = sum(failed_batches)
            logger.error(
                "%d/%d simulation batches failed (%d/%d simulations lost).",
                len(failed_batches), total_batches, failed_simulations, n_simulations,
            )

        # If nothing succeeded, or a large fraction of the requested simulations
        # were lost, the aggregated stats are not trustworthy enough to normalize
        # and silently return — surface a hard failure instead.
        if completed_simulations == 0:
            raise TournamentSimulationError(
                f"All {total_batches} simulation batches failed; no results were produced. "
                "See logs for the underlying exception tracebacks."
            )

        failure_fraction = 1 - (completed_simulations / n_simulations)
        if failure_fraction > 0.25:
            raise TournamentSimulationError(
                f"{len(failed_batches)}/{total_batches} simulation batches failed "
                f"({failure_fraction:.0%} of requested simulations lost). Aborting rather than "
                "returning results skewed by partial data. See logs for tracebacks."
            )

        # 4. Normalize against the simulations that actually completed, so a
        # partial (but tolerated) failure doesn't silently understate probabilities.
        normalized_stats = {}
        for team, team_stats in aggregated_stats.items():
            normalized_stats[team] = {
                stage: (count / completed_simulations if stage != "group" else 1.0)
                for stage, count in team_stats.items()
            }

        return normalized_stats
