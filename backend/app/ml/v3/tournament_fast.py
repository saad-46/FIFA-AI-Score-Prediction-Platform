"""
Vectorised tournament simulation.

Same rules, same inputs and same output shape as ``tournament.simulate`` -- that
function is the readable reference implementation and the specification. This
one plays all simulations of a match at once with numpy so that 100,000
tournaments take seconds instead of minutes inside an API request.

The two are kept honest against each other by the test-suite: with every result
fixed they must agree exactly, and with free sampling their stage probabilities
must agree within Monte Carlo error.

The only step still done one simulation at a time is breaking a points tie
inside a group, which reuses ``tournament.rank_group`` so the head-to-head rules
exist in exactly one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from app.ml.v3.models import MAX_GOALS
from app.ml.v3.tournament import (EXTRA_TIME_FRACTION, STAGES, FixedResult, TournamentFormat, rank_group)

_N = MAX_GOALS + 1
_CELLS = _N * _N


@dataclass
class MatchTensor:
    """
    Scoreline distributions for every ordered pair of the tournament's teams.

        cdf0[a, b]   cumulative flattened score matrix, a v b at a neutral venue
        cdfh[a, b]   the same with a playing at home (filled only for hosts)
        lam0/lamh    expected goals of the first team; the second team's are the transpose-style lookup
        pens[a, b]   P(a wins a shoot-out against b)
    """
    teams: list[str]
    cdf0: np.ndarray
    lam0_a: np.ndarray
    lam0_b: np.ndarray
    cdfh: np.ndarray
    lamh_a: np.ndarray
    lamh_b: np.ndarray
    pens: np.ndarray
    hosts: tuple[str, ...] = ()


def build_tensor(teams: list[str], hosts: tuple[str, ...],
                 batch_provider: Callable[[list[tuple[str, str, int]]], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]
                 ) -> MatchTensor:
    """
    ``batch_provider(fixtures)`` takes [(a, b, venue)] and returns
    (matrices [n, G, G], lambda_a [n], lambda_b [n], p_shootout_a [n]).
    """
    T = len(teams)
    idx = {t: i for i, t in enumerate(teams)}
    cdf0 = np.zeros((T, T, _CELLS)); lam0_a = np.ones((T, T)); lam0_b = np.ones((T, T)); pens = np.full((T, T), 0.5)
    cdfh = np.zeros((T, T, _CELLS)); lamh_a = np.ones((T, T)); lamh_b = np.ones((T, T))

    def to_cdf(m: np.ndarray) -> np.ndarray:
        c = np.cumsum(m.reshape(len(m), -1), axis=1)
        c /= c[:, -1:]
        c[:, -1] = 1.0
        return c

    neutral = [(a, b, 0) for i, a in enumerate(teams) for b in teams[i + 1:]]
    mats, la, lb, pp = batch_provider(neutral)
    ia = np.array([idx[a] for a, _, _ in neutral]); ib = np.array([idx[b] for _, b, _ in neutral])
    cdf0[ia, ib] = to_cdf(mats); cdf0[ib, ia] = to_cdf(np.transpose(mats, (0, 2, 1)))
    lam0_a[ia, ib], lam0_b[ia, ib] = la, lb
    lam0_a[ib, ia], lam0_b[ib, ia] = lb, la
    pens[ia, ib], pens[ib, ia] = pp, 1.0 - pp

    home = [(h, b, 1) for h in hosts if h in idx for b in teams if b != h]
    if home:
        mats, la, lb, _ = batch_provider(home)
        ha = np.array([idx[a] for a, _, _ in home]); hb = np.array([idx[b] for _, b, _ in home])
        cdfh[ha, hb] = to_cdf(mats)
        lamh_a[ha, hb], lamh_b[ha, hb] = la, lb
    return MatchTensor(teams, cdf0, lam0_a, lam0_b, cdfh, lamh_a, lamh_b, pens, tuple(h for h in hosts if h in idx))


def _sample_cells(cdf_rows: np.ndarray, u: np.ndarray) -> np.ndarray:
    return np.minimum((cdf_rows < u[:, None]).sum(axis=1), _CELLS - 1)


def _play_group_fixture(mt: MatchTensor, a: int, b: int, venue: int, n: int, rng) -> tuple[np.ndarray, np.ndarray]:
    if venue == 1:
        cdf = mt.cdfh[a, b]
    elif venue == -1:
        cdf = mt.cdfh[b, a]
    else:
        cdf = mt.cdf0[a, b]
    cell = np.minimum(np.searchsorted(cdf, rng.random(n), side="right"), _CELLS - 1)
    g1, g2 = cell // _N, cell % _N
    return (g2, g1) if venue == -1 else (g1, g2)


def _play_knockout(mt: MatchTensor, a: np.ndarray, b: np.ndarray, host: Optional[int], rng
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised knockout tie. Returns goals_a, goals_b (incl. extra time), a_advances, method code."""
    n = len(a)
    if host is None:
        b_home = np.zeros(n, dtype=bool); any_home = b_home
    else:
        a_home, b_home = a == host, b == host
        any_home = a_home | b_home
    x = np.where(b_home, b, a); y = np.where(b_home, a, b)          # x is the home side when there is one
    cdf = mt.cdf0[x, y]
    lx, ly = mt.lam0_a[x, y], mt.lam0_b[x, y]
    if host is not None and any_home.any():
        h = np.nonzero(any_home)[0]
        cdf[h] = mt.cdfh[x[h], y[h]]
        lx = lx.copy(); ly = ly.copy()
        lx[h], ly[h] = mt.lamh_a[x[h], y[h]], mt.lamh_b[x[h], y[h]]
    cell = _sample_cells(cdf, rng.random(n))
    gx, gy = cell // _N, cell % _N
    method = np.zeros(n, dtype=np.int8)                                # 0 = 90 minutes
    level = gx == gy
    ex = rng.poisson(lx * EXTRA_TIME_FRACTION); ey = rng.poisson(ly * EXTRA_TIME_FRACTION)
    gx = gx + np.where(level, ex, 0); gy = gy + np.where(level, ey, 0)
    still = level & (gx == gy)
    method[level & ~still] = 1                                         # extra time
    method[still] = 2                                                  # penalties
    pens_x = rng.random(n) < mt.pens[x, y]
    x_adv = np.where(still, pens_x, gx > gy)
    ga = np.where(b_home, gy, gx); gb = np.where(b_home, gx, gy)
    a_adv = np.where(b_home, ~x_adv, x_adv)
    return ga, gb, a_adv, method


