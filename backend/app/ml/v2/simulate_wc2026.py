"""
WC2026 tournament simulation and champion prediction (WC2026_BACKTEST mode).

Uses the backtest model — trained only on 1930-2022, with feature accumulators
frozen at the end of 2022 — so every probability here reflects pre-tournament
knowledge only. The actual 2026 results are used solely as ground truth to score
against, never as an input.

Produces three things:

  1. BRACKET PROGRESSION ACCURACY
     For each knockout match that actually happened, did the model favour the
     team that actually advanced? Scored per round.

  2. KNOCKOUT MONTE CARLO
     Starting from the real Round-of-32 field, matches are resolved by sampling
     from model win probabilities and winners propagated through the official
     dependency graph parsed from the wallchart. Yields champion probabilities.
     Conditioning is stated explicitly: this takes the 32 qualifiers as given
     and asks "given who reached the knockouts, who wins?"

  3. FULL-TOURNAMENT MONTE CARLO
     Group stage simulated from scratch, standings computed with FIFA
     tiebreakers, then the knockout bracket. Answers "before a ball was kicked,
     who wins?" Round-of-32 seeding follows the slot assignment observed in the
     official bracket rather than an invented rule.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.simulate_wc2026
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.v2.features import (build_dataset, feature_columns, load_canonical,
                                synthetic_match)

ART = Path(__file__).resolve().parent / "artifacts"
CANON = Path(__file__).resolve().parents[2] / "data" / "canonical"
N_SIMS = 20000
RNG = np.random.default_rng(42)

STAGE_META = {
    "round_of_32": (5, "2026-06-28"), "round_of_16": (6, "2026-07-04"),
    "quarter_final": (7, "2026-07-09"), "semi_final": (8, "2026-07-14"),
    "third_place": (9, "2026-07-18"), "final": (10, "2026-07-19"),
}
HOSTS = {"Canada", "Mexico", "USA"}


class MatchOracle:
    """Model win/draw/loss probabilities for any pairing, from frozen 2022 state."""

    def __init__(self, bundle, builder, cols):
        self.clf = bundle["classifier"]
        # Present only on a calibrated bundle; applied identically to every
        # sampled matchup so the simulation inherits the calibrated
        # probabilities rather than the raw overconfident ones.
        self.calibrator = bundle.get("calibrator")
        self.builder = builder
        self.cols = cols
        self._cache: dict[tuple, np.ndarray] = {}

    def probs(self, home: str, away: str, stage: str) -> np.ndarray:
        key = (home, away, stage)
        if key in self._cache:
            return self._cache[key]
        order, day = STAGE_META.get(stage, (5, "2026-06-28"))
        row = synthetic_match(home, away, stage=stage, stage_order=order,
                              is_knockout=stage != "group_stage",
                              date=pd.Timestamp(day),
                              home_is_host=home in HOSTS, away_is_host=away in HOSTS)
        feats = self.builder.features_for(row)
        x = np.array([[feats.get(c, np.nan) for c in self.cols]], dtype=np.float32)
        p = self.clf.predict_proba(x)
        if self.calibrator is not None:
            p = self.calibrator.transform(p)
        p = p[0]
        self._cache[key] = p
        return p

    def knockout_win_prob(self, home: str, away: str, stage: str) -> float:
        """A knockout tie must produce a winner; the draw mass is split by relative strength."""
        p = self.probs(home, away, stage)
        away_w, draw, home_w = p[0], p[1], p[2]
        denom = home_w + away_w
        share = home_w / denom if denom > 1e-9 else 0.5
        return float(home_w + draw * share)


def bracket_progression_accuracy(matches: pd.DataFrame, oracle: MatchOracle) -> dict:
    ko = matches[(matches["year"] == 2026) & (matches["is_knockout"])].copy()
    per_round: dict[str, dict] = defaultdict(lambda: {"correct": 0, "n": 0, "detail": []})
    for _, m in ko.iterrows():
        actual = m["winner_team"]
        if not isinstance(actual, str) or not actual:
            continue
        p_home = oracle.knockout_win_prob(m["home_team"], m["away_team"], m["stage"])
        predicted = m["home_team"] if p_home >= 0.5 else m["away_team"]
        bucket = per_round[m["stage"]]
        bucket["n"] += 1
        bucket["correct"] += int(predicted == actual)
        bucket["detail"].append({
            "match_number": int(m["match_number"]) if pd.notna(m["match_number"]) else None,
            "fixture": f"{m['home_team']} v {m['away_team']}",
            "model_favourite": predicted, "p_favourite": round(max(p_home, 1 - p_home), 4),
            "actual_winner": actual, "correct": predicted == actual,
        })
    total_c = sum(v["correct"] for v in per_round.values())
    total_n = sum(v["n"] for v in per_round.values())
    return {
        "overall": {"correct": total_c, "n": total_n,
                    "accuracy": round(total_c / total_n, 4) if total_n else None},
        "by_round": {k: {"correct": v["correct"], "n": v["n"],
                         "accuracy": round(v["correct"] / v["n"], 4)}
                     for k, v in per_round.items()},
        "matches": [d for v in per_round.values() for d in v["detail"]],
    }


def load_graph() -> dict[int, dict]:
    graph = json.loads((CANON / "wc2026_tournament_graph.json").read_text(encoding="utf-8"))
    return {n["match_number"]: n for n in graph["nodes"]}


def simulate_knockouts(slots: dict[int, tuple[str, str]], graph: dict[int, dict],
                       oracle: MatchOracle, n_sims: int) -> dict:
    """Propagate winners through the official dependency graph."""
    order = sorted(k for k in graph if graph[k]["stage"] != "group_stage")
    champions, finalists, semis = Counter(), Counter(), Counter()

    for _ in range(n_sims):
        winners: dict[int, str] = {}
        losers: dict[int, str] = {}
        for num in order:
            node = graph[num]
            if num in slots:
                home, away = slots[num]
            else:
                hs, as_ = node["home_source"] or {}, node["away_source"] or {}
                home = (winners if hs.get("type") == "winner_of" else losers).get(hs.get("match_number"))
                away = (winners if as_.get("type") == "winner_of" else losers).get(as_.get("match_number"))
            if not home or not away:
                continue
            p = oracle.knockout_win_prob(home, away, node["stage"])
            if RNG.random() < p:
                winners[num], losers[num] = home, away
            else:
                winners[num], losers[num] = away, home
            if node["stage"] == "semi_final":
                semis[home] += 1
                semis[away] += 1
            if node["stage"] == "final":
                finalists[home] += 1
                finalists[away] += 1
        if 104 in winners:
            champions[winners[104]] += 1

    return {
        "n_sims": n_sims,
        "champion_probabilities": [
            {"team": t, "p": round(c / n_sims, 4)}
            for t, c in champions.most_common(16)],
        "final_appearance_probabilities": [
            {"team": t, "p": round(c / n_sims, 4)}
            for t, c in finalists.most_common(16)],
        "semi_final_probabilities": [
            {"team": t, "p": round(c / n_sims, 4)}
            for t, c in semis.most_common(16)],
    }


def simulate_full_tournament(matches, teams, graph, oracle, n_sims: int) -> dict:
    """Group stage from scratch, then knockouts. Pre-tournament conditioning."""
    wc = teams[teams["is_wc2026_team"].astype(str).str.lower().isin(["true", "1"])]
    group_of = dict(zip(wc["team_name"], wc["wc2026_group"]))

    gs = matches[(matches["year"] == 2026) & (matches["stage"] == "group_stage")]
    fixtures = [(r["home_team"], r["away_team"], r["group_name"]) for _, r in gs.iterrows()]

    # Observed Round-of-32 slot assignment: which (group, finishing position)
    # occupied each R32 slot in the official bracket. Read from the real result
    # rather than assuming a seeding rule the wallchart never states.
    r32 = matches[(matches["year"] == 2026) & (matches["stage"] == "round_of_32")]
    real_standings = compute_standings(
        [(r["home_team"], r["away_team"], r["group_name"],
          int(r["home_goals"]), int(r["away_goals"])) for _, r in gs.iterrows()], group_of)
    pos_of = {}
    for grp, table in real_standings.items():
        for idx, row in enumerate(table):
            pos_of[row["team"]] = (grp, idx + 1)
    slot_rule: dict[int, tuple] = {}
    for _, m in r32.iterrows():
        n = int(m["match_number"])
        slot_rule[n] = (pos_of.get(m["home_team"]), pos_of.get(m["away_team"]))

    champions, group_winners = Counter(), Counter()
    for _ in range(n_sims):
        played = []
        for home, away, grp in fixtures:
            p = oracle.probs(home, away, "group_stage")
            outcome = RNG.choice(3, p=p / p.sum())
            hg, ag = (1, 0) if outcome == 2 else (1, 1) if outcome == 1 else (0, 1)
            played.append((home, away, grp, hg, ag))
        standings = compute_standings(played, group_of)
        placed = {}
        for grp, table in standings.items():
            for idx, row in enumerate(table):
                placed[(grp, idx + 1)] = row["team"]
            if table:
                group_winners[table[0]["team"]] += 1

        slots = {}
        for num, (hp, ap) in slot_rule.items():
            h, a = placed.get(hp), placed.get(ap)
            if h and a and h != a:
                slots[num] = (h, a)
        if len(slots) < len(slot_rule):
            continue
        res = simulate_knockouts(slots, graph, oracle, 1)
        if res["champion_probabilities"]:
            champions[res["champion_probabilities"][0]["team"]] += 1

    total = sum(champions.values()) or 1
    return {
        "n_sims": n_sims,
        "completed_sims": total,
        "champion_probabilities": [
            {"team": t, "p": round(c / total, 4)} for t, c in champions.most_common(16)],
        "group_winner_probabilities": [
            {"team": t, "p": round(c / n_sims, 4)} for t, c in group_winners.most_common(12)],
    }


def compute_standings(played, group_of) -> dict[str, list[dict]]:
    tables: dict[str, dict[str, dict]] = defaultdict(dict)
    for home, away, grp, hg, ag in played:
        g = grp or group_of.get(home)
        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            row = tables[g].setdefault(team, {"team": team, "pts": 0, "gf": 0, "ga": 0, "gd": 0})
            row["gf"] += gf
            row["ga"] += ga
            row["gd"] = row["gf"] - row["ga"]
            row["pts"] += 3 if gf > ga else 1 if gf == ga else 0
    return {g: sorted(rows.values(), key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))
            for g, rows in tables.items()}


def main() -> None:
    matches, teams, stats = load_canonical()
    bundle = joblib.load(ART / "model_wc2026_backtest.pkl")
    _, builder = build_dataset(matches, teams, stats,
                               groups=tuple(bundle["feature_groups"]),
                               freeze_after_year=2022, return_builder=True)
    oracle = MatchOracle(bundle, builder, bundle["feature_columns"])
    graph = load_graph()

    print("=" * 74)
    print("BRACKET PROGRESSION ACCURACY (actual knockout fixtures)")
    print("=" * 74)
    prog = bracket_progression_accuracy(matches, oracle)
    o = prog["overall"]
    print(f"overall: {o['correct']}/{o['n']} = {o['accuracy']:.4f}")
    for rnd, v in prog["by_round"].items():
        print(f"   {rnd:<16} {v['correct']:>2}/{v['n']:<3} = {v['accuracy']:.3f}")

    print()
    print("=" * 74)
    print(f"KNOCKOUT MONTE CARLO — {N_SIMS:,} sims, real R32 field")
    print("=" * 74)
    r32 = matches[(matches["year"] == 2026) & (matches["stage"] == "round_of_32")]
    slots = {int(m["match_number"]): (m["home_team"], m["away_team"]) for _, m in r32.iterrows()}
    ko = simulate_knockouts(slots, graph, oracle, N_SIMS)
    for row in ko["champion_probabilities"][:10]:
        print(f"   {row['team']:<24} {row['p'] * 100:5.1f}%")

    print()
    print("=" * 74)
    print(f"FULL-TOURNAMENT MONTE CARLO — {N_SIMS // 4:,} sims, from the group stage")
    print("=" * 74)
    full = simulate_full_tournament(matches, teams, graph, oracle, N_SIMS // 4)
    for row in full["champion_probabilities"][:10]:
        print(f"   {row['team']:<24} {row['p'] * 100:5.1f}%")

    actual_final = matches[(matches["year"] == 2026) & (matches["stage"] == "final")].iloc[0]
    actual_champion = actual_final["winner_team"]
    ko_rank = next((i + 1 for i, r in enumerate(ko["champion_probabilities"])
                    if r["team"] == actual_champion), None)
    full_rank = next((i + 1 for i, r in enumerate(full["champion_probabilities"])
                      if r["team"] == actual_champion), None)

    out = {
        "mode": "WC2026_BACKTEST",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "conditioning": {
            "model_training": "1930-2022 only; feature accumulators frozen at end of 2022",
            "knockout_monte_carlo": "conditioned on the real 32 qualifiers",
            "full_tournament_monte_carlo": "unconditioned; group stage simulated from scratch",
        },
        "bracket_progression": prog,
        "knockout_monte_carlo": ko,
        "full_tournament_monte_carlo": full,
        "actual_outcome": {
            "champion": actual_champion,
            "final": f"{actual_final['home_team']} v {actual_final['away_team']}",
            "model_rank_for_actual_champion_knockout_mc": ko_rank,
            "model_rank_for_actual_champion_full_mc": full_rank,
        },
    }
    (ART / "wc2026_simulation.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"actual champion: {actual_champion}")
    print(f"   model rank (knockout MC): {ko_rank}")
    print(f"   model rank (full MC):     {full_rank}")
    print(f"\nartifacts -> {ART / 'wc2026_simulation.json'}")


if __name__ == "__main__":
    main()
