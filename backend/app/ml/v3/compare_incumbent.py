"""
Challenger versus incumbents on the same matches: the 104 games of the 2026
World Cup.

    python -m app.ml.v3.compare_incumbent

Two incumbents exist and they are compared separately, because they are in
different positions:

``v1.0.0``  The model production actually serves (PREDICTION_ENGINE=legacy,
            USE_V2_MODEL=false). Its training file contains the first 76
            matches of this tournament, so the comparison is reported three
            ways: all 104, the 76 it trained on, and the 28 it never saw. It
            is asked the way the API asks it, with its history cut at each
            match date.

``v2.1.0``  The frozen pre-tournament ledger shipped in
            app/ml/v2/artifacts/wc2026_pretournament_predictions.csv. It is read,
            never regenerated.

V3 is the pre-tournament bundle (nothing fitted on or after 2026-06-11), scored
two ways: ratings frozen on the eve of the tournament for every match, and
ratings updated after each real result (each prediction still uses only earlier
matches).

Results are after extra time with shoot-outs counted as draws, the definition
of the training corpus. 104 matches is a small sample; every difference is
reported with a paired bootstrap interval and should be read with it.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from app.ml.v3 import backtest, wc2026
from app.ml.v3.data import DATASET_TO_REGISTRY
from app.ml.v3.features import build_training_frame, finalise
from app.ml.v3.models import EloOrderedLogit
from app.ml.v3.inference import ART, get_service
from app.ml.v3.ratings import EloConfig, walk


def _score(p: np.ndarray, y: np.ndarray) -> dict:
    return {
        "log_loss": round(backtest.log_loss(p, y), 4), "brier": round(backtest.brier(p, y), 4),
        "rps": round(backtest.rps(p, y), 4), "accuracy": round(float((p.argmax(1) == y).mean()), 4),
        "mean_top_probability": round(float(p.max(1).mean()), 4),
        "draws_predicted": int((p.argmax(1) == 1).sum()),
    }


def _venue(r) -> int:
    return 1 if r.venue_country == r.team_a else (-1 if r.venue_country == r.team_b else 0)


def run() -> dict:
    pre = get_service("wc2026_pretournament")
    w = wc2026.wc2026_matches(pre.matches_all)
    y = np.where(w.goals_a > w.goals_b, 0, np.where(w.goals_a == w.goals_b, 1, 2))

    # ── V3, ratings frozen before the opening match ─────────────────────────
    frozen_frame = pre._frame([(r.team_a, r.team_b, _venue(r)) for r in w.itertuples()], 5)
    p_frozen = pre.forecaster.predict_proba(frozen_frame)

    # ── V3, ratings rolled forward through the tournament ───────────────────
    hist = pre.matches_all[pre.matches_all["date"] < wc2026.FORECAST_CUTOFF]
    cfg = EloConfig(**pre.manifest["rating_config"])
    eng, _ = walk(hist, cfg, collect=False)
    snaps = []
    for r in w.itertuples(index=False):
        s = finalise(pd.DataFrame([eng.snapshot(r.team_a, r.team_b, r.date, _venue(r), 5)]))
        s["venue"] = s["venue"].astype(int)
        s["tier"] = s["tier"].astype(int)
        snaps.append(s)
        eng.advance(r.team_a, r.team_b, int(r.goals_a), int(r.goals_b), r.date, int(r.venue), float(r.importance))
    rolling_frame = pd.concat(snaps, ignore_index=True)
    p_rolling = pre.forecaster.predict_proba(rolling_frame)

    # ── Plain Elo: same ratings, same cutoff, same two regimes ──────────────
    # The reference a rating-based model has to beat. Its three parameters are
    # fitted on exactly the matches the V3 bundle was fitted on.
    train_frame, _ = build_training_frame(hist, cfg)
    train_frame = train_frame[train_frame["date"] >= backtest.TRAIN_START]
    elo = EloOrderedLogit().fit(train_frame)
    p_elo_frozen, p_elo_rolling = elo.predict_proba(frozen_frame), elo.predict_proba(rolling_frame)

    out: dict = {
        "sample": "FIFA World Cup 2026, 104 matches",
        "outcome_definition": "result after extra time; shoot-outs count as draws",
        "outcome_counts": {"team_a_win": int((y == 0).sum()), "draw": int((y == 1).sum()), "team_b_win": int((y == 2).sum())},
        "challenger": pre.version,
        "information_cutoffs": {
            "v3_and_plain_elo_frozen": "model and ratings: matches before 2026-06-11",
            "v3_and_plain_elo_rolling": "model: matches before 2026-06-11; ratings: matches before each fixture",
            "v2_1_0_ledger": "model and match accumulators: end of 2022; team Elo / FIFA rank: undated, no recorded source",
            "v1_0_0": "model fitted on a file ending 2026-06-30 (includes 76 of these matches); history cut before each fixture",
        },
        "v3_frozen_ratings": _score(p_frozen, y),
        "v3_rolling_ratings": _score(p_rolling, y),
        "plain_elo_frozen_ratings": _score(p_elo_frozen, y),
        "plain_elo_rolling_ratings": _score(p_elo_rolling, y),
        "v3_minus_plain_elo_frozen": backtest.bootstrap_diff(p_frozen, p_elo_frozen, y),
        "v3_minus_plain_elo_rolling": backtest.bootstrap_diff(p_rolling, p_elo_rolling, y),
        "plain_elo_train_rows": int(len(train_frame)),
        "uniform": _score(np.full((len(y), 3), 1 / 3), y),
    }

    # ── v2.1.0 frozen ledger ────────────────────────────────────────────────
    from app.data import wc2026 as legacy_data
    canonical = {int(r["match_number"]): r for r in legacy_data.load_wc2026_matches()}
    ledger = legacy_data.load_frozen_predictions()
    by_pair: dict[frozenset, list[int]] = {}
    for i, r in enumerate(w.itertuples(index=False)):
        by_pair.setdefault(frozenset((r.team_a, r.team_b)), []).append(i)
    p_v2 = np.full((len(w), 3), np.nan)
    taken: set[int] = set()
    for no in sorted(canonical):
        h = DATASET_TO_REGISTRY.get(canonical[no]["home_team"], canonical[no]["home_team"])
        a = DATASET_TO_REGISTRY.get(canonical[no]["away_team"], canonical[no]["away_team"])
        i = next(k for k in by_pair[frozenset((h, a))] if k not in taken)
        taken.add(i)
        e = ledger[no]
        p = np.array([e["home_win_probability"], e["draw_probability"], e["away_win_probability"]], dtype=float)
        p_v2[i] = (p if w.team_a.iloc[i] == h else p[::-1]) / p.sum()
    assert not np.isnan(p_v2).any()
    out["v2_1_0_frozen_ledger"] = {
        **_score(p_v2, y),
        "ledger_model_version": sorted({e["model_version"] for e in ledger.values()}),
        "v3_frozen_minus_v2": backtest.bootstrap_diff(p_frozen, p_v2, y),
        "plain_elo_frozen_minus_v2": backtest.bootstrap_diff(p_elo_frozen, p_v2, y),
        "v3_rolling_minus_v2": backtest.bootstrap_diff(p_rolling, p_v2, y),
        "caveat": (
            "The ledger's team-strength inputs (canonical_teams.csv Elo and FIFA rank) are round numbers with no "
            "recorded source, first committed on 2026-07-04, after the group stage had finished. Its "
            "pre-tournament status cannot be verified from the repository."
        ),
    }

    # ── v1.0.0, the model production serves ─────────────────────────────────
    logging.disable(logging.CRITICAL)
    try:
        from app.ml.features.feature_engineering import compute_dynamic_elo
        from app.ml.models.predictor import get_predictor
        from app.ml.train import load_data
        frame = compute_dynamic_elo(load_data())
        predictor = get_predictor()
        trained_on: dict[frozenset, int] = {}
        for r in frame[frame.date >= wc2026.FORECAST_CUTOFF].itertuples():
            k = frozenset((r.home_team, r.away_team))
            trained_on[k] = trained_on.get(k, 0) + 1
        p_v1, p_v1_swapped, seen, used = [], [], [], {}
        for r in w.itertuples(index=False):
            k = frozenset((r.team_a, r.team_b))
            used[k] = used.get(k, 0) + 1
            seen.append(used[k] <= trained_on.get(k, 0))
            past = frame[frame.date < r.date]
            neutral = _venue(r) == 0
            o = predictor.predict(df=past, home_team=r.team_a, away_team=r.team_b,
                                  tournament="FIFA World Cup", neutral_venue=neutral)
            s = predictor.predict(df=past, home_team=r.team_b, away_team=r.team_a,
                                  tournament="FIFA World Cup", neutral_venue=neutral)
            p = np.array([o["home_win_probability"], o["draw_probability"], o["away_win_probability"]])
            q = np.array([s["away_win_probability"], s["draw_probability"], s["home_win_probability"]])
            p_v1.append(p / p.sum())
            p_v1_swapped.append(q / q.sum())
    finally:
        logging.disable(logging.NOTSET)
    p_v1, p_v1_swapped, seen = np.array(p_v1), np.array(p_v1_swapped), np.array(seen)
    v1: dict = {
        "model_version": predictor.model_version,
        "training_file_rows": int(len(frame)), "training_file_last_match": str(frame.date.max().date()),
        "world_cup_2026_matches_in_training_file": int(seen.sum()),
        "team_order_asymmetry": {
            "definition": "|P(A wins) with A listed first - P(A wins) with A listed second|, same fixture and venue flag",
            "mean": round(float(np.abs(p_v1[:, 0] - p_v1_swapped[:, 0]).mean()), 4),
            "max": round(float(np.abs(p_v1[:, 0] - p_v1_swapped[:, 0]).max()), 4),
        },
    }
    for label, mask in (("all_104", np.ones(len(y), bool)), ("the_76_it_trained_on", seen), ("the_28_it_never_saw", ~seen)):
        v1[label] = {"n": int(mask.sum()), "v1": _score(p_v1[mask], y[mask]), "v3_rolling": _score(p_rolling[mask], y[mask]),
                     "plain_elo_rolling": _score(p_elo_rolling[mask], y[mask]),
                     "v3_minus_v1": backtest.bootstrap_diff(p_rolling[mask], p_v1[mask], y[mask]),
                     "plain_elo_minus_v1": backtest.bootstrap_diff(p_elo_rolling[mask], p_v1[mask], y[mask])}
    out["v1_0_0_production"] = v1
    return out


def main() -> None:
    out = run()
    path = ART / "incumbent_comparison.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nwritten: {path}")


if __name__ == "__main__":
    main()
