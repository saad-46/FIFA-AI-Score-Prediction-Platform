"""
Feature registry and the shared feature builder.

Every model input is declared in ``FEATURE_REGISTRY`` with what it means, where
it comes from, when it becomes known and what leakage risk it carries. A column
that is not registered cannot be fed to a model: ``feature_matrix`` selects by
registry name only, and the test-suite asserts the registry and the engine's
snapshot agree.

All features come from ``RatingEngine.snapshot`` -- state as it stood before the
match. Nothing here reads a score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.v3.ratings import EloConfig, RatingEngine, walk

SCHEMA_VERSION = "v3-features-1"


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    definition: str
    source: str
    available: str           # when the value is known relative to kick-off
    missing_policy: str
    leakage_risk: str
    antisymmetric: bool      # True: negates when the two teams are swapped


_PRE = "before kick-off (uses matches strictly earlier in the chronological walk)"

FEATURE_REGISTRY: tuple[FeatureSpec, ...] = (
    FeatureSpec("elo_diff_venue", "Elo(A) - Elo(B) + home advantage x venue", "RatingEngine Elo", _PRE,
                "new team starts at 1500", "none: rating is read before the update", True),
    FeatureSpec("elo_diff", "Elo(A) - Elo(B), no venue term", "RatingEngine Elo", _PRE,
                "new team starts at 1500", "none", True),
    FeatureSpec("venue", "+1 A at home, 0 neutral, -1 B at home", "fixture metadata", "known when the fixture is set",
                "never missing", "none: fixture property", True),
    FeatureSpec("log_xg_ratio", "log(expected goals A / expected goals B) from online Poisson", "RatingEngine attack/defence", _PRE,
                "new team has attack=defence=0", "none", True),
    FeatureSpec("log_xg_total", "log(expected goals A + B)", "RatingEngine attack/defence", _PRE,
                "league-average for new teams", "none", False),
    FeatureSpec("form_pts_diff", "exp-weighted points per match, A - B (half-life EloConfig.form_halflife)", "RatingEngine form", _PRE,
                "prior 1.35 pts/match", "none", True),
    FeatureSpec("form_gd_diff", "exp-weighted goal difference per match, A - B", "RatingEngine form", _PRE,
                "prior 0", "none", True),
    FeatureSpec("momentum_diff", "Elo change over each team's last 10 matches, A - B", "RatingEngine Elo history", _PRE,
                "0 with no history", "none", True),
    FeatureSpec("rest_days_diff", "days since last match (capped 365), A - B", "match dates", _PRE,
                "365 when no previous match", "none", True),
    FeatureSpec("activity_diff", "matches played in the previous 365 days, A - B", "match dates", _PRE,
                "0", "none", True),
    FeatureSpec("h2h_gd_shrunk", "past head-to-head goal difference / (meetings + 4)", "RatingEngine h2h", _PRE,
                "0 with no meetings", "none: only earlier meetings", True),
    FeatureSpec("exp_min", "min(log1p matches played A, B): how well-rated the weaker-known side is", "match counts", _PRE,
                "0", "none", False),
    FeatureSpec("abs_elo_diff", "|elo_diff_venue|: mismatch size (drives the draw rate)", "RatingEngine Elo", _PRE,
                "0", "none", False),
    FeatureSpec("tier", "competition tier 1 (friendly) .. 5 (World Cup finals)", "fixture metadata", "known when the fixture is set",
                "never missing", "none", False),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURE_REGISTRY)
ANTISYMMETRIC = tuple(f.name for f in FEATURE_REGISTRY if f.antisymmetric)

# Columns that must never appear in a model matrix.
FORBIDDEN_INPUTS = frozenset({
    "goals_a", "goals_b", "result", "shootout_winner", "winner", "margin",
    "home_score", "away_score", "y", "target",
})


def finalise(snap: pd.DataFrame) -> pd.DataFrame:
    """Derive the registry columns that are functions of raw snapshot columns."""
    out = snap.copy()
    out["exp_min"] = np.minimum(out["log_matches_a"], out["log_matches_b"])
    out["abs_elo_diff"] = out["elo_diff_venue"].abs()
    return out


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Select exactly the registered model inputs, in registry order."""
    missing = [c for c in FEATURE_NAMES if c not in frame.columns]
    if missing:
        raise KeyError(f"feature frame is missing registered features: {missing}")
    leaked = FORBIDDEN_INPUTS.intersection(FEATURE_NAMES)
    if leaked:  # pragma: no cover - guards future edits to the registry
        raise AssertionError(f"registry contains forbidden inputs: {sorted(leaked)}")
    return frame.loc[:, list(FEATURE_NAMES)].astype(float)


def mirror(X: pd.DataFrame) -> pd.DataFrame:
    """The same fixtures with the two teams swapped (A<->B, venue negated)."""
    M = X.copy()
    for c in ANTISYMMETRIC:
        M[c] = -M[c]
    return M


def build_training_frame(matches: pd.DataFrame, cfg: EloConfig | None = None) -> tuple[pd.DataFrame, RatingEngine]:
    """
    One chronological walk -> (matches joined with their pre-match features, the
    engine in its final state). The engine is what inference snapshots from.
    """
    eng, snap = walk(matches, cfg, collect=True)
    base = matches.reset_index(drop=True)
    feats = finalise(snap).reset_index(drop=True)
    # `venue` and `tier` exist on both sides with identical values; keep one copy
    # so a column name never resolves to two columns.
    base = base.drop(columns=[c for c in feats.columns if c in base.columns])
    frame = pd.concat([base, feats], axis=1)
    frame["venue"] = frame["venue"].astype(int)
    frame["tier"] = frame["tier"].astype(int)
    return frame, eng


def fixture_features(eng: RatingEngine, team_a: str, team_b: str, date: pd.Timestamp,
                     venue: int, tier: int) -> pd.DataFrame:
    """Features for one not-yet-played fixture, from the engine's current state."""
    snap = pd.DataFrame([eng.snapshot(team_a, team_b, date, venue, tier)])
    return finalise(snap)
