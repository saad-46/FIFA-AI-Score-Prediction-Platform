"""
Walk-forward evaluation.

Every candidate is scored on the same folds and the same matches. A fold is
three consecutive, non-overlapping periods:

    train  ->  validation  ->  test
    fit        early stopping,   scored once
               calibration,
               ensemble weights

Nothing fitted ever sees its own test period, and the final test period (2026)
is not touched by any tuning decision: rating hyper-parameters, model
hyper-parameters, the calibration method and the ensemble weights are all chosen
on earlier folds.

Features need no refitting per fold. They come from one chronological rating
walk in which each match's features are read before its result is applied, so
they are out-of-sample by construction for every fold at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

EPS = 1e-12
TRAIN_START = "1990-01-01"


@dataclass(frozen=True)
class Fold:
    name: str
    val_start: str
    test_start: str
    test_end: str        # exclusive
    final: bool = False


# Development folds, then the untouched final test.
FOLDS: tuple[Fold, ...] = (
    Fold("2010-2013", "2006-01-01", "2010-01-01", "2014-01-01"),
    Fold("2014-2017", "2010-01-01", "2014-01-01", "2018-01-01"),
    Fold("2018-2021", "2014-01-01", "2018-01-01", "2022-01-01"),
    Fold("2022-2025", "2018-01-01", "2022-01-01", "2026-01-01"),
    Fold("2026-final", "2022-01-01", "2026-01-01", "2027-01-01", final=True),
)
DEV_FOLDS = tuple(f for f in FOLDS if not f.final)
FINAL_FOLD = FOLDS[-1]


def split(frame: pd.DataFrame, fold: Fold) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = frame["date"]
    train = frame[(d >= TRAIN_START) & (d < fold.val_start)]
    val = frame[(d >= fold.val_start) & (d < fold.test_start)]
    test = frame[(d >= fold.test_start) & (d < fold.test_end)]
    assert train["date"].max() < val["date"].min() < test["date"].min()
    return train, val, test


# ── Metrics ──────────────────────────────────────────────────────────────────

def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], EPS, None)).mean())


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(((p - np.eye(3)[y]) ** 2).sum(axis=1).mean())


def rps(p: np.ndarray, y: np.ndarray) -> float:
    """Ranked probability score for the ordered outcome A > D > B (lower is better)."""
    cp = np.cumsum(p, axis=1)[:, :2]
    cy = np.cumsum(np.eye(3)[y], axis=1)[:, :2]
    return float((((cp - cy) ** 2).sum(axis=1) / 2.0).mean())


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error of the top-class probability."""
    conf, pred = p.max(axis=1), p.argmax(axis=1)
    edges = np.linspace(0, 1, bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            out += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(out)


def classwise_ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for k in range(3):
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (p[:, k] > lo) & (p[:, k] <= hi)
            if m.any():
                tot += m.mean() * abs((y[m] == k).mean() - p[m, k].mean())
    return float(tot / 3)


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    """Per-class reliability: predicted vs observed frequency in each bin."""
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for k, name in enumerate(("A", "D", "B")):
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (p[:, k] > lo) & (p[:, k] <= hi)
            if m.sum() >= 20:
                rows.append({"class": name, "bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                             "predicted": round(float(p[m, k].mean()), 4),
                             "observed": round(float((y[m] == k).mean()), 4)})
    return rows


def class_report(p: np.ndarray, y: np.ndarray) -> dict:
    pred = p.argmax(axis=1)
    out = {}
    for k, name in enumerate(("A", "D", "B")):
        tp = int(((pred == k) & (y == k)).sum())
        fp = int(((pred == k) & (y != k)).sum())
        fn = int(((pred != k) & (y == k)).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        out[name] = {"precision": round(pr, 4), "recall": round(rc, 4),
                     "f1": round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0,
                     "support": int((y == k).sum()), "predicted": int((pred == k).sum())}
    return out


def score(p: np.ndarray, y: np.ndarray, goals: Optional[tuple] = None,
          actual_goals: Optional[tuple] = None) -> dict:
    rep = class_report(p, y)
    out = {
        "n": int(len(y)),
        "log_loss": round(log_loss(p, y), 5),
        "brier": round(brier(p, y), 5),
        "rps": round(rps(p, y), 5),
        "accuracy": round(float((p.argmax(axis=1) == y).mean()), 4),
        "draw_recall": rep["D"]["recall"],
        "draw_precision": rep["D"]["precision"],
        "mean_p_draw": round(float(p[:, 1].mean()), 4),
        "ece": round(ece(p, y), 4),
        "classwise_ece": round(classwise_ece(p, y), 4),
    }
    if goals is not None and actual_goals is not None:
        la, lb = goals
        ga, gb = actual_goals
        err = np.concatenate([la - ga, lb - gb])
        out["goal_mae"] = round(float(np.abs(err).mean()), 4)
        out["goal_rmse"] = round(float(np.sqrt((err ** 2).mean())), 4)
    return out


def bootstrap_diff(p_model: np.ndarray, p_ref: np.ndarray, y: np.ndarray,
                   n_boot: int = 2000, seed: int = 0) -> dict:
    """
    Paired bootstrap of (model log loss - reference log loss). Negative means the
    model is better; the interval says whether that is distinguishable from noise.
    """
    idx = np.arange(len(y))
    d = -np.log(np.clip(p_model[idx, y], EPS, None)) + np.log(np.clip(p_ref[idx, y], EPS, None))
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(n_boot, len(d)))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"mean_diff": round(float(d.mean()), 5), "ci95": [round(float(lo), 5), round(float(hi), 5)],
            "significant": bool(hi < 0 or lo > 0)}


def slices(frame: pd.DataFrame, p: np.ndarray, y: np.ndarray, min_n: int = 100) -> dict:
    """Log loss / accuracy within sub-populations of one test period."""
    out: dict[str, dict] = {}

    def add(label: str, mask: np.ndarray) -> None:
        if mask.sum() >= min_n:
            out[label] = {"n": int(mask.sum()), "log_loss": round(log_loss(p[mask], y[mask]), 4),
                          "rps": round(rps(p[mask], y[mask]), 4),
                          "accuracy": round(float((p[mask].argmax(1) == y[mask]).mean()), 4)}

    tier = frame["tier"].to_numpy()
    for t, name in ((5, "tier5_world_cup"), (4, "tier4_continental_finals"), (3, "tier3_qualifiers"),
                    (2, "tier2_minor_tournaments"), (1, "tier1_friendlies")):
        add(name, tier == t)
    v = frame["venue"].to_numpy()
    add("venue_home", v == 1)
    add("venue_neutral", v == 0)
    gap = frame["abs_elo_diff"].to_numpy()
    add("elo_gap_lt_100", gap < 100)
    add("elo_gap_100_300", (gap >= 100) & (gap < 300))
    add("elo_gap_ge_300", gap >= 300)
    add("sparse_history_lt_50_matches", frame["exp_min"].to_numpy() < np.log1p(50))
    return out
