"""
Rules-driven Monte Carlo tournament engine.

The match model answers "what is the scoreline distribution for A v B at this
venue?". This module answers a different question -- "given those
distributions, how often does each team reach each round?" -- by playing the
whole competition many times under its actual rules.

It knows nothing about any particular team. A tournament is described entirely
by a ``TournamentFormat`` (groups, fixtures, bracket wiring, tie-break rules);
the 2026 World Cup is one instance built by ``wc2026_format()`` from the
committed schedule, bracket graph and Annex C table.

Rules implemented for 2026 (48 teams, 12 groups of four, 104 matches)
---------------------------------------------------------------------
* Group ranking: points; then, among the teams level on points, head-to-head
  points, head-to-head goal difference, head-to-head goals (re-applied to any
  subset still level); then overall goal difference and overall goals. FIFA's
  next criteria are fair-play points and the FIFA ranking, neither of which is
  available here, so a remaining tie is settled by a random draw. That is a
  stated simplification and it is rare: it needs teams level on all six
  criteria above.
* Third-placed teams: ranked across groups on points, goal difference, goals
  (then the same random draw); the best eight qualify.
* Round of 32: the official slot map (1A v 3C/E/F/H/I, 2A v 2B, ...). Which
  third-placed team meets which group winner is read from Annex C of the
  regulations -- all 495 combinations -- not approximated.
* Knockout ties: 90 minutes; if level, extra time; if still level, penalties.
  Nobody advances on a draw.

Fixed results
-------------
``fixed`` maps a *match number* to a known result, for conditional forecasts
("as of the end of the group stage"). It is keyed by match number rather than
by the pair of teams on purpose: the previous simulator keyed by team pair, so
a group-stage result was silently reused whenever the same two teams met again
in a knockout round.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from app.ml.v3.models import MAX_GOALS

_CANON = Path(__file__).resolve().parents[2] / "data" / "canonical"
STAGES = ("group", "r32", "r16", "qf", "sf", "third_place", "final", "winner")
EXTRA_TIME_FRACTION = 1.0 / 3.0     # 30 minutes of extra time against 90 of normal time


@dataclass(frozen=True)
class GroupFixture:
    match_number: int
    group: str
    team_a: str
    team_b: str
    venue_country: Optional[str] = None


@dataclass
class TournamentFormat:
    name: str
    year: int
    groups: dict[str, list[str]]
    group_fixtures: list[GroupFixture]
    # Round-of-32 slots: match number -> (slot_a, slot_b); a slot is ("W", "A"),
    # ("R", "A") or ("T", "A") = the third-placed team assigned to winner A.
    r32_slots: dict[int, tuple[tuple[str, str], tuple[str, str]]]
    # Later knockout matches: match number -> ((kind, source_match), (kind, source_match))
    knockout_links: dict[int, tuple[tuple[str, int], tuple[str, int]]]
    third_place_allocation: dict[str, dict[str, str]]
    n_third_qualifiers: int
    stage_of: dict[int, str]
    venue_country: dict[int, str] = field(default_factory=dict)
    final_match: int = 104
    third_place_match: Optional[int] = 103

    @property
    def teams(self) -> list[str]:
        return [t for g in self.groups.values() for t in g]

    def validate(self) -> None:
        teams = self.teams
        if len(set(teams)) != len(teams):
            raise ValueError("a team appears in more than one group")
        per_group = {g: 0 for g in self.groups}
        seen = set()
        for f in self.group_fixtures:
            if f.team_a not in self.groups[f.group] or f.team_b not in self.groups[f.group]:
                raise ValueError(f"fixture {f.match_number}: team not in group {f.group}")
            pair = frozenset((f.team_a, f.team_b))
            if pair in seen:
                raise ValueError(f"fixture {f.match_number}: pair plays twice")
            seen.add(pair)
            per_group[f.group] += 1
        for g, ts in self.groups.items():
            expect = len(ts) * (len(ts) - 1) // 2
            if per_group[g] != expect:
                raise ValueError(f"group {g}: {per_group[g]} fixtures, expected {expect}")
        n_ko = len(self.r32_slots) + len(self.knockout_links)
        if len(self.group_fixtures) + n_ko != 104 and self.year == 2026:
            raise ValueError(f"2026 format must have 104 matches, got {len(self.group_fixtures) + n_ko}")


# ── Group ranking ────────────────────────────────────────────────────────────

def _table(teams, results):
    pts = {t: 0 for t in teams}
    gd = {t: 0 for t in teams}
    gf = {t: 0 for t in teams}
    members = set(teams)
    for a, b, ga, gb in results:
        if a in members and b in members:
            gf[a] += ga; gf[b] += gb
            gd[a] += ga - gb; gd[b] += gb - ga
            if ga > gb:
                pts[a] += 3
            elif gb > ga:
                pts[b] += 3
            else:
                pts[a] += 1; pts[b] += 1
    return pts, gd, gf


def _break_tie(tied: list[str], results, overall_gd, overall_gf, rng) -> list[str]:
    """Order teams level on points: head-to-head first, then overall, then lot."""
    if len(tied) == 1:
        return list(tied)
    hp, hgd, hgf = _table(tied, results)
    buckets: dict[tuple, list[str]] = {}
    for t in tied:
        buckets.setdefault((hp[t], hgd[t], hgf[t]), []).append(t)
    if len(buckets) > 1:
        out: list[str] = []
        for key in sorted(buckets, reverse=True):
            # Head-to-head is re-applied among only the teams still level.
            out.extend(_break_tie(buckets[key], results, overall_gd, overall_gf, rng))
        return out
    # Head-to-head cannot separate them: overall goal difference, then goals.
    ob: dict[tuple, list[str]] = {}
    for t in tied:
        ob.setdefault((overall_gd[t], overall_gf[t]), []).append(t)
    out = []
    for key in sorted(ob, reverse=True):
        grp = ob[key]
        if len(grp) > 1:
            grp = list(grp)
            rng.shuffle(grp)      # stands in for fair-play points / FIFA ranking
        out.extend(grp)
    return out


def rank_group(teams: list[str], results: list[tuple[str, str, int, int]], rng) -> tuple[list[str], dict]:
    """Final order of one group plus each team's (points, goal difference, goals)."""
    pts, gd, gf = _table(teams, results)
    by_pts: dict[int, list[str]] = {}
    for t in teams:
        by_pts.setdefault(pts[t], []).append(t)
    order: list[str] = []
    for p in sorted(by_pts, reverse=True):
        order.extend(_break_tie(by_pts[p], results, gd, gf, rng))
    return order, {t: (pts[t], gd[t], gf[t]) for t in teams}


