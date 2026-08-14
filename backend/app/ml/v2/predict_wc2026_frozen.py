"""
Frozen WC2026 prediction (Phase 17-19) — generated strictly AFTER the model
in finalize_historical.py was frozen, using ONLY information available
before each 2026 match (accumulators frozen at end-2022, exactly as the
approved backtest bundle already does — the historical-optimization pass
changed which features/hyperparameters/calibration are used, not this
no-2026-leakage discipline).

TWO SEPARATE OUTPUTS (Phase 18), produced in this order and never revised
after the fact (Phase 19):

  1. PRE-TOURNAMENT PREDICTION — all 104 matches, generated from the frozen
     model with accumulators frozen at 2022. Written to disk FIRST.
  2. ACTUAL-BACKTEST COMPARISON — only after (1) is written, the real 2026
     results are read and compared. This file is written SECOND and never
     causes (1) to be edited, retrained, or regenerated.

If you are tempted to re-run this after looking at (2) because a particular
match "should" have gone the other way — don't. That is exactly the
leakage-by-hindsight the task prohibits (Phase 19). Any candidate change
belongs in run_experiments.py, tested against 2002-2022, logged to the
registry, and only released as a new version (e.g. v2.2.0) if it clears the
acceptance bar there — never by editing this file's output directly.

Usage:
    backend/venv/Scripts/python.exe -m app.ml.v2.predict_wc2026_frozen
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.poisson import PoissonEngine
from app.ml.v2.features import build_dataset, load_canonical, synthetic_match

ART = Path(__file__).resolve().parent / "artifacts"
FROZEN_ARTIFACT = ART / "model_v2_historical_optimized.pkl"
CLASS_NAMES = {0: "away_win", 1: "draw", 2: "home_win"}


def _load_frozen():
    if not FROZEN_ARTIFACT.exists():
        raise FileNotFoundError(
            f"{FROZEN_ARTIFACT} not found — run "
            "`python -m app.ml.v2.finalize_historical` first to freeze the model. "
            "This script refuses to run against an unfrozen configuration."
        )
    return joblib.load(FROZEN_ARTIFACT)


def generate_pre_tournament_predictions() -> pd.DataFrame:
    """Step 1: predict all 104 WC2026 matches, accumulators frozen at 2022."""
    bundle = _load_frozen()
    matches, teams, stats = load_canonical()

    _, builder = build_dataset(matches, teams, stats,
                               groups=tuple(bundle["feature_groups"]),
                               freeze_after_year=2022, return_builder=True)
    cols = bundle["feature_columns"]
    clf, hr, ar, cal = bundle["classifier"], bundle["home_regressor"], bundle["away_regressor"], bundle["calibrator"]
    poisson = PoissonEngine()

    wc26 = matches[(matches["year"] == 2026)].sort_values(
        ["stage_order", "match_number"] if "match_number" in matches.columns else ["stage_order", "date"])

    rows = []
    for m in wc26.itertuples():
        feats = builder.features_for(pd.Series({
            "home_team": m.home_team, "away_team": m.away_team, "stage": m.stage,
            "stage_order": m.stage_order, "is_knockout": m.is_knockout, "date": m.date,
            "home_is_host": m.home_is_host, "away_is_host": m.away_is_host,
            "neutral_venue": m.neutral_venue,
        }))
        x = np.array([[feats.get(c, np.nan) for c in cols]], dtype=np.float32)
        raw_proba = clf.predict_proba(x)
        proba = cal.transform(raw_proba)[0]
        home_xg = float(np.clip(hr.predict(x)[0], 0.0, None))
        away_xg = float(np.clip(ar.predict(x)[0], 0.0, None))
        poisson_result = poisson.predict(home_xg=home_xg, away_xg=away_xg)
        most_likely_score = poisson_result.most_likely_score

        rows.append({
            "match_number": getattr(m, "match_number", None),
            "date": m.date.strftime("%Y-%m-%d") if hasattr(m.date, "strftime") else str(m.date),
            "stage": m.stage,
            "home_team": m.home_team, "away_team": m.away_team,
            "predicted_winner": (m.home_team if proba[2] >= max(proba[0], proba[1])
                                 else m.away_team if proba[0] >= proba[1] else "Draw"),
            "home_win_probability": round(float(proba[2]), 4),
            "draw_probability": round(float(proba[1]), 4),
            "away_win_probability": round(float(proba[0]), 4),
            "predicted_home_goals": round(home_xg, 3),
            "predicted_away_goals": round(away_xg, 3),
            "most_likely_score": most_likely_score,
            "model_version": bundle["model_version"],
        })

    return pd.DataFrame(rows)


def compare_against_actual(pre_tournament: pd.DataFrame) -> dict:
    """Step 2: ONLY read after step 1 is saved. Never feeds back into it."""
    matches, _, _ = load_canonical()
    wc26 = matches[matches["year"] == 2026].set_index(["home_team", "away_team"])

    correct = 0
    scored = 0
    rows = []
    for r in pre_tournament.itertuples():
        key = (r.home_team, r.away_team)
        if key not in wc26.index:
            continue
        actual_row = wc26.loc[key]
        if isinstance(actual_row, pd.DataFrame):
            actual_row = actual_row.iloc[0]
        actual_winner = actual_row["winner_team"] if pd.notna(actual_row["winner_team"]) else "Draw"
        is_correct = r.predicted_winner == actual_winner
        scored += 1
        correct += int(is_correct)
        rows.append({"match": f"{r.home_team} v {r.away_team}", "stage": r.stage,
                    "predicted": r.predicted_winner, "actual": actual_winner,
                    "correct": is_correct})

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "n_matches_scored": scored,
        "accuracy": round(correct / scored, 4) if scored else None,
        "matches": rows,
        "note": "This file is a comparison ONLY. It was written after, and never "
               "caused a change to, wc2026_pretournament_predictions.csv.",
    }


def main() -> None:
    print("Generating PRE-TOURNAMENT predictions (frozen model, accumulators @ 2022)...")
    pre = generate_pre_tournament_predictions()
    pre_path = ART / "wc2026_pretournament_predictions.csv"
    pre.to_csv(pre_path, index=False)
    print(f"  {len(pre)} matches -> {pre_path}")
    print(f"  (this file is now considered FINAL for this model version — see module docstring)")

    print()
    print("Generating actual-results comparison (read-only follow-up, no model changes)...")
    comparison = compare_against_actual(pre)
    comp_path = ART / "wc2026_actual_comparison.json"
    comp_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  accuracy vs actual: {comparison['accuracy']} ({comparison['n_matches_scored']} matches)")
    print(f"  -> {comp_path}")


if __name__ == "__main__":
    main()
