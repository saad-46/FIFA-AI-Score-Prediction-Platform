"""
Leakage-safe feature engineering for the canonical v2 World Cup corpus.

THE INVARIANT THIS MODULE ENFORCES
----------------------------------
Every feature for match M is computed from matches strictly BEFORE M in
chronological order. Nothing about M itself — its score, result, statistics,
attendance, or anything derived from them — may enter M's own feature row.

Mechanically this is guaranteed by a single-pass design: the corpus is walked in
date order, features for a match are emitted from accumulator state, and only
afterwards is that match folded into the accumulators. There is no vectorised
"compute over the whole frame then shift" step where an off-by-one could
silently leak the target.

Two operating modes, deliberately kept separate:

    WC2026_BACKTEST    accumulators are frozen at the end of 2022. Answers
                       "what would this model have predicted going into the
                       2026 tournament?" 2026 results are ground truth only.

    CURRENT_PRODUCTION accumulators absorb everything including 2026, for
                       predicting future tournaments.

Feature families are toggleable so the ablation harness can build strict
supersets (Experiment 1 ⊂ 2 ⊂ 3 ⊂ 4 ⊂ 5).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

CANON_DIR = Path(__file__).resolve().parents[2] / "data" / "canonical"

BASE_ELO = 1500.0
ELO_K = 40.0          # World-Cup matches only, so a single high-importance K
ELO_HOME_ADV = 65.0   # applied only when a side is an actual host nation

FORM_WINDOWS = (3, 5, 10)

FEATURE_GROUPS = ("strength", "form", "history", "context", "rolling_stats")


# ---------------------------------------------------------------------------
def load_canonical() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    matches = pd.read_csv(CANON_DIR / "canonical_matches.csv", encoding="utf-8-sig")
    teams = pd.read_csv(CANON_DIR / "canonical_teams.csv", encoding="utf-8-sig")
    stats = pd.read_csv(CANON_DIR / "canonical_match_stats.csv", encoding="utf-8-sig")

    matches["date"] = pd.to_datetime(matches["date"])
    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)

    # Decisive score: extra time where played, else full time. The corrupt
    # total_goals_* columns were dropped at build time and do not exist here.
    matches["home_goals"] = matches["home_score_et"].fillna(matches["home_score_ft"])
    matches["away_goals"] = matches["away_score_et"].fillna(matches["away_score_ft"])
    return matches, teams, stats


def result_label(home_goals: float, away_goals: float) -> int:
    """0 = away win, 1 = draw, 2 = home win (matches the existing pipeline)."""
    if home_goals > away_goals:
        return 2
    if home_goals < away_goals:
        return 0
    return 1


# ---------------------------------------------------------------------------
@dataclass
class TeamState:
    elo: float = BASE_ELO
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    clean_sheets: int = 0
    tournaments: set = field(default_factory=set)
    knockout_matches: int = 0
    last_date: pd.Timestamp | None = None
    recent: deque = field(default_factory=lambda: deque(maxlen=max(FORM_WINDOWS)))
    recent_stats: deque = field(default_factory=lambda: deque(maxlen=max(FORM_WINDOWS)))
    # Candidate-feature state (historical-optimization phase). Purely
    # additive: populated unconditionally in update() but only READ when a
    # candidate group is explicitly requested, so existing frozen bundles
    # (built with the original 5 groups) are byte-for-byte unaffected.
    elo_history: deque = field(default_factory=lambda: deque(maxlen=10))   # pre-match Elo each time
    elo_surprise: deque = field(default_factory=lambda: deque(maxlen=max(FORM_WINDOWS)))


class FeatureBuilder:
    """Single chronological pass: emit-then-update, so nothing can look ahead."""

    def __init__(self, stats: pd.DataFrame | None = None,
                 groups: tuple[str, ...] = FEATURE_GROUPS,
                 fifa_rank: dict[str, float] | None = None,
                 s5_elo: dict[str, float] | None = None):
        self.state: dict[str, TeamState] = defaultdict(TeamState)
        self.groups = set(groups)
        self.fifa_rank = fifa_rank or {}
        self.s5_elo = s5_elo or {}
        self.stats_by_match: dict[str, dict[str, dict]] = {}
        if stats is not None:
            for row in stats.to_dict("records"):
                self.stats_by_match.setdefault(row["match_id"], {})[row["team"]] = row

    # -- accumulator readers (pre-match only) -------------------------------
    def _form(self, st: TeamState, prefix: str) -> dict:
        out: dict[str, float] = {}
        hist = list(st.recent)
        for w in FORM_WINDOWS:
            recent = hist[-w:]
            n = len(recent)
            if n == 0:
                out[f"{prefix}_form_pts_{w}"] = np.nan
                out[f"{prefix}_form_gf_{w}"] = np.nan
                out[f"{prefix}_form_ga_{w}"] = np.nan
                out[f"{prefix}_form_gd_{w}"] = np.nan
                out[f"{prefix}_form_winrate_{w}"] = np.nan
                out[f"{prefix}_form_drawrate_{w}"] = np.nan
                out[f"{prefix}_form_cs_{w}"] = np.nan
                continue
            pts = sum(3 if r["res"] == "W" else 1 if r["res"] == "D" else 0 for r in recent)
            gf = sum(r["gf"] for r in recent)
            ga = sum(r["ga"] for r in recent)
            out[f"{prefix}_form_pts_{w}"] = pts / n
            out[f"{prefix}_form_gf_{w}"] = gf / n
            out[f"{prefix}_form_ga_{w}"] = ga / n
            out[f"{prefix}_form_gd_{w}"] = (gf - ga) / n
            out[f"{prefix}_form_winrate_{w}"] = sum(1 for r in recent if r["res"] == "W") / n
            out[f"{prefix}_form_drawrate_{w}"] = sum(1 for r in recent if r["res"] == "D") / n
            out[f"{prefix}_form_cs_{w}"] = sum(1 for r in recent if r["ga"] == 0) / n
        return out

    def _history(self, st: TeamState, prefix: str) -> dict:
        p = st.played
        return {
            f"{prefix}_wc_matches": p,
            f"{prefix}_wc_winrate": st.wins / p if p else np.nan,
            f"{prefix}_wc_drawrate": st.draws / p if p else np.nan,
            f"{prefix}_wc_gf_avg": st.goals_for / p if p else np.nan,
            f"{prefix}_wc_ga_avg": st.goals_against / p if p else np.nan,
            f"{prefix}_wc_cs_rate": st.clean_sheets / p if p else np.nan,
            f"{prefix}_wc_tournaments": len(st.tournaments),
            f"{prefix}_wc_knockout_matches": st.knockout_matches,
        }

    def _rolling_stats(self, st: TeamState, prefix: str) -> dict:
        """
        Lagged aggregates of S4 match statistics.

        These describe EARLIER matches only. The same match's statistics are
        never read here — that would be leakage, since possession/shots/cards
        are outcomes of the match being predicted.
        """
        fields = ("possession", "total_shots", "sot", "corners",
                  "fouls", "cards_yellow")
        out: dict[str, float] = {}
        hist = list(st.recent_stats)
        for w in (3, 5):
            recent = [r for r in hist[-w:] if r]
            for f in fields:
                vals = [r[f] for r in recent if r.get(f) is not None and not pd.isna(r.get(f))]
                out[f"{prefix}_avg_{f}_{w}"] = float(np.mean(vals)) if vals else np.nan
        return out

    # -- feature row --------------------------------------------------------
    def features_for(self, m: pd.Series) -> dict:
        home, away = m["home_team"], m["away_team"]
        hs, as_ = self.state[home], self.state[away]
        f: dict[str, float] = {}

        if "strength" in self.groups:
            home_adv = ELO_HOME_ADV if m["home_is_host"] else 0.0
            f["home_elo"] = hs.elo
            f["away_elo"] = as_.elo
            f["elo_diff"] = (hs.elo + home_adv) - as_.elo
            f["elo_abs_diff"] = abs(hs.elo - as_.elo)
            hr = self.fifa_rank.get(home, np.nan)
            ar = self.fifa_rank.get(away, np.nan)
            f["home_fifa_rank"] = hr
            f["away_fifa_rank"] = ar
            f["fifa_rank_diff"] = (ar - hr) if not (pd.isna(hr) or pd.isna(ar)) else np.nan
            he = self.s5_elo.get(home, np.nan)
            ae = self.s5_elo.get(away, np.nan)
            f["s5_elo_diff"] = (he - ae) if not (pd.isna(he) or pd.isna(ae)) else np.nan

        if "form" in self.groups:
            f.update(self._form(hs, "home"))
            f.update(self._form(as_, "away"))
            for w in FORM_WINDOWS:
                for k in ("pts", "gd", "gf", "ga"):
                    a, b = f.get(f"home_form_{k}_{w}"), f.get(f"away_form_{k}_{w}")
                    f[f"form_{k}_diff_{w}"] = (a - b) if not (pd.isna(a) or pd.isna(b)) else np.nan

        if "history" in self.groups:
            f.update(self._history(hs, "home"))
            f.update(self._history(as_, "away"))
            for k in ("wc_matches", "wc_winrate", "wc_gf_avg", "wc_ga_avg",
                      "wc_tournaments", "wc_knockout_matches"):
                a, b = f.get(f"home_{k}"), f.get(f"away_{k}")
                f[f"{k}_diff"] = (a - b) if not (pd.isna(a) or pd.isna(b)) else np.nan

        if "context" in self.groups:
            f["stage_order"] = float(m["stage_order"])
            f["is_knockout"] = 1.0 if m["is_knockout"] else 0.0
            f["neutral_venue"] = 1.0 if m["neutral_venue"] else 0.0
            f["home_is_host"] = 1.0 if m["home_is_host"] else 0.0
            f["away_is_host"] = 1.0 if m["away_is_host"] else 0.0
            for prefix, st in (("home", hs), ("away", as_)):
                rest = ((m["date"] - st.last_date).days
                        if st.last_date is not None else np.nan)
                f[f"{prefix}_rest_days"] = min(rest, 365) if not pd.isna(rest) else np.nan
            hr_, ar_ = f.get("home_rest_days"), f.get("away_rest_days")
            f["rest_days_diff"] = (hr_ - ar_) if not (pd.isna(hr_) or pd.isna(ar_)) else np.nan

        if "rolling_stats" in self.groups:
            f.update(self._rolling_stats(hs, "home"))
            f.update(self._rolling_stats(as_, "away"))

        # ---- candidate groups (historical-optimization phase) -------------
        if "form_compact" in self.groups:
            f.update(self._form_compact(hs, "home"))
            f.update(self._form_compact(as_, "away"))
            a, b = f.get("home_form_weighted_5"), f.get("away_form_weighted_5")
            f["form_weighted_diff_5"] = (a - b) if not (pd.isna(a) or pd.isna(b)) else np.nan

        if "elo_surprise_form" in self.groups:
            f.update(self._elo_surprise_form(hs, "home"))
            f.update(self._elo_surprise_form(as_, "away"))
            for w in (5, 10):
                a, b = f.get(f"home_elo_surprise_{w}"), f.get(f"away_elo_surprise_{w}")
                f[f"elo_surprise_diff_{w}"] = (a - b) if not (pd.isna(a) or pd.isna(b)) else np.nan

        if "elo_trend" in self.groups:
            for prefix, st in (("home", hs), ("away", as_)):
                hist = list(st.elo_history)
                f[f"{prefix}_elo_trend_5"] = (st.elo - hist[-5]) if len(hist) >= 5 else np.nan
            a, b = f.get("home_elo_trend_5"), f.get("away_elo_trend_5")
            f["elo_trend_diff_5"] = (a - b) if not (pd.isna(a) or pd.isna(b)) else np.nan

        return f

    def _form_compact(self, st: TeamState, prefix: str) -> dict:
        """
        Recency-weighted single-window form (last 5, linearly decaying
        weights 5,4,3,2,1 — most recent match weighted 5x the oldest) —
        a deliberately compact alternative to the existing 3-window x 7-stat
        raw-average 'form' group, which alone (E2) was found to HURT
        performance in the ablation phase. Tests whether the problem was too
        many noisy features, not the concept of recent form itself.
        """
        hist = list(st.recent)[-5:]
        n = len(hist)
        if n == 0:
            return {f"{prefix}_form_weighted_5": np.nan}
        weights = list(range(1, n + 1))  # oldest=1 ... most recent=n
        pts = [3 if r["res"] == "W" else 1 if r["res"] == "D" else 0 for r in hist]
        weighted = sum(w * p for w, p in zip(weights, pts)) / sum(weights)
        return {f"{prefix}_form_weighted_5": weighted}

    def _elo_surprise_form(self, st: TeamState, prefix: str) -> dict:
        """
        Opponent-adjusted form: mean(actual Elo-score - Elo-expected score)
        over the last N matches. Positive = team has been OUTPERFORMING what
        its Elo rating alone would predict against the opposition it actually
        faced (i.e. opponent strength is already baked in, unlike raw form).
        """
        hist = list(st.elo_surprise)
        out = {}
        for w in (5, 10):
            recent = hist[-w:]
            out[f"{prefix}_elo_surprise_{w}"] = float(np.mean(recent)) if recent else np.nan
        return out

    # -- accumulator writer -------------------------------------------------
    def update(self, m: pd.Series) -> None:
        home, away = m["home_team"], m["away_team"]
        hg, ag = m["home_goals"], m["away_goals"]
        if pd.isna(hg) or pd.isna(ag):
            return                                   # walkover: no result to learn from
        hs, as_ = self.state[home], self.state[away]

        exp_home = 1.0 / (1.0 + 10 ** (-((hs.elo + (ELO_HOME_ADV if m["home_is_host"] else 0.0))
                                         - as_.elo) / 400.0))
        score_home = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        margin = max(1.0, abs(hg - ag)) ** 0.5
        delta = ELO_K * margin * (score_home - exp_home)
        hs.elo += delta
        as_.elo -= delta

        # Pre-match Elo snapshot + Elo-based "surprise" (actual score minus
        # what the pre-match Elo gap alone predicted), for the elo_trend and
        # elo_surprise_form candidate groups. Recorded from the SAME
        # exp_home/score_home already computed above for the real Elo
        # update, so this is not a second, inconsistent notion of "expected".
        hs.elo_history.append(hs.elo)     # pre-update (pre-match) value
        as_.elo_history.append(as_.elo)
        hs.elo_surprise.append(score_home - exp_home)
        as_.elo_surprise.append((1.0 - score_home) - (1.0 - exp_home))

        for st, gf, ga, is_home in ((hs, hg, ag, True), (as_, ag, hg, False)):
            st.played += 1
            st.goals_for += int(gf)
            st.goals_against += int(ga)
            if gf > ga:
                st.wins += 1
                res = "W"
            elif gf == ga:
                st.draws += 1
                res = "D"
            else:
                st.losses += 1
                res = "L"
            if ga == 0:
                st.clean_sheets += 1
            st.tournaments.add(int(m["tournament_year"]) if "tournament_year" in m else int(m["year"]))
            if m["is_knockout"]:
                st.knockout_matches += 1
            st.last_date = m["date"]
            st.recent.append({"res": res, "gf": int(gf), "ga": int(ga)})

            team_name = home if is_home else away
            st.recent_stats.append(
                self.stats_by_match.get(m["match_id"], {}).get(team_name))


# ---------------------------------------------------------------------------
def build_dataset(matches: pd.DataFrame, teams: pd.DataFrame,
                  stats: pd.DataFrame | None = None,
                  groups: tuple[str, ...] = FEATURE_GROUPS,
                  freeze_after_year: int | None = None,
                  return_builder: bool = False):
    """
    Emit one leakage-safe feature row per match, in chronological order.

    ``freeze_after_year`` stops the accumulators absorbing results after the
    given year. Used for WC2026_BACKTEST (freeze at 2022) so that every 2026
    feature row reflects only pre-tournament knowledge — including 2026 matches
    not learning from earlier 2026 matches, which is what "predicting the
    tournament in advance" actually means.
    """
    wc26 = teams[teams["is_wc2026_team"].astype(str).str.lower().isin(["true", "1"])]
    fifa_rank = {r["team_name"]: r["fifa_ranking_pre_wc2026"] for _, r in wc26.iterrows()}
    s5_elo = {r["team_name"]: r["elo_rating_pre_wc2026"] for _, r in wc26.iterrows()}

    fb = FeatureBuilder(stats=stats, groups=groups, fifa_rank=fifa_rank, s5_elo=s5_elo)
    rows = []
    for _, m in matches.iterrows():
        feats = fb.features_for(m)
        feats.update({
            "match_id": m["match_id"],
            "date": m["date"],
            "year": int(m["year"]),
            "stage": m["stage"],
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "home_goals": m["home_goals"],
            "away_goals": m["away_goals"],
        })
        if not (pd.isna(m["home_goals"]) or pd.isna(m["away_goals"])):
            feats["target_result"] = result_label(m["home_goals"], m["away_goals"])
        else:
            feats["target_result"] = np.nan
        rows.append(feats)

        if freeze_after_year is None or int(m["year"]) <= freeze_after_year:
            fb.update(m)

    df = pd.DataFrame(rows)
    # The builder is returned so a tournament simulator can score hypothetical
    # matchups (knockout pairings that never actually occurred) from exactly the
    # same frozen accumulator state the backtest used.
    return (df, fb) if return_builder else df


def synthetic_match(home: str, away: str, *, stage: str, stage_order: int,
                    is_knockout: bool, date: pd.Timestamp,
                    home_is_host: bool = False, away_is_host: bool = False) -> pd.Series:
    """A minimal match row for scoring a hypothetical fixture."""
    return pd.Series({
        "home_team": home, "away_team": away, "stage": stage,
        "stage_order": stage_order, "is_knockout": is_knockout, "date": date,
        "home_is_host": home_is_host, "away_is_host": away_is_host,
        "neutral_venue": not (home_is_host or away_is_host),
        "match_id": None,
    })


def feature_columns(df: pd.DataFrame) -> list[str]:
    meta = {"match_id", "date", "year", "stage", "home_team", "away_team",
            "home_goals", "away_goals", "target_result"}
    return [c for c in df.columns if c not in meta]