def rank_third_placed(thirds: list[tuple[str, str, tuple[int, int, int]]], rng) -> list[tuple[str, str]]:
    """``thirds``: (group, team, (pts, gd, gf)). Best first; exact ties by lot."""
    keyed = [(stats, rng.random(), g, t) for g, t, stats in thirds]
    keyed.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(g, t) for _, _, g, t in keyed]


# ── Match sampling ───────────────────────────────────────────────────────────

@dataclass
class Matchup:
    """Everything the engine needs for one ordered fixture at one venue state."""
    cdf: np.ndarray          # cumulative flattened score matrix, 90 minutes
    lam_a: float
    lam_b: float
    p_pens_a: float          # P(team_a wins a shoot-out)


class MatchSampler:
    """
    Lazily builds and caches ``Matchup`` objects. ``provider(a, b, venue)`` must
    return ``(score_matrix, lam_a, lam_b, p_pens_a)`` for team a listed first.
    """

    def __init__(self, provider: Callable[[str, str, int], tuple[np.ndarray, float, float, float]]):
        self.provider = provider
        self.cache: dict[tuple[str, str, int], Matchup] = {}

    def get(self, a: str, b: str, venue: int) -> Matchup:
        key = (a, b, venue)
        m = self.cache.get(key)
        if m is None:
            mat, la, lb, pp = self.provider(a, b, venue)
            flat = np.asarray(mat, dtype=float).ravel()
            cdf = np.cumsum(flat / flat.sum())
            cdf[-1] = 1.0
            m = Matchup(cdf, float(la), float(lb), float(pp))
            self.cache[key] = m
        return m


