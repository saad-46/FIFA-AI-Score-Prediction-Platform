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
from itertools import combinations
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple

# ── Project root on path ──────────────────────────────────────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logger = logging.getLogger(__name__)


class TournamentSimulationError(RuntimeError):
    """Raised when too many simulation batches fail to produce a trustworthy result."""


def _simulate_match_static(team1: str, team2: str, is_knockout: bool, matchup_cache: Dict[str, Dict[str, Any]]) -> tuple[int, int, str]:
    """
    Simulates a single match using Poisson sampling from predicted xG.
    Returns: (team1_goals, team2_goals, winner_name_or_draw)
    """
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


def _run_simulation_batch(groups: Dict[str, List[str]], matchup_cache: Dict[str, Dict[str, Any]], batch_size: int) -> List[Dict[str, Dict[str, int]]]:
    """Runs a batch of simulations and returns the raw counts."""
    
    # We return a list of stats dictionaries per simulation to sum them up later.
    # To save memory, we can just return an aggregated stats dict for this batch.
    
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
                g1, g2, winner = _simulate_match_static(t1, t2, is_knockout=False, matchup_cache=matchup_cache)
                
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
        
        # Pair them up avoiding same group
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

        # Play R32
        r16_teams = []
        for t1, t2 in r32_bracket:
            batch_stats[t1]["r32"] += 1
            batch_stats[t2]["r32"] += 1
            _, _, winner = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            r16_teams.append(winner)

        # Play R16
        qf_teams = []
        for i in range(0, len(r16_teams) - 1, 2):
            t1, t2 = r16_teams[i], r16_teams[i+1]
            batch_stats[t1]["r16"] += 1
            batch_stats[t2]["r16"] += 1
            _, _, winner = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            qf_teams.append(winner)

        # Play QF
        sf_teams = []
        for i in range(0, len(qf_teams) - 1, 2):
            t1, t2 = qf_teams[i], qf_teams[i+1]
            batch_stats[t1]["qf"] += 1
            batch_stats[t2]["qf"] += 1
            _, _, winner = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            sf_teams.append(winner)

        # Play SF
        final_teams = []
        third_place_teams = []
        for i in range(0, len(sf_teams) - 1, 2):
            t1, t2 = sf_teams[i], sf_teams[i+1]
            batch_stats[t1]["sf"] += 1
            batch_stats[t2]["sf"] += 1
            _, _, winner = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            final_teams.append(winner)
            third_place_teams.append(t1 if winner == t2 else t2)

        # Play Third Place
        if len(third_place_teams) == 2:
            t1, t2 = third_place_teams[0], third_place_teams[1]
            batch_stats[t1]["third_place"] += 1
            batch_stats[t2]["third_place"] += 1
            _, _, _ = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            
        # Play Final
        if len(final_teams) == 2:
            t1, t2 = final_teams[0], final_teams[1]
            batch_stats[t1]["final"] += 1
            batch_stats[t2]["final"] += 1
            _, _, winner = _simulate_match_static(t1, t2, is_knockout=True, matchup_cache=matchup_cache)
            batch_stats[winner]["winner"] += 1

    return batch_stats


class TournamentSimulator:
    def __init__(self, predictor, df: pd.DataFrame):
        self.predictor = predictor
        self.df = df
        self.matchup_cache: Dict[str, Dict[str, Any]] = {}

    def _get_matchup_key(self, team1: str, team2: str) -> str:
        return "|".join(sorted([team1, team2]))

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

        try:
            batch_results = self.predictor.predict_batch(
                df=self.df,
                pairs=pairs,
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
                    "home_team": pred["home_team"],
                    "away_team": pred["away_team"],
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
                    home_team=t1,
                    away_team=t2,
                    tournament="World Cup",
                    neutral_venue=True,
                    match_date=match_date
                )

                # Make sure the prediction dict is fully JSON serializable and decoupled from models

                self.matchup_cache[key] = {
                    "home_team": pred["home_team"],
                    "away_team": pred["away_team"],
                    "expected_home_goals": pred["expected_home_goals"],
                    "expected_away_goals": pred["expected_away_goals"],
                    "home_win_probability": pred["home_win_probability"],
                    "away_win_probability": pred["away_win_probability"],
                    "draw_probability": pred["draw_probability"],
                }
            except Exception as e:
                logger.warning(f"Prediction failed for {t1} vs {t2}: {e}. Falling back to 1.0 xG each.")
                self.matchup_cache[key] = {
                    "home_team": t1,
                    "away_team": t2,
                    "expected_home_goals": 1.0,
                    "expected_away_goals": 1.0,
                    "home_win_probability": 0.33,
                    "away_win_probability": 0.33,
                    "draw_probability": 0.34,
                }

    def simulate_tournament(self, groups: Dict[str, List[str]], n_simulations: int = 10000) -> Dict[str, Dict[str, float]]:
        """
        Run Monte Carlo simulations of the FIFA 2026 tournament.
        Supports multiprocessing for extreme speed.
        """
        all_teams = []
        for g_teams in groups.values():
            all_teams.extend(g_teams)
            
        if len(all_teams) != 48:
            logger.warning(f"FIFA 2026 requires 48 teams. Found {len(all_teams)}.")

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
                executor.submit(_run_simulation_batch, groups, self.matchup_cache, b): b
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
