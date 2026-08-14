"""
Systematic error categorization (Phase 5).

Takes the in-memory result of ``historical.run_historical_simulation()``
(not just the saved CSV — this needs the fitted builders to recover elo/rank
context for each match) and buckets every wrong prediction into named error
categories, then reports which categories are large enough to be systematic
(not just noise) versus which look randomly distributed.

Per the task: this module only CLASSIFIES errors. It does not propose or
apply fixes — that happens in run_experiments.py, and only for categories
found here to be large and structurally explicable.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from app.ml.v2.features import load_canonical


def categorize_errors(sim_result: dict) -> dict:
    matches, _, _ = load_canonical()
    result_method = matches.set_index("match_id")["result_method"].to_dict()
    stage_order = matches.set_index("match_id")["stage_order"].to_dict()

    rows = []
    for year, fold in sim_result["folds"].items():
        ledger = fold["ledger"]
        builder = fold["oracle"].builder
        for r in ledger.itertuples():
            home_state = builder.state.get(r.home_team)
            away_state = builder.state.get(r.away_team)
            elo_diff = (home_state.elo - away_state.elo) if home_state and away_state else None
            rows.append({
                "year": year, "match_id": r.match_id, "stage": r.stage,
                "home_team": r.home_team, "away_team": r.away_team,
                "actual_result": r.actual_result, "predicted_result": r.predicted_result,
                "correct": r.correct, "confidence": r.confidence,
                "home_goals": r.home_goals, "away_goals": r.away_goals,
                "total_goals": r.home_goals + r.away_goals,
                "elo_diff": elo_diff,
                "result_method": result_method.get(r.match_id),
                "is_knockout": stage_order.get(r.match_id, 1) > 1,
            })
    df = pd.DataFrame(rows)
    wrong = df[~df["correct"]]
    n_total, n_wrong = len(df), len(wrong)

    categories: dict[str, dict] = {}

    def add(name: str, mask_all: pd.Series, mask_wrong: pd.Series, note: str):
        n_pop = int(mask_all.sum())
        n_err = int(mask_wrong.sum())
        categories[name] = {
            "population": n_pop,
            "errors_in_population": n_err,
            "error_rate": round(n_err / n_pop, 4) if n_pop else None,
            "overall_error_rate": round(n_wrong / n_total, 4),
            "share_of_all_errors": round(n_err / n_wrong, 4) if n_wrong else None,
            "note": note,
        }

    # Strong favourite lost — model was >=65% confident and wrong
    m_all = df["confidence"] >= 0.65
    add("strong_favourite_lost", m_all, wrong["confidence"] >= 0.65,
        "Model gave >=65% to the predicted outcome, but was wrong.")

    # Draw predicted as a decisive win, or vice versa
    m_all = df["actual_result"] == "draw"
    add("draw_predicted_as_win", m_all, wrong["actual_result"] == "draw",
        "Match was actually a draw; model predicted a decisive winner.")
    m_all = df["predicted_result"] == "draw"
    add("win_predicted_as_draw", m_all, wrong["predicted_result"] == "draw",
        "Model predicted a draw; match actually had a winner.")

    # Underdog undervalued — actual winner had negative Elo diff (as favourite's side)
    # but model's probability for the ACTUAL outcome was low
    def actual_outcome_prob(row):
        # Requires re-deriving which probability corresponds to actual outcome;
        # approximated here via confidence-of-wrong-pick as a proxy already
        # captured in "strong_favourite_lost" above. This category instead
        # looks specifically at upsets by Elo gap.
        return None

    has_elo = df["elo_diff"].notna()
    home_favourite_lost = (df["elo_diff"] > 100) & (df["actual_result"] == "away_win")
    away_favourite_lost = (df["elo_diff"] < -100) & (df["actual_result"] == "home_win")
    upset_mask = has_elo & (home_favourite_lost | away_favourite_lost)
    upset_wrong = wrong.index.isin(df[upset_mask].index)
    add("elo_favourite_upset", upset_mask,
        pd.Series(upset_wrong, index=wrong.index) if len(wrong) else pd.Series(dtype=bool),
        "Elo gap >100 in one side's favour, but the underdog won outright — a "
        "genuine upset regardless of what the model predicted; flags whether "
        "the model still over-trusted Elo in these cases.")

    # Stage-specific
    add("knockout_stage_errors", df["is_knockout"], wrong["is_knockout"],
        "Errors specifically in knockout matches (higher stakes, single match, "
        "small sample per stage).")
    add("group_stage_errors", ~df["is_knockout"], ~wrong["is_knockout"],
        "Errors in group-stage matches.")

    # High/low scoring
    add("high_scoring_match_error", df["total_goals"] >= 4, wrong["total_goals"] >= 4,
        "Actual combined goals >= 4.")
    add("low_scoring_match_error", df["total_goals"] <= 1, wrong["total_goals"] <= 1,
        "Actual combined goals <= 1.")

    # Extra time / penalties
    et_mask = df["result_method"].isin(["Extra Time", "Penalties", "Draw (after Extra Time)"])
    add("extra_time_or_penalties", et_mask,
        wrong["result_method"].isin(["Extra Time", "Penalties", "Draw (after Extra Time)"])
        if len(wrong) else pd.Series(dtype=bool),
        "Match went to extra time or penalties — score-based features see a "
        "level match at 90 minutes; result depends on factors outside the "
        "model's inputs.")

    # ---- systematic vs random classification ----
    baseline_rate = n_wrong / n_total
    verdicts = {}
    for name, c in categories.items():
        if not c["population"] or c["error_rate"] is None:
            verdicts[name] = "insufficient_data"
            continue
        # A simple, transparent rule: a category is flagged systematic if its
        # error rate is at least 1.4x the overall baseline AND has enough
        # matches (>=15) for that gap to be more than noise.
        if c["population"] >= 15 and c["error_rate"] >= baseline_rate * 1.4:
            verdicts[name] = "systematic — error rate notably above baseline"
        elif c["population"] < 15:
            verdicts[name] = "too small a sample to call systematic"
        else:
            verdicts[name] = "consistent with baseline — not distinguishable from random"

    return {
        "n_total_matches": n_total, "n_wrong": n_wrong,
        "overall_error_rate": round(baseline_rate, 4),
        "categories": categories, "verdicts": verdicts,
        "per_match": df.to_dict("records"),
    }