def _venue_for(a: str, b: str, country: Optional[str]) -> int:
    if country is not None:
        if a == country:
            return 1
        if b == country:
            return -1
    return 0


_N = MAX_GOALS + 1


def _score(cdf: np.ndarray, u: float) -> tuple[int, int]:
    i = int(np.searchsorted(cdf, u, side="right"))
    if i >= _N * _N:
        i = _N * _N - 1
    return i // _N, i % _N


def play_knockout(m: Matchup, rng) -> tuple[int, int, bool, str]:
    """
    One knockout tie. Returns (goals_a, goals_b, a_advances, method) where the
    goals include extra time and method is "90", "aet" or "pens".
    """
    ga, gb = _score(m.cdf, rng.random())
    if ga != gb:
        return ga, gb, ga > gb, "90"
    ea = rng.poisson(m.lam_a * EXTRA_TIME_FRACTION)
    eb = rng.poisson(m.lam_b * EXTRA_TIME_FRACTION)
    ga, gb = ga + ea, gb + eb
    if ga != gb:
        return ga, gb, ga > gb, "aet"
    return ga, gb, rng.random() < m.p_pens_a, "pens"


# ── Simulation ───────────────────────────────────────────────────────────────

@dataclass
class FixedResult:
    """A known result for one match number. ``advances`` is required for a
    knockout tie that finished level (who won on penalties)."""
    goals_a: int
    goals_b: int
    advances: Optional[str] = None