def _annex_table(fmt: TournamentFormat, groups: list[str]) -> np.ndarray:
    """alloc[bitmask of qualifying third-placed groups, winner group] -> third-placed group (or -1)."""
    gi = {g: i for i, g in enumerate(groups)}
    table = np.full((1 << len(groups), len(groups)), -1, dtype=np.int16)
    for key, opp in fmt.third_place_allocation.items():
        mask = sum(1 << gi[g] for g in key)
        for w, t in opp.items():
            table[mask, gi[w]] = gi[t]
    return table


def simulate_fast(fmt: TournamentFormat, mt: MatchTensor, n_sims: int = 10000, seed: int = 20260611,
                  fixed: Optional[dict[int, FixedResult]] = None, n_batches: int = 10) -> dict[str, Any]:
    fmt.validate()
    fixed = fixed or {}
    if mt.teams != fmt.teams:
        raise ValueError("tensor team order must match the format's team order")
    rng = np.random.default_rng(seed)
    teams = fmt.teams
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    groups = list(fmt.groups)
    G = len(groups)
    S = {s: i for i, s in enumerate(STAGES)}
    annex = _annex_table(fmt, groups)
    fixtures_by_group = {g: [f for f in fmt.group_fixtures if f.group == g] for g in groups}
    host_idx = {c: idx[c] for c in set(fmt.venue_country.values()) if c in idx}

    n_batches = max(1, min(n_batches, n_sims))
    sizes = [n_sims // n_batches + (1 if i < n_sims % n_batches else 0) for i in range(n_batches)]
    counts = np.zeros((n_batches, T, len(STAGES)), dtype=np.int64)
    pts_sum = np.zeros(T); gf_sum = np.zeros(T); ga_sum = np.zeros(T)
    group_pos = np.zeros((T, 4), dtype=np.int64)
    methods = np.zeros(3, dtype=np.int64)

    for bi, n in enumerate(sizes):
        winner = np.zeros((G, n), dtype=np.int64); runner = np.zeros((G, n), dtype=np.int64)
        third = np.zeros((G, n), dtype=np.int64); third_key = np.zeros((G, n))
        for g_i, g in enumerate(groups):
            gteams = fmt.groups[g]
            local = {t: k for k, t in enumerate(gteams)}
            k_n = len(gteams)
            pts = np.zeros((n, k_n), dtype=np.int64); gd = np.zeros((n, k_n), dtype=np.int64)
            gf = np.zeros((n, k_n), dtype=np.int64)
            scores = []
            for f in fixtures_by_group[g]:
                fr = fixed.get(f.match_number)
                if fr is not None:
                    ga = np.full(n, fr.goals_a, dtype=np.int64); gb = np.full(n, fr.goals_b, dtype=np.int64)
                else:
                    v = 0
                    if f.venue_country is not None:
                        v = 1 if f.team_a == f.venue_country else (-1 if f.team_b == f.venue_country else 0)
                    ga, gb = _play_group_fixture(mt, idx[f.team_a], idx[f.team_b], v, n, rng)
                la, lb = local[f.team_a], local[f.team_b]
                gf[:, la] += ga; gf[:, lb] += gb
                gd[:, la] += ga - gb; gd[:, lb] += gb - ga
                pts[:, la] += np.where(ga > gb, 3, np.where(ga == gb, 1, 0))
                pts[:, lb] += np.where(gb > ga, 3, np.where(ga == gb, 1, 0))
                scores.append((f.team_a, f.team_b, ga, gb))

            order = np.argsort(-pts, axis=1, kind="stable")
            sorted_pts = np.take_along_axis(pts, order, axis=1)
            tied = np.nonzero((sorted_pts[:, 1:] == sorted_pts[:, :-1]).any(axis=1))[0]
            for s in tied:                       # head-to-head rules: one implementation, in tournament.py
                res = [(a, b, int(ga[s]), int(gb[s])) for a, b, ga, gb in scores]
                ranked, _ = rank_group(gteams, res, rng)
                order[s] = [local[t] for t in ranked]

            g_idx = np.array([idx[t] for t in gteams])
            rows = np.arange(n)
            winner[g_i] = g_idx[order[:, 0]]; runner[g_i] = g_idx[order[:, 1]]
            if k_n > 2:
                t3 = order[:, 2]
                third[g_i] = g_idx[t3]
                third_key[g_i] = (pts[rows, t3] * 10000 + (gd[rows, t3] + 100) * 100 + gf[rows, t3]) + rng.random(n) * 0.5
            for pos in range(k_n):
                np.add.at(group_pos[:, pos], g_idx[order[:, pos]], 1)
            pts_sum[g_idx] += pts.sum(axis=0); gf_sum[g_idx] += gf.sum(axis=0); ga_sum[g_idx] += (gf - gd).sum(axis=0)
        counts[bi, :, S["group"]] += n

        # best third-placed teams -> Annex C row
        rank3 = np.argsort(-third_key, axis=0, kind="stable")[: fmt.n_third_qualifiers]      # (8, n) group indices
        mask = (1 << rank3).sum(axis=0)
        alloc = annex[mask]                                                                   # (n, G)
        if (alloc.max(axis=1) < 0).any():
            raise RuntimeError("a set of qualifying third-placed groups is missing from the allocation table")
        cols = np.arange(n)

        def resolve(slot: tuple[str, str]) -> np.ndarray:
            kind, g = slot
            gi = groups.index(g)
            if kind == "W":
                return winner[gi]
            if kind == "R":
                return runner[gi]
            return third[alloc[:, gi], cols]

        mw: dict[int, np.ndarray] = {}
        ml: dict[int, np.ndarray] = {}

        def play(no: int, a: np.ndarray, b: np.ndarray) -> None:
            st = S[fmt.stage_of[no]]
            counts[bi, :, st] += np.bincount(a, minlength=T) + np.bincount(b, minlength=T)
            fr = fixed.get(no)
            if fr is not None:
                if fr.goals_a != fr.goals_b:
                    a_adv = np.full(n, fr.goals_a > fr.goals_b)
                elif fr.advances in idx:
                    adv = idx[fr.advances]
                    if not ((a == adv) | (b == adv)).all():
                        raise ValueError(f"match {no}: `advances` is not one of the two teams")
                    a_adv = a == adv
                else:
                    raise ValueError(f"match {no}: level fixed result needs `advances`")
            else:
                c = fmt.venue_country.get(no)
                _, _, a_adv, method = _play_knockout(mt, a, b, host_idx.get(c), rng)
                methods[:] += np.bincount(method, minlength=3)
            mw[no] = np.where(a_adv, a, b); ml[no] = np.where(a_adv, b, a)

        for no in sorted(fmt.r32_slots):
            sa, sb = fmt.r32_slots[no]
            play(no, resolve(sa), resolve(sb))
        for no in sorted(fmt.knockout_links):
            (ka, na), (kb, nb) = fmt.knockout_links[no]
            play(no, mw[na] if ka == "winner_of" else ml[na], mw[nb] if kb == "winner_of" else ml[nb])
        counts[bi, :, S["winner"]] += np.bincount(mw[fmt.final_match], minlength=T)

    total = counts.sum(axis=0)
    batch_win = counts[:, :, S["winner"]] / np.array(sizes)[:, None]
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
    return {
        "format": fmt.name, "n_simulations": n_sims, "seed": seed, "n_batches": n_batches,
        "fixed_matches": sorted(fixed), "teams": out_teams,
        "diagnostics": {
            "champion_probability_sum": float(sum(v["winner"] for v in out_teams.values())),
            "max_champion_standard_error": float(max(v["winner_se"] for v in out_teams.values())),
            "max_champion_batch_sd": float(max(v["winner_batch_sd"] for v in out_teams.values())),
            "knockout_resolution": {"90": int(methods[0]), "aet": int(methods[1]), "pens": int(methods[2])},
        },
    }
