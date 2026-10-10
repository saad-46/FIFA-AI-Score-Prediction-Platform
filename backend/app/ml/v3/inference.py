"""
Inference service: load one validated bundle, answer fixture questions.

Nothing is trained here. ``ForecastService.load`` reads a bundle written by
``app.ml.v3.train``, checks it against its manifest, and rebuilds team state by
running the same chronological rating walk used in training over the committed
corpus up to the bundle's information cutoff. Rebuilding rather than unpickling
the state means the features a prediction sees are produced by exactly the code
and data that produced the training features -- and a bundle can never be served
against a corpus it was not trained on, because the fingerprints must match.

If any check fails the service raises ``ModelUnavailable``. Callers are expected
to surface that as "prediction unavailable", never to substitute a guess.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from app.ml.v3.data import DATASET_TO_REGISTRY, SHOOTOUTS_CSV, competition_tier, corpus_fingerprint, file_sha256, load_matches
from app.ml.v3.features import FEATURE_NAMES, SCHEMA_VERSION, feature_matrix, finalise, mirror
from app.ml.v3.models import MAX_GOALS
from app.ml.v3.pipeline import Forecaster
from app.ml.v3.ratings import EloConfig, RatingEngine, walk
from app.ml.v3.tournament import MatchSampler

logger = logging.getLogger(__name__)
ART = Path(__file__).resolve().parent / "artifacts"


class ModelUnavailable(RuntimeError):
    """The bundle is missing, corrupt, or inconsistent with the data on disk."""


class UnknownTeam(ValueError):
    """A team with no match history: there is nothing to base a forecast on."""


# Labels for the explanation panel. Each is what the feature measures, phrased
# from team A's point of view.
READABLE = {
    "elo_diff_venue": "Elo rating gap (with home advantage)",
    "elo_diff": "Elo rating gap",
    "venue": "Venue (home / neutral / away)",
    "log_xg_ratio": "Attack vs defence strength balance",
    "log_xg_total": "Expected openness of the match",
    "form_pts_diff": "Recent points-per-match gap",
    "form_gd_diff": "Recent goal-difference gap",
    "momentum_diff": "Rating trend over the last 10 matches",
    "rest_days_diff": "Rest since last match",
    "activity_diff": "Matches played in the last year",
    "h2h_gd_shrunk": "Head-to-head record",
    "exp_min": "Depth of match history",
    "abs_elo_diff": "Size of the mismatch",
    "tier": "Competition level",
}


class ForecastService:
    def __init__(self, forecaster: Forecaster, manifest: dict, engine: RatingEngine,
                 matches_all: pd.DataFrame, cutoff: pd.Timestamp):
        self.forecaster = forecaster
        self.manifest = manifest
        self.engine = engine
        self.matches_all = matches_all
        self.cutoff = cutoff
        self.version = f"v{manifest['pipeline_version']}-{manifest['name']}"
        last = engine.last_match_date
        self.data_through = None if last is None else str(last.date())

    # ── loading ─────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, name: Optional[str] = None) -> "ForecastService":
        t0 = time.time()
        try:
            if name is None:
                name = json.loads((ART / "ACTIVE.json").read_text(encoding="utf-8"))["active"]
            manifest = json.loads((ART / f"manifest_{name}.json").read_text(encoding="utf-8"))
            path = ART / manifest["artifact"]
            if file_sha256(path) != manifest["artifact_sha256"]:
                raise ModelUnavailable(f"bundle {path.name} does not match its manifest checksum")
            if manifest["feature_schema"] != SCHEMA_VERSION or tuple(manifest["features"]) != tuple(FEATURE_NAMES):
                raise ModelUnavailable("bundle was trained with a different feature schema than this code")
            if manifest["corpus_fingerprint"] != corpus_fingerprint():
                raise ModelUnavailable("match corpus on disk differs from the one the bundle was trained on")
            # The shoot-out file feeds the penalty model and the bracket replay;
            # it has to be the one recorded at training time too.
            recorded = manifest.get("source", {}).get("files", {}).get(SHOOTOUTS_CSV.name, {}).get("sha256")
            if recorded and (not SHOOTOUTS_CSV.exists() or file_sha256(SHOOTOUTS_CSV) != recorded):
                raise ModelUnavailable("shoot-out file on disk differs from the one the bundle was trained on")
            forecaster: Forecaster = joblib.load(path)
        except ModelUnavailable:
            raise
        except Exception as exc:                       # missing file, bad JSON, unpickling error
            raise ModelUnavailable(f"could not load bundle {name!r}: {exc}") from exc

        matches = load_matches()
        cutoff = pd.Timestamp(manifest["information_cutoff"])
        history = matches[matches["date"] < cutoff]
        engine, _ = walk(history, EloConfig(**manifest["rating_config"]), collect=False)
        svc = cls(forecaster, manifest, engine, matches, cutoff)
        logger.info("v3 forecast service loaded: bundle=%s cutoff=%s data_through=%s matches=%d load_ms=%.0f",
                    name, cutoff.date(), svc.data_through, engine.matches_seen, (time.time() - t0) * 1000)
        return svc

    def advanced_to(self, cutoff: pd.Timestamp, label: str) -> "ForecastService":
        """
        The same fitted model with team state walked forward to a later date.

        Used for conditional forecasts ("given the real group stage, who wins the
        knockout rounds?"): ratings and form absorb the matches played before
        ``cutoff`` exactly as they would have in real time, while every fitted
        parameter stays as it was at the bundle's own cutoff. Moving backwards
        is refused -- a bundle must never be asked about dates it was trained on.
        """
        cutoff = pd.Timestamp(cutoff)
        if cutoff < self.cutoff:
            raise ValueError("cannot move a bundle's team state before its training cutoff")
        history = self.matches_all[self.matches_all["date"] < cutoff]
        engine, _ = walk(history, EloConfig(**self.manifest["rating_config"]), collect=False)
        svc = ForecastService(self.forecaster, self.manifest, engine, self.matches_all, cutoff)
        svc.version = f"{self.version}+{label}"
        return svc

    def history_frame(self) -> pd.DataFrame:
        """
        Matches this service's team state is built from, in the column names the
        API's head-to-head and insight code expects. ``neutral_venue`` is carried
        so "home record" statements are not computed from neutral-ground matches.
        """
        h = self.matches_all[self.matches_all["date"] < self.cutoff]
        return pd.DataFrame({
            "date": h["date"].to_numpy(), "home_team": h["team_a"].to_numpy(), "away_team": h["team_b"].to_numpy(),
            "home_score": h["goals_a"].to_numpy(), "away_score": h["goals_b"].to_numpy(),
            "tournament": h["tournament"].to_numpy(), "neutral_venue": (h["venue"] == 0).to_numpy(),
        })

    # ── features ────────────────────────────────────────────────────────────
    def known(self, team: str) -> bool:
        return self.engine.n.get(team, 0) > 0

    def resolve(self, label: str) -> Optional[str]:
        """
        A caller's team label -> the corpus name, or None if it is not a team
        there are matches for. Accepts the corpus name, a FIFA code, the
        upstream dataset's spelling, or the display name used by the 2026
        groups data ("Korea Republic"), ignoring case. Nothing is guessed: an
        unrecognised label resolves to None and the caller must refuse it.
        """
        from app.ml.v3 import wc2026
        label = label.strip()
        candidates = (label, wc2026.code_to_name().get(label.upper()), DATASET_TO_REGISTRY.get(label),
                      wc2026.display_name_to_name().get(label.casefold()))
        for c in candidates:
            if c and self.known(c):
                return c
        folded = label.casefold()
        for name in self.engine.n:
            if name.casefold() == folded and self.known(name):
                return name
        return None

    def _frame(self, fixtures: list[tuple[str, str, int]], tier: int) -> pd.DataFrame:
        for a, b, _ in fixtures:
            for t in (a, b):
                if not self.known(t):
                    raise UnknownTeam(f"no match history for {t!r}")
            if a == b:
                raise ValueError("a team cannot play itself")
        rows = [self.engine.snapshot(a, b, self.cutoff, int(v), int(tier)) for a, b, v in fixtures]
        frame = finalise(pd.DataFrame(rows))
        frame["venue"] = frame["venue"].astype(int)
        frame["tier"] = frame["tier"].astype(int)
        return frame

    # ── single fixture ──────────────────────────────────────────────────────
    def predict(self, team_a: str, team_b: str, venue: int = 0, tier: int = 5, top_n: int = 10) -> dict[str, Any]:
        """
        ``venue``: +1 team_a at home, 0 neutral, -1 team_b at home.
        Returns outcome probabilities, expected goals and the scoreline table.
        """
        t0 = time.time()
        frame = self._frame([(team_a, team_b, venue)], tier)
        mats, p, la, lb = self.forecaster.score_matrices(frame)
        m, p = mats[0], p[0]
        if not (np.isfinite(p).all() and abs(p.sum() - 1.0) < 1e-6 and (p >= 0).all()):
            raise ModelUnavailable("model produced invalid probabilities")
        n = MAX_GOALS + 1
        flat = [(float(m[i, j]), i, j) for i in range(n) for j in range(n)]
        flat.sort(reverse=True)
        top = [{"score": f"{i}-{j}", "probability": round(pr, 4)} for pr, i, j in flat[:top_n]]
        out = {
            "team_a": team_a, "team_b": team_b, "venue": int(venue), "tier": int(tier),
            "team_a_win_probability": float(p[0]), "draw_probability": float(p[1]),
            "team_b_win_probability": float(p[2]),
            "expected_goals_a": float(la[0]), "expected_goals_b": float(lb[0]),
            "most_likely_score": top[0]["score"], "top_scorelines": top,
            "elo_a": float(self.engine.elo[team_a]), "elo_b": float(self.engine.elo[team_b]),
            "model_version": self.version, "information_cutoff": str(self.cutoff.date()),
            "data_through": self.data_through,
            "explanation": self._explain(frame, int(np.argmax(p))),
        }
        logger.info("v3 predict %s v %s venue=%d tier=%d -> %.3f/%.3f/%.3f model=%s latency_ms=%.1f",
                    team_a, team_b, venue, tier, p[0], p[1], p[2], self.version, (time.time() - t0) * 1000)
        return out

    def _explain(self, frame: pd.DataFrame, cls_idx: int) -> dict[str, Any]:
        """
        Exact TreeSHAP contributions of the XGBoost component toward the most
        likely outcome, averaged over the two team orientations exactly as the
        prediction is. It explains one of the two blended models, and says so.
        """
        import xgboost as xgb
        X = feature_matrix(frame)
        booster = self.forecaster.xgb.clf.get_booster()
        c1 = booster.predict(xgb.DMatrix(X), pred_contribs=True)[0]            # (3, n_features + 1)
        c2 = booster.predict(xgb.DMatrix(mirror(X)), pred_contribs=True)[0]
        # In the mirrored orientation class k corresponds to class 2-k, and an
        # antisymmetric feature's value is negated, so its contribution keeps its meaning.
        contrib = 0.5 * (c1[cls_idx, :-1] + c2[2 - cls_idx, :-1])
        items = [{"feature": f, "readable_name": READABLE.get(f, f), "impact": float(v)}
                 for f, v in zip(FEATURE_NAMES, contrib)]
        pos = sorted((i for i in items if i["impact"] > 0), key=lambda i: -i["impact"])[:5]
        neg = sorted((i for i in items if i["impact"] < 0), key=lambda i: i["impact"])[:5]
        return {"top_positive_features": pos, "top_negative_features": neg,
                "method": "TreeSHAP on the XGBoost component of the blend"}

    def tensor(self, teams: list[str], hosts: tuple[str, ...] = (), tier: int = 5):
        """All pairwise scoreline distributions for ``teams`` (for ``simulate_fast``)."""
        from app.ml.v3.tournament_fast import build_tensor

        def batch(fixtures):
            frame = self._frame(fixtures, tier)
            mats, _, la, lb = self.forecaster.score_matrices(frame)
            return mats, la, lb, np.asarray(self.forecaster.p_shootout(frame["elo_diff"].to_numpy()))

        return build_tensor(list(teams), tuple(hosts), batch)

    # ── tournament support ──────────────────────────────────────────────────
    def sampler(self, tier: int = 5, teams: Optional[list[str]] = None) -> MatchSampler:
        """
        A ``MatchSampler`` over this model. Neutral-venue matchups for ``teams``
        are computed in one batch up front; anything else (a host playing at
        home) is computed on first use.
        """
        def provider(a: str, b: str, venue: int):
            frame = self._frame([(a, b, venue)], tier)
            mats, _, la, lb = self.forecaster.score_matrices(frame)
            return mats[0], float(la[0]), float(lb[0]), float(self.forecaster.p_shootout(frame["elo_diff"].iloc[0]))

        s = MatchSampler(provider)
        if teams:
            fixtures = [(a, b, 0) for i, a in enumerate(teams) for b in teams[i + 1:]]
            frame = self._frame(fixtures, tier)
            mats, _, la, lb = self.forecaster.score_matrices(frame)
            pp = self.forecaster.p_shootout(frame["elo_diff"].to_numpy())
            from app.ml.v3.tournament import Matchup
            for k, (a, b, _) in enumerate(fixtures):
                for (x, y, mat, l1, l2, pen) in ((a, b, mats[k], la[k], lb[k], pp[k]),
                                                 (b, a, mats[k].T, lb[k], la[k], 1.0 - pp[k])):
                    flat = np.asarray(mat, dtype=float).ravel()
                    cdf = np.cumsum(flat / flat.sum()); cdf[-1] = 1.0
                    s.cache[(x, y, 0)] = Matchup(cdf, float(l1), float(l2), float(pen))
        return s


_services: dict[str, ForecastService] = {}


def get_service(name: Optional[str] = None) -> ForecastService:
    """Process-wide cache of loaded bundles (loading costs a few seconds)."""
    key = name or "__active__"
    if key not in _services:
        _services[key] = ForecastService.load(name)
    return _services[key]


def reset_services() -> None:
    _services.clear()


def tier_for(tournament: Optional[str]) -> int:
    """Competition tier from the free-text tournament field of the public API."""
    if not tournament:
        return 5          # this product is a World Cup forecaster; that is its default context
    aliases = {"world cup": "FIFA World Cup", "fifa world cup": "FIFA World Cup", "uefa euro": "UEFA Euro",
               "copa america": "Copa América", "africa cup of nations": "African Cup of Nations",
               "concacaf gold cup": "Gold Cup", "fifa confederations cup": "Confederations Cup",
               "conmebol world cup qualifying": "FIFA World Cup qualification",
               "uefa world cup qualifying": "FIFA World Cup qualification"}
    return competition_tier(aliases.get(tournament.strip().lower(), tournament))