def simulate(fmt: TournamentFormat, sampler: MatchSampler, n_sims: int = 10000, seed: int = 20260611,
             fixed: Optional[dict[int, FixedResult]] = None, n_batches: int = 10,
             return_paths: bool = False) -> dict[str, Any]:
    """
    Play the tournament ``n_sims`` times.

    Reproducible: the same (format, sampler, n_sims, seed, fixed) always yields
    the same output. Results are accumulated in ``n_batches`` equal batches so
    the spread between batches can be reported as a convergence diagnostic.
    """
    fmt.validate()
    fixed = fixed or {}
    rng = np.random.default_rng(seed)
    teams = fmt.teams
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    counts = np.zeros((n_batches, T, len(STAGES)), dtype=np.int64)
    S = {s: i for i, s in enumerate(STAGES)}
    pts_sum = np.zeros(T); gf_sum = np.zeros(T); ga_sum = np.zeros(T)
    group_pos = np.zeros((T, 4), dtype=np.int64)
    method_counts = {"90": 0, "aet": 0, "pens": 0}
    paths: list[dict] = []

    # Group-stage scores are sampled for all simulations at once per fixture.
    gs_scores: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for f in fmt.group_fixtures:
        if f.match_number in fixed:
            fr = fixed[f.match_number]
            gs_scores[f.match_number] = (np.full(n_sims, fr.goals_a), np.full(n_sims, fr.goals_b))
            continue
        m = sampler.get(f.team_a, f.team_b, _venue_for(f.team_a, f.team_b, f.venue_country))
        cell = np.minimum(np.searchsorted(m.cdf, rng.random(n_sims), side="right"), _N * _N - 1)
        gs_scores[f.match_number] = (cell // _N, cell % _N)

    fixtures_by_group: dict[str, list[GroupFixture]] = {g: [] for g in fmt.groups}
    for f in fmt.group_fixtures:
        fixtures_by_group[f.group].append(f)
    r32_order = sorted(fmt.r32_slots)
    ko_order = sorted(fmt.knockout_links)
    batch_of = (np.arange(n_sims) * n_batches // n_sims)

    for s in range(n_sims):
        b = batch_of[s]
        winner: dict[str, str] = {}
        runner: dict[str, str] = {}
        thirds: list[tuple[str, str, tuple[int, int, int]]] = []
        for g, gteams in fmt.groups.items():
            res = [(f.team_a, f.team_b, int(gs_scores[f.match_number][0][s]), int(gs_scores[f.match_number][1][s]))
                   for f in fixtures_by_group[g]]
            order, stats = rank_group(gteams, res, rng)
            winner[g], runner[g] = order[0], order[1]
            if len(order) > 2:
                thirds.append((g, order[2], stats[order[2]]))
            for pos, t in enumerate(order):
                i = idx[t]
                group_pos[i, pos] += 1
                pts_sum[i] += stats[t][0]
            for a, bb, ga, gb in res:
                gf_sum[idx[a]] += ga; ga_sum[idx[a]] += gb
                gf_sum[idx[bb]] += gb; ga_sum[idx[bb]] += ga
        counts[b, :, S["group"]] += 1

        best = rank_third_placed(thirds, rng)[: fmt.n_third_qualifiers]
        third_of_group = dict(best)
        key = "".join(sorted(third_of_group))
        alloc = fmt.third_place_allocation[key]      # winner group -> third-placed group

        def resolve(slot: tuple[str, str]) -> str:
            kind, g = slot
            if kind == "W":
                return winner[g]
            if kind == "R":
                return runner[g]
            return third_of_group[alloc[g]]

        match_winner: dict[int, str] = {}
        match_loser: dict[int, str] = {}
        path: dict[int, tuple] = {}

        def play(no: int, a: str, bb: str) -> None:
            stage = fmt.stage_of[no]
            counts[b, idx[a], S[stage]] += 1
            counts[b, idx[bb], S[stage]] += 1
            fr = fixed.get(no)
            if fr is not None:
                if fr.goals_a != fr.goals_b:
                    a_adv = fr.goals_a > fr.goals_b
                elif fr.advances in (a, bb):
                    a_adv = fr.advances == a
                else:
                    raise ValueError(f"match {no}: level fixed result needs `advances`")
                ga, gb, method = fr.goals_a, fr.goals_b, "fixed"
            else:
                m = sampler.get(a, bb, _venue_for(a, bb, fmt.venue_country.get(no)))
                ga, gb, a_adv, method = play_knockout(m, rng)
                method_counts[method] += 1
            match_winner[no], match_loser[no] = (a, bb) if a_adv else (bb, a)
            if return_paths:
                path[no] = (a, bb, ga, gb, match_winner[no], method)

        for no in r32_order:
            sa, sb = fmt.r32_slots[no]
            play(no, resolve(sa), resolve(sb))
        for no in ko_order:
            (ka, na), (kb, nb) = fmt.knockout_links[no]
            a = match_winner[na] if ka == "winner_of" else match_loser[na]
            bb = match_winner[nb] if kb == "winner_of" else match_loser[nb]
            play(no, a, bb)
        counts[b, idx[match_winner[fmt.final_match]], S["winner"]] += 1
        if return_paths:
            paths.append({"qualified_thirds": key, "matches": path, "champion": match_winner[fmt.final_match]})

    total = counts.sum(axis=0)
    per_batch = n_sims / n_batches
    batch_win = counts[:, :, S["winner"]] / per_batch
    out_teams = {}
    for t, i in idx.items():
        p = {s: float(total[i, S[s]] / n_sims) for s in STAGES}
        pw = p["winner"]
        out_teams[t] = {
            **p,
            "winner_se": float(math.sqrt(max(pw * (1 - pw), 0.0) / n_sims)),
            "winner_batch_sd": float(batch_win[:, i].std(ddof=1)) if n_batches > 1 else 0.0,
            "expected_group_points": float(pts_sum[i] / n_sims),
            "expected_group_goals_for": float(gf_sum[i] / n_sims),
            "expected_group_goals_against": float(ga_sum[i] / n_sims),
            "group_position_probabilities": [float(x / n_sims) for x in group_pos[i]],
        }
    champ_sum = sum(v["winner"] for v in out_teams.values())
    max_se = max(v["winner_se"] for v in out_teams.values())
    result = {
        "format": fmt.name, "n_simulations": n_sims, "seed": seed, "n_batches": n_batches,
        "fixed_matches": sorted(fixed),
        "teams": out_teams,
        "diagnostics": {
            "champion_probability_sum": champ_sum,
            "max_champion_standard_error": max_se,
            "max_champion_batch_sd": max(v["winner_batch_sd"] for v in out_teams.values()),
            "knockout_resolution": method_counts,
        },
    }
    if return_paths:
        result["paths"] = paths
    return result


# ── 2026 format ──────────────────────────────────────────────────────────────

# Official Round-of-32 slot map (FIFA World Cup 2026 match schedule). A deterministic
# test replays the real group stage through this map and Annex C and checks it
# reproduces all sixteen real pairings.
R32_SLOTS_2026: dict[int, tuple[tuple[str, str], tuple[str, str]]] = {
    73: (("R", "A"), ("R", "B")),
    74: (("W", "E"), ("T", "E")),
    75: (("W", "F"), ("R", "C")),
    76: (("W", "C"), ("R", "F")),
    77: (("W", "I"), ("T", "I")),
    78: (("R", "E"), ("R", "I")),
    79: (("W", "A"), ("T", "A")),
    80: (("W", "L"), ("T", "L")),
    81: (("W", "D"), ("T", "D")),
    82: (("W", "G"), ("T", "G")),
    83: (("R", "K"), ("R", "L")),
    84: (("W", "H"), ("R", "J")),
    85: (("W", "B"), ("T", "B")),
    86: (("W", "J"), ("R", "H")),
    87: (("W", "K"), ("T", "K")),
    88: (("R", "D"), ("R", "G")),
}

# Official bracket wiring after the Round of 32 (FIFA World Cup 2026 match schedule).
KNOCKOUT_LINKS_2026: dict[int, tuple[tuple[str, int], tuple[str, int]]] = {
    89: (("winner_of", 74), ("winner_of", 77)),
    90: (("winner_of", 73), ("winner_of", 75)),
    91: (("winner_of", 76), ("winner_of", 78)),
    92: (("winner_of", 79), ("winner_of", 80)),
    93: (("winner_of", 83), ("winner_of", 84)),
    94: (("winner_of", 81), ("winner_of", 82)),
    95: (("winner_of", 86), ("winner_of", 88)),
    96: (("winner_of", 85), ("winner_of", 87)),
    97: (("winner_of", 89), ("winner_of", 90)),
    98: (("winner_of", 93), ("winner_of", 94)),
    99: (("winner_of", 91), ("winner_of", 92)),
    100: (("winner_of", 95), ("winner_of", 96)),
    101: (("winner_of", 97), ("winner_of", 98)),
    102: (("winner_of", 99), ("winner_of", 100)),
    103: (("loser_of", 101), ("loser_of", 102)),
    104: (("winner_of", 101), ("winner_of", 102)),
}


def _stage_2026(no: int) -> str:
    if no <= 88:
        return "r32"
    if no <= 96:
        return "r16"
    if no <= 100:
        return "qf"
    if no <= 102:
        return "sf"
    return "third_place" if no == 103 else "final"


def wc2026_format(groups: dict[str, list[str]], group_fixtures: list[GroupFixture],
                  venue_country: dict[int, str]) -> TournamentFormat:
    """Assemble the 2026 format: official slot map, bracket links and Annex C."""
    annex = json.loads((_CANON / "wc2026_third_place_allocation.json").read_text(encoding="utf-8"))
    fmt = TournamentFormat(
        name="FIFA World Cup 2026", year=2026, groups=groups, group_fixtures=group_fixtures,
        r32_slots=R32_SLOTS_2026, knockout_links=KNOCKOUT_LINKS_2026,
        third_place_allocation={k: v["opponents"] for k, v in annex["combinations"].items()},
        n_third_qualifiers=8, stage_of={no: _stage_2026(no) for no in range(73, 105)},
        venue_country=venue_country,
    )
    fmt.validate()
    return fmt
