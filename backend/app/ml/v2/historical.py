"""
Historical tournament simulation — the core walk-forward engine for
evaluating (and improving) V2 on 2002/2006/2010/2014/2018/2022 before ever
touching WC2026.

METHODOLOGICAL CORRECTION vs. the original ablation (experiments.py)
----------------------------------------------------------------------------
The original ablation's ``walk_forward()`` built features with
``freeze_after_year=None`` — accumulators updated continuously through the
WHOLE dataset. Because ``FeatureBuilder`` emits a row's features before
folding that row in, this never leaked a match's own outcome into its own
features. But it DID let earlier matches of the SAME tournament inform later
matches of that SAME tournament (e.g. a team's group-stage form entering its
own quarter-final features) — legitimate for "predict the next match knowing
the tournament so far", but not what this task asks for: "pretend you are
standing before that tournament" and predict the WHOLE thing at once.

Every fold here therefore freezes accumulators at ``year - 1``, exactly
mirroring how the already-approved WC2026 backtest bundle was built
(``freeze_after_year=2022``). No match in the target year can inform any
other match in that same year. This is stricter than the original ablation,
so its 0.4978 accuracy figure is not directly comparable to anything
produced here — the "Current V2" baseline is re-measured under this regime
specifically so the final comparison table (Phase 15) compares like with
like.

WC2026 is never a parameter to any function in this module. The six years
below are hardcoded as the only years this module will ever train up to or
evaluate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss,
                             f1_score, log_loss, mean_absolute_error,
                             mean_squared_error, precision_score, recall_score)
from xgboost import XGBClassifier, XGBRegressor

from app.ml.v2.experiments import CLF_PARAMS, REG_PARAMS
from app.ml.v2.features import build_dataset, feature_columns, load_canonical
from app.ml.v2.simulate_wc2026 import MatchOracle, compute_standings

#: The only six years this module will ever evaluate. WC2026 (2026) never
#: appears in this list, by construction — not by discipline alone.
HISTORICAL_YEARS = [2002, 2006, 2010, 2014, 2018, 2022]
CLASS_NAMES = {0: "away_win", 1: "draw", 2: "home_win"}
EPS = 1e-12


# ═══════════════════════════════════════════════════════════════════════════
# Metrics (shared vocabulary with the calibration phase, extended with
# precision/recall/F1 and draw Brier as this task requires)
# ═══════════════════════════════════════════════════════════════════════════

def expected_calibration_error(y, proba, bins: int = 10) -> float:
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def reliability_buckets(y, proba) -> list[dict]:
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    out = []
    for lo, hi in [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7),
                   (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]:
        m = (conf > lo) & (conf <= hi)
        if not m.sum():
            continue
        out.append({"bucket": f"{int(lo*100)}-{int(hi*100)}%", "n": int(m.sum()),
                    "mean_confidence": round(float(conf[m].mean()), 4),
                    "empirical_accuracy": round(float(correct[m].mean()), 4)})
    return out


def full_metrics(y, proba, home_true=None, away_true=None, home_pred=None, away_pred=None) -> dict:
    pred = proba.argmax(axis=1)
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y)), y] = 1.0
    draw_true = (y == 1).astype(int)
    draw_prob = proba[:, 1]
    m = {
        "n": int(len(y)),
        "accuracy": round(float(accuracy_score(y, pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y, pred)), 4),
        "precision_macro": round(float(precision_score(y, pred, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y, pred, average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y, pred, average="macro", zero_division=0)), 4),
        "log_loss": round(float(log_loss(y, proba, labels=[0, 1, 2])), 4),
        "brier_multiclass": round(float(np.mean(np.sum((proba - onehot) ** 2, axis=1))), 4),
        "ece": round(expected_calibration_error(y, proba), 4),
        "draw_precision": round(float(precision_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "draw_recall": round(float(recall_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "draw_f1": round(float(f1_score(y, pred, labels=[1], average="macro", zero_division=0)), 4),
        "draw_brier": round(float(brier_score_loss(draw_true, draw_prob)), 4),
        "reliability": reliability_buckets(y, proba),
    }
    if home_pred is not None:
        m["home_goals_mae"] = round(float(mean_absolute_error(home_true, home_pred)), 4)
        m["away_goals_mae"] = round(float(mean_absolute_error(away_true, away_pred)), 4)
        m["total_goals_mae"] = round(float(mean_absolute_error(
            np.asarray(home_true) + np.asarray(away_true),
            np.asarray(home_pred) + np.asarray(away_pred))), 4)
        m["home_goals_rmse"] = round(float(np.sqrt(mean_squared_error(home_true, home_pred))), 4)
        m["away_goals_rmse"] = round(float(np.sqrt(mean_squared_error(away_true, away_pred))), 4)
    return m


def composite_objective(m: dict) -> float:
    """
    Documented weighting (Phase 9). Lower is better (it's a loss).
    Weights sum to 1.0 across the five ranked criteria; score-quality is a
    smaller tie-breaking term so it can't dominate the ranking on its own.

        0.35  chronological log loss     (primary — proper scoring rule)
        0.20  Brier score
        0.15  1 - accuracy               (converted to a loss)
        0.15  ECE
        0.10  1 - draw_f1                (draw performance, F1 not recall alone
                                           so it can't be gamed by over-predicting draws)
        0.05  mean(home_goals_mae, away_goals_mae) / 3   (scaled into [0,~1] range)
    """
    score_term = (m.get("home_goals_mae", 0) + m.get("away_goals_mae", 0)) / 2 / 3.0
    return (
        0.35 * m["log_loss"]
        + 0.20 * m["brier_multiclass"]
        + 0.15 * (1 - m["accuracy"])
        + 0.15 * m["ece"]
        + 0.10 * (1 - m["draw_f1"])
        + 0.05 * score_term
    )


# ═══════════════════════════════════════════════════════════════════════════
# Per-tournament walk-forward fold
# ═══════════════════════════════════════════════════════════════════════════

def _train(train: pd.DataFrame, cols: list[str], clf_params: dict, reg_params: dict):
    X = train[cols].to_numpy(np.float32)
    y = train["target_result"].to_numpy(int)
    clf = XGBClassifier(**clf_params).fit(X, y)
    hr = XGBRegressor(**reg_params).fit(X, train["home_goals"].to_numpy(np.float32))
    ar = XGBRegressor(**reg_params).fit(X, train["away_goals"].to_numpy(np.float32))
    return clf, hr, ar


def run_tournament_fold(matches: pd.DataFrame, teams: pd.DataFrame, stats: pd.DataFrame,
                        year: int, groups: tuple[str, ...],
                        clf_params: dict = CLF_PARAMS, reg_params: dict = REG_PARAMS,
                        exclude_features: tuple[str, ...] = (),
                        light: bool = False) -> dict:
    """
    Train on everything strictly before `year` (accumulators frozen at
    year-1 — see module docstring), predict every match of `year`, return the
    full ledger plus metrics plus knockout progression plus the fitted
    model/oracle for downstream group-qualification / champion-MC use.

    `exclude_features` drops named columns AFTER the full group set has been
    built, for testing feature redundancy (e.g. "does dropping the absolute
    FIFA-rank columns and keeping only the difference change anything?")
    without needing a new FeatureBuilder group.

    `light=True` skips the group-qualification Monte Carlo (2000 sims x 8
    groups — the most expensive part of a fold) and returns an empty dict for
    it. Knockout progression is cheap (a lookup, not a simulation) and always
    computed. Used by the hyperparameter search, which only needs the
    classifier/regressor metrics that feed the composite objective and would
    otherwise pay full group-MC cost on every one of ~30 trials for no
    benefit — group qualification isn't part of what's being tuned there.
    """
    df, builder = build_dataset(matches, teams, stats, groups=groups,
                                freeze_after_year=year - 1, return_builder=True)
    cols = [c for c in feature_columns(df) if c not in exclude_features]
    train = df[(df["year"] < year) & df["target_result"].notna()]
    test = df[(df["year"] == year) & df["target_result"].notna()]
    if train.empty or test.empty:
        raise ValueError(f"no train/test data for year={year}")

    clf, hr, ar = _train(train, cols, clf_params, reg_params)
    Xte = test[cols].to_numpy(np.float32)
    proba = clf.predict_proba(Xte)
    hp, ap = hr.predict(Xte), ar.predict(Xte)
    y_true = test["target_result"].to_numpy(int)

    ledger = test[["match_id", "date", "stage", "home_team", "away_team",
                   "home_goals", "away_goals"]].copy()
    ledger["tournament_year"] = year
    ledger["predicted_home_goals"] = np.round(hp, 3)
    ledger["predicted_away_goals"] = np.round(ap, 3)
    ledger["away_win_probability"] = proba[:, 0].round(4)
    ledger["draw_probability"] = proba[:, 1].round(4)
    ledger["home_win_probability"] = proba[:, 2].round(4)
    pred_class = proba.argmax(axis=1)
    ledger["predicted_result"] = [CLASS_NAMES[c] for c in pred_class]
    ledger["actual_result"] = [CLASS_NAMES[c] for c in y_true]
    ledger["predicted_winner"] = [
        row.home_team if c == 2 else row.away_team if c == 0 else "Draw"
        for row, c in zip(ledger.itertuples(), pred_class)
    ]
    ledger["actual_winner"] = [
        row.home_team if c == 2 else row.away_team if c == 0 else "Draw"
        for row, c in zip(ledger.itertuples(), y_true)
    ]
    ledger["correct"] = ledger["predicted_result"] == ledger["actual_result"]
    ledger["confidence"] = proba.max(axis=1).round(4)
    ledger["model_version"] = "historical-fold"

    metrics = full_metrics(y_true, proba, test["home_goals"].to_numpy(),
                           test["away_goals"].to_numpy(), hp, ap)
    metrics["composite_objective"] = round(composite_objective(metrics), 5)

    oracle = MatchOracle({"classifier": clf, "calibrator": None}, builder, cols)
    progression = _knockout_progression(matches, year, oracle)
    group_qual = ({"note": "skipped (light mode)", "teams": [],
                   "brier_score": None, "team_level_qualification_accuracy": None}
                 if light else _group_qualification(matches, teams, year, oracle))

    return {
        "year": year, "ledger": ledger, "metrics": metrics,
        "progression": progression, "group_qualification": group_qual,
        "model": (clf, hr, ar, cols, builder), "oracle": oracle,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Knockout progression accuracy — data-driven (Phase 4, 10)
# ═══════════════════════════════════════════════════════════════════════════

def _knockout_progression(matches: pd.DataFrame, year: int, oracle: MatchOracle) -> dict:
    """For every knockout match that actually happened, did the model favour
    the team that actually advanced? Purely data-driven — no simulator
    involved, so a failure here is unambiguously a MATCH-MODEL error, not a
    tournament-simulator error (see Phase 10)."""
    ko = matches[(matches["year"] == year) & (matches["is_knockout"])]
    by_stage: dict[str, dict] = {}
    rows = []
    for m in ko.itertuples():
        winner = m.winner_team
        if not isinstance(winner, str) or not winner:
            continue
        p_home = oracle.knockout_win_prob(m.home_team, m.away_team, m.stage)
        favourite = m.home_team if p_home >= 0.5 else m.away_team
        bucket = by_stage.setdefault(m.stage, {"correct": 0, "n": 0})
        bucket["n"] += 1
        bucket["correct"] += int(favourite == winner)
        rows.append({"stage": m.stage, "home": m.home_team, "away": m.away_team,
                     "favourite": favourite, "p_favourite": round(max(p_home, 1 - p_home), 4),
                     "actual_winner": winner, "correct": favourite == winner})
    total_c = sum(v["correct"] for v in by_stage.values())
    total_n = sum(v["n"] for v in by_stage.values())
    return {
        "overall": {"correct": total_c, "n": total_n,
                    "accuracy": round(total_c / total_n, 4) if total_n else None},
        "by_stage": {k: {**v, "accuracy": round(v["correct"] / v["n"], 4)} for k, v in by_stage.items()},
        "matches": rows,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Group qualification (Phase 4) — Monte Carlo from match-level probabilities
# ═══════════════════════════════════════════════════════════════════════════

def _group_qualification(matches: pd.DataFrame, teams: pd.DataFrame, year: int,
                         oracle: MatchOracle, n_sims: int = 2000, seed: int = 42) -> dict:
    gs = matches[(matches["year"] == year) & (matches["stage"] == "group_stage")]
    if gs.empty:
        return {"note": "no group_stage rows for this year", "teams": []}

    group_of = {}
    for m in gs.itertuples():
        if isinstance(m.group_name, str) and m.group_name:
            group_of[m.home_team] = m.group_name
            group_of[m.away_team] = m.group_name

    # Actual qualifiers: top 2 by (points, GD, GF) from the real results.
    played_actual = [(m.home_team, m.away_team, group_of.get(m.home_team, "?"),
                     int(m.home_goals), int(m.away_goals))
                     for m in gs.itertuples() if pd.notna(m.home_goals)]
    actual_standings = compute_standings(played_actual, group_of)
    actual_qualifiers = {row["team"] for table in actual_standings.values() for row in table[:2]}

    fixtures = [(m.home_team, m.away_team, group_of.get(m.home_team, "?")) for m in gs.itertuples()]
    rng = np.random.default_rng(seed)
    qual_count: dict[str, int] = {t: 0 for t in group_of}

    for _ in range(n_sims):
        played = []
        for home, away, grp in fixtures:
            p = oracle.probs(home, away, "group_stage")
            outcome = rng.choice(3, p=p / p.sum())
            hg, ag = (1, 0) if outcome == 2 else (1, 1) if outcome == 1 else (0, 1)
            played.append((home, away, grp, hg, ag))
        standings = compute_standings(played, group_of)
        for table in standings.values():
            for row in table[:2]:
                qual_count[row["team"]] = qual_count.get(row["team"], 0) + 1

    rows, sq_errors = [], []
    for team, grp in group_of.items():
        p_qual = qual_count.get(team, 0) / n_sims
        actual = 1 if team in actual_qualifiers else 0
        sq_errors.append((p_qual - actual) ** 2)
        rows.append({"team": team, "group": grp, "simulated_qualification_prob": round(p_qual, 4),
                    "actually_qualified": bool(actual)})

    # "top-2-by-model-probability equals actual qualifiers" accuracy, per group
    hits, total_groups = 0, 0
    for grp in set(group_of.values()):
        team_probs = [(r["team"], r["simulated_qualification_prob"]) for r in rows if r["group"] == grp]
        predicted_top2 = {t for t, _ in sorted(team_probs, key=lambda x: -x[1])[:2]}
        actual_top2 = {r["team"] for r in rows if r["group"] == grp and r["actually_qualified"]}
        hits += len(predicted_top2 & actual_top2)
        total_groups += 1

    return {
        "n_sims": n_sims,
        "brier_score": round(float(np.mean(sq_errors)), 4),
        "team_level_qualification_hits": hits,
        "team_level_qualification_total": total_groups * 2,
        "team_level_qualification_accuracy": round(hits / (total_groups * 2), 4) if total_groups else None,
        "teams": sorted(rows, key=lambda r: (-r["simulated_qualification_prob"])),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Historical bracket derivation + champion Monte Carlo (Phase 10-12)
# ═══════════════════════════════════════════════════════════════════════════

def derive_bracket_from_data(matches: pd.DataFrame, year: int) -> dict:
    """
    Reconstruct the knockout dependency graph purely from who actually beat
    whom — no external bracket document, no assumed seeding rule. For every
    knockout match, each side's "source" is whichever earlier-stage match in
    the same tournament that side's team won (or, for the third-place match,
    lost). This is a real, verifiable graph, not an invented one: re-run it
    and you get back the exact bracket that actually happened.

    Two node categories are EXPECTED to have no resolvable source, and are
    not counted as errors:
      * round_of_16 — the bracket's entry point. Its participants come from
        group-stage qualification, not from an earlier knockout match; they
        are reported separately as `r16_pairings`, not as graph sources.
      * third_place — sourced from the LOSERS of the semi-finals. Tracked
        via a separate `loser_of_match` map alongside the winners map.
    """
    stage_rank = {"round_of_16": 1, "quarter_final": 2, "semi_final": 3,
                 "third_place": 4, "final": 4}
    ko = matches[(matches["year"] == year) & (matches["stage"].isin(stage_rank))].copy()
    ko["rank"] = ko["stage"].map(stage_rank)
    ko = ko.sort_values(["rank", "date"])

    graph = {}
    winner_of_match: dict[int, dict] = {}  # rank -> {team_name: match_id they won}
    loser_of_match: dict[int, dict] = {}   # rank -> {team_name: match_id they lost}
    for m in ko.itertuples():
        node = {"match_id": m.match_id, "stage": m.stage,
               "home_source": None, "away_source": None}
        if m.stage == "third_place":
            prior = loser_of_match.get(m.rank - 1, {})
        elif m.rank > 1:
            prior = winner_of_match.get(m.rank - 1, {})
        else:
            prior = {}
        node["home_source"] = prior.get(m.home_team)
        node["away_source"] = prior.get(m.away_team)
        graph[m.match_id] = {"row": m, "node": node}

        if isinstance(m.winner_team, str) and m.winner_team:
            winner_of_match.setdefault(m.rank, {})[m.winner_team] = m.match_id
            loser_team = m.away_team if m.winner_team == m.home_team else m.home_team
            loser_of_match.setdefault(m.rank, {})[loser_team] = m.match_id

    r16 = ko[ko["stage"] == "round_of_16"]
    r16_pairings = [(m.home_team, m.away_team) for m in r16.itertuples()]

    # Only count a node as unresolved if it's a stage that SHOULD have a
    # source (i.e. not round_of_16, which is the bracket's entry point).
    unresolved = sum(
        1 for g in graph.values()
        if g["node"]["stage"] != "round_of_16"
        and (g["node"]["home_source"] is None or g["node"]["away_source"] is None)
    )
    return {"graph": graph, "r16_pairings": r16_pairings, "unresolved_sources": unresolved}


def champion_monte_carlo(matches: pd.DataFrame, year: int, oracle: MatchOracle,
                         n_sims: int = 20000, seed: int = 42) -> dict:
    """Monte Carlo champion simulation conditioned on the REAL Round-of-16
    field (the same conditioning style as the WC2026 'knockout MC')."""
    bracket = derive_bracket_from_data(matches, year)
    if bracket["unresolved_sources"] > 0 or not bracket["r16_pairings"]:
        return {"error": f"could not fully derive bracket for {year} "
                          f"({bracket['unresolved_sources']} unresolved sources)"}

    rng = np.random.default_rng(seed)
    from collections import Counter
    champions = Counter()

    stage_next = {"round_of_16": "quarter_final", "quarter_final": "semi_final",
                 "semi_final": "final"}

    for _ in range(n_sims):
        winners: dict[str, str] = {}
        for stage in ("round_of_16", "quarter_final", "semi_final", "final"):
            for mid, g in bracket["graph"].items():
                if g["node"]["stage"] != stage:
                    continue
                node = g["node"]
                if stage == "round_of_16":
                    home, away = g["row"].home_team, g["row"].away_team
                else:
                    home = winners.get(node["home_source"])
                    away = winners.get(node["away_source"])
                if not home or not away:
                    continue
                p = oracle.knockout_win_prob(home, away, stage)
                winners[mid] = home if rng.random() < p else away
        final_ids = [mid for mid, g in bracket["graph"].items() if g["node"]["stage"] == "final"]
        if final_ids and final_ids[0] in winners:
            champions[winners[final_ids[0]]] += 1

    total = sum(champions.values()) or 1
    ranked = [{"team": t, "p": round(c / total, 4)} for t, c in champions.most_common()]

    actual_final = matches[(matches["year"] == year) & (matches["stage"] == "final")]
    actual_champion = actual_final.iloc[0]["winner_team"] if not actual_final.empty else None
    rank = next((i + 1 for i, r in enumerate(ranked) if r["team"] == actual_champion), None)
    p_actual = next((r["p"] for r in ranked if r["team"] == actual_champion), 0.0)

    return {
        "year": year, "n_sims": n_sims, "completed_sims": total,
        "champion_probabilities": ranked[:16],
        "actual_champion": actual_champion,
        "actual_champion_rank": rank,
        "actual_champion_probability": p_actual,
        "actual_champion_in_top3": bool(rank and rank <= 3),
        "actual_champion_in_top5": bool(rank and rank <= 5),
        "brier_champion": round((1 - p_actual) ** 2, 4),
    }


def monte_carlo_convergence(matches: pd.DataFrame, year: int, oracle: MatchOracle,
                            sim_counts: tuple[int, ...] = (10_000, 50_000, 100_000)) -> dict:
    """Does the champion distribution stabilise as n_sims grows?"""
    runs = {n: champion_monte_carlo(matches, year, oracle, n_sims=n) for n in sim_counts}
    top_team_by_n = {n: (r["champion_probabilities"][0]["team"] if r.get("champion_probabilities") else None)
                     for n, r in runs.items()}
    prob_by_n = {}
    all_teams = {row["team"] for r in runs.values() for row in r.get("champion_probabilities", [])}
    for team in all_teams:
        prob_by_n[team] = {n: next((row["p"] for row in r.get("champion_probabilities", [])
                                    if row["team"] == team), 0.0) for n, r in runs.items()}
    max_counts = list(sim_counts)
    max_drift = max(
        (abs(prob_by_n[t][max_counts[-1]] - prob_by_n[t][max_counts[-2]]) for t in all_teams),
        default=0.0,
    )
    return {"year": year, "top_team_by_sim_count": top_team_by_n,
           "max_probability_drift_last_two_counts": round(max_drift, 4),
           "converged": max_drift < 0.01, "detail": prob_by_n}


# ═══════════════════════════════════════════════════════════════════════════
# Full historical run — all six tournaments
# ═══════════════════════════════════════════════════════════════════════════

def run_historical_simulation(groups: tuple[str, ...], clf_params: dict = CLF_PARAMS,
                              reg_params: dict = REG_PARAMS,
                              years: list[int] = HISTORICAL_YEARS,
                              exclude_features: tuple[str, ...] = (),
                              light: bool = False) -> dict:
    matches, teams, stats = load_canonical()
    folds = {}
    ledgers = []
    for year in years:
        fold = run_tournament_fold(matches, teams, stats, year, groups, clf_params, reg_params,
                                   exclude_features=exclude_features, light=light)
        folds[year] = fold
        ledgers.append(fold["ledger"])

    full_ledger = pd.concat(ledgers, ignore_index=True)
    agg_keys = ["accuracy", "balanced_accuracy", "log_loss", "brier_multiclass", "ece",
               "draw_recall", "draw_f1", "draw_brier", "home_goals_mae", "away_goals_mae",
               "composite_objective"]
    means = {k: round(float(np.mean([folds[y]["metrics"][k] for y in years])), 4) for k in agg_keys}
    stds = {k: round(float(np.std([folds[y]["metrics"][k] for y in years])), 4) for k in agg_keys}

    prog_c = sum(folds[y]["progression"]["overall"]["correct"] for y in years)
    prog_n = sum(folds[y]["progression"]["overall"]["n"] for y in years)

    return {
        "years": years,
        "per_tournament": {y: {"metrics": folds[y]["metrics"],
                               "progression": folds[y]["progression"]["overall"],
                               "group_qualification": {
                                   k: v for k, v in folds[y]["group_qualification"].items() if k != "teams"}}
                           for y in years},
        "aggregate": {"mean": means, "std": stds,
                     "knockout_progression_accuracy": round(prog_c / prog_n, 4) if prog_n else None},
        "ledger": full_ledger,
        "folds": folds,  # includes fitted models/oracles for downstream reuse — not JSON-serialisable
    }
