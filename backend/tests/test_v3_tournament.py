"""
V3 tournament engine: group ranking, third-place qualification, the official
2026 bracket, and the two simulators (readable reference and vectorised).

The strongest test here is the replay: fed the 104 real results of the 2026
World Cup, the engine must reproduce the real bracket round by round and crown
the real champion. A wrong slot map, a wrong Annex C row or a wrong tie-break
cannot survive it.
"""

from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pytest

from app.ml.v3 import wc2026
from app.ml.v3.inference import get_service
from app.ml.v3.models import score_matrix
from app.ml.v3.tournament import (KNOCKOUT_LINKS_2026, R32_SLOTS_2026, STAGES, FixedResult, GroupFixture,
                                  MatchSampler, rank_group, rank_third_placed, simulate, wc2026_format)
from app.ml.v3.tournament_fast import build_tensor, simulate_fast

LETTERS = "ABCDEFGHIJKL"


@pytest.fixture(scope="module")
def pre():
    return get_service("wc2026_pretournament")


@pytest.fixture(scope="module")
def official(pre):
    fmt, w = wc2026.build_format(pre.matches_all)
    return fmt, w


@pytest.fixture(scope="module")
def tensor(pre, official):
    fmt, _ = official
    return pre.tensor(fmt.teams, hosts=wc2026.HOSTS, tier=5)


def _neutral_format():
    """48 anonymous teams, round-robin groups, no venue information."""
    groups = {g: [f"{g}{i}" for i in range(1, 5)] for g in LETTERS}
    fixtures, no = [], 0
    for g, ts in groups.items():
        for a, b in combinations(ts, 2):
            no += 1
            fixtures.append(GroupFixture(no, g, a, b, None))
    return wc2026_format(groups, fixtures, {})


def _equal_provider(a, b, venue):
    return score_matrix(1.3, 1.3, -0.05), 1.3, 1.3, 0.5


def _equal_batch(fixtures):
    n = len(fixtures)
    m = score_matrix(1.3, 1.3, -0.05)
    return np.repeat(m[None], n, axis=0), np.full(n, 1.3), np.full(n, 1.3), np.full(n, 0.5)


# ═══════════════════════════════════════════════════════════════════════════
# Group ranking
# ═══════════════════════════════════════════════════════════════════════════

def test_group_ranked_by_points():
    rng = np.random.default_rng(0)
    res = [("A", "B", 1, 0), ("A", "C", 2, 0), ("A", "D", 1, 0), ("B", "C", 1, 0), ("B", "D", 3, 0), ("C", "D", 1, 0)]
    order, stats = rank_group(["A", "B", "C", "D"], res, rng)
    assert order == ["A", "B", "C", "D"]
    assert stats["A"] == (9, 4, 4) and stats["D"] == (0, -5, 0)


def test_head_to_head_beats_overall_goal_difference():
    """2026 rules: two teams level on points are split by their own meeting first."""
    rng = np.random.default_rng(0)
    # A and B both finish on 6. B has the far better overall goal difference, but A beat B.
    res = [("A", "B", 1, 0), ("A", "C", 0, 1), ("A", "D", 1, 0), ("B", "C", 5, 0), ("B", "D", 5, 0), ("C", "D", 0, 0)]
    order, stats = rank_group(["A", "B", "C", "D"], res, rng)
    assert stats["A"][0] == stats["B"][0] == 6
    assert stats["B"][1] > stats["A"][1]
    assert order[:2] == ["A", "B"]


def test_three_way_tie_uses_the_mini_table():
    rng = np.random.default_rng(0)
    # A, B, C each beat D and take 3 points from each other in a cycle; the cycle's margins differ.
    res = [("A", "B", 3, 0), ("B", "C", 1, 0), ("C", "A", 1, 0),
           ("A", "D", 1, 0), ("B", "D", 4, 0), ("C", "D", 1, 0)]
    order, stats = rank_group(["A", "B", "C", "D"], res, rng)
    assert stats["A"][0] == stats["B"][0] == stats["C"][0] == 6
    # Mini-table goal difference: A +2, C 0, B -2 -- even though B has the best overall goal difference.
    assert order == ["A", "C", "B", "D"]


def test_fully_level_teams_are_separated_by_lot_not_by_listing_order():
    res = [("A", "B", 1, 1), ("A", "C", 1, 1), ("A", "D", 1, 1), ("B", "C", 1, 1), ("B", "D", 1, 1), ("C", "D", 1, 1)]
    firsts = {rank_group(["A", "B", "C", "D"], res, np.random.default_rng(s))[0][0] for s in range(60)}
    assert firsts == {"A", "B", "C", "D"}


def test_third_placed_teams_ranked_by_points_then_goal_difference_then_goals():
    rng = np.random.default_rng(0)
    thirds = [("A", "a", (3, 0, 2)), ("B", "b", (4, -1, 1)), ("C", "c", (3, 1, 1)), ("D", "d", (3, 0, 3))]
    assert rank_third_placed(thirds, rng) == [("B", "b"), ("C", "c"), ("D", "d"), ("A", "a")]


# ═══════════════════════════════════════════════════════════════════════════
# Format: official bracket and Annex C
# ═══════════════════════════════════════════════════════════════════════════

def test_official_format_shape(official):
    fmt, _ = official
    assert len(fmt.teams) == 48 and len(set(fmt.teams)) == 48
    assert len(fmt.group_fixtures) == 72
    assert sorted(fmt.r32_slots) == list(range(73, 89))
    assert sorted(fmt.knockout_links) == list(range(89, 105))
    per_team = {t: 0 for t in fmt.teams}
    for f in fmt.group_fixtures:
        per_team[f.team_a] += 1
        per_team[f.team_b] += 1
    assert set(per_team.values()) == {3}


def test_round_of_32_slots_use_every_qualifier_once():
    slots = [s for pair in R32_SLOTS_2026.values() for s in pair]
    assert sorted(g for k, g in slots if k == "W") == list(LETTERS)
    assert sorted(g for k, g in slots if k == "R") == list(LETTERS)
    assert len([s for s in slots if s[0] == "T"]) == 8
    assert len(slots) == 32


def test_knockout_links_form_a_single_elimination_tree():
    feeds: dict[int, int] = {}
    for no, pair in KNOCKOUT_LINKS_2026.items():
        for kind, src in pair:
            if kind == "winner_of":
                assert src not in feeds, f"winner of {src} is used twice"
                feeds[src] = no
            assert src < no
    assert sorted(feeds) == list(range(73, 103))            # every match but the last two feeds a later one
    assert KNOCKOUT_LINKS_2026[103] == (("loser_of", 101), ("loser_of", 102))
    assert KNOCKOUT_LINKS_2026[104] == (("winner_of", 101), ("winner_of", 102))


def test_annex_c_covers_every_combination_consistently(official):
    fmt, _ = official
    table = fmt.third_place_allocation
    assert len(table) == math.comb(12, 8) == 495
    third_slots = {a[1] if a[0] == "T" else b[1] for a, b in R32_SLOTS_2026.values() if "T" in (a[0], b[0])}
    assert len(third_slots) == 8
    for key, opponents in table.items():
        assert len(key) == 8 and list(key) == sorted(key)
        assert set(opponents) == third_slots                 # the same eight group winners always host a third
        assert sorted(opponents.values()) == list(key)       # each qualified third is used exactly once
        assert all(w != t for w, t in opponents.items())     # never against the winner of its own group


# ═══════════════════════════════════════════════════════════════════════════
# Replay of the real tournament
# ═══════════════════════════════════════════════════════════════════════════

def test_replay_reproduces_the_real_2026_world_cup(pre, official, tensor):
    fmt, w = official
    fixed = wc2026.actual_results(fmt, w)
    assert sorted(fixed) == list(range(1, 105))

    ref = simulate(fmt, pre.sampler(tier=5), n_sims=2, seed=1, fixed=fixed, return_paths=True)
    fast = simulate_fast(fmt, tensor, n_sims=2, seed=1, fixed=fixed)
    for out in (ref, fast):
        t = out["teams"]
        assert t["Spain"]["winner"] == 1.0
        assert t["Argentina"]["final"] == 1.0 and t["Argentina"]["winner"] == 0.0
        assert t["USA"]["r16"] == 1.0 and t["USA"]["qf"] == 0.0        # lost to Belgium in the Round of 16
        assert t["Belgium"]["qf"] == 1.0
        assert sum(v["winner"] for v in t.values()) == 1.0
    # With nothing left to chance the two engines must agree exactly.
    assert all(ref["teams"][t][s] == fast["teams"][t][s] for t in fmt.teams for s in STAGES)

    # Every replayed knockout tie was played in the host country the schedule says.
    path = ref["paths"][0]["matches"]
    ko = w[w["date"] >= wc2026.group_stage_results(fmt, w)[1]]
    played = {frozenset((r.team_a, r.team_b)): r.venue_country for r in ko.itertuples(index=False)}
    for no, (a, b, *_rest) in path.items():
        assert played[frozenset((a, b))] == wc2026.KO_VENUE_COUNTRY[no], no


def test_group_stage_conditioning_fixes_exactly_the_group_matches(official):
    fmt, w = official
    fixed, known_from = wc2026.group_stage_results(fmt, w)
    assert sorted(fixed) == list(range(1, 73))
    assert str(known_from.date()) == "2026-06-28"
    assert (w["date"] < known_from).sum() == 72


# ═══════════════════════════════════════════════════════════════════════════
# Simulation invariants
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_STAGE_TOTALS = {"group": 48, "r32": 32, "r16": 16, "qf": 8, "sf": 4, "third_place": 2, "final": 2, "winner": 1}


def _check_invariants(out):
    teams = out["teams"]
    for stage, total in EXPECTED_STAGE_TOTALS.items():
        assert sum(v[stage] for v in teams.values()) == pytest.approx(total, abs=1e-9), stage
    for v in teams.values():
        assert v["group"] == 1.0
        assert v["r32"] >= v["r16"] >= v["qf"] >= v["sf"] >= v["final"] >= v["winner"] >= 0.0
        assert v["sf"] == pytest.approx(v["final"] + v["third_place"], abs=1e-9)
        assert sum(v["group_position_probabilities"]) == pytest.approx(1.0, abs=1e-9)
    assert out["diagnostics"]["champion_probability_sum"] == pytest.approx(1.0, abs=1e-9)


def test_invariants_hold_in_both_engines(pre, official, tensor):
    fmt, _ = official
    _check_invariants(simulate(fmt, pre.sampler(tier=5, teams=fmt.teams), n_sims=300, seed=3))
    _check_invariants(simulate_fast(fmt, tensor, n_sims=3000, seed=3))


def test_each_simulation_has_exactly_one_champion(pre, official):
    fmt, _ = official
    out = simulate(fmt, pre.sampler(tier=5, teams=fmt.teams), n_sims=200, seed=5, return_paths=True)
    assert len(out["paths"]) == 200
    for path in out["paths"]:
        assert path["champion"] in fmt.teams
        assert len(path["matches"]) == 32
        final = path["matches"][104]
        assert path["champion"] == final[4] and final[4] in (final[0], final[1])
    counted = {}
    for path in out["paths"]:
        counted[path["champion"]] = counted.get(path["champion"], 0) + 1
    for team, n in counted.items():
        assert out["teams"][team]["winner"] == pytest.approx(n / 200)


def test_same_seed_same_result_and_different_seed_differs(official, tensor):
    fmt, _ = official
    a = simulate_fast(fmt, tensor, n_sims=2000, seed=11)
    b = simulate_fast(fmt, tensor, n_sims=2000, seed=11)
    c = simulate_fast(fmt, tensor, n_sims=2000, seed=12)
    assert a["teams"] == b["teams"]
    assert a["teams"] != c["teams"]


def test_reference_engine_is_reproducible(pre, official):
    fmt, _ = official
    sampler = pre.sampler(tier=5, teams=fmt.teams)
    assert simulate(fmt, sampler, n_sims=150, seed=4)["teams"] == simulate(fmt, sampler, n_sims=150, seed=4)["teams"]


def test_vectorised_engine_agrees_with_reference(pre, official, tensor):
    """Different random streams, same distribution: differences must be Monte Carlo noise."""
    fmt, _ = official
    n_ref, n_fast = 4000, 40000
    ref = simulate(fmt, pre.sampler(tier=5, teams=fmt.teams), n_sims=n_ref, seed=21)["teams"]
    fast = simulate_fast(fmt, tensor, n_sims=n_fast, seed=22)["teams"]
    worst = 0.0
    for t in fmt.teams:
        for stage in ("r32", "r16", "qf", "sf", "final", "winner"):
            p, q = ref[t][stage], fast[t][stage]
            pooled = (p * n_ref + q * n_fast) / (n_ref + n_fast)
            se = math.sqrt(max(pooled * (1 - pooled), 1e-4) * (1 / n_ref + 1 / n_fast))
            worst = max(worst, abs(p - q) / se)
    # 288 comparisons: the largest |z| of that many standard normals is ~3; 4.5 leaves room without hiding a bias.
    assert worst < 4.5, worst


def test_no_team_or_slot_is_privileged_when_all_teams_are_equal():
    """
    With 48 identical teams and no venue information every team must have the
    same chance: 1/48. Any hard-coded favourite, any bias toward a bracket slot
    or toward the first-listed team would show up here.
    """
    fmt = _neutral_format()
    mt = build_tensor(fmt.teams, (), _equal_batch)
    n = 60000
    out = simulate_fast(fmt, mt, n_sims=n, seed=7)
    _check_invariants(out)
    p = np.array([out["teams"][t]["winner"] for t in fmt.teams])
    se = math.sqrt((1 / 48) * (47 / 48) / n)
    assert np.abs(p - 1 / 48).max() < 4.5 * se
    reach = np.array([out["teams"][t]["r32"] for t in fmt.teams])
    assert np.abs(reach - 32 / 48).max() < 4.5 * math.sqrt((2 / 3) * (1 / 3) / n)

    ref = simulate(fmt, MatchSampler(_equal_provider), n_sims=6000, seed=7)
    _check_invariants(ref)
    q = np.array([ref["teams"][t]["winner"] for t in fmt.teams])
    assert np.abs(q - 1 / 48).max() < 4.5 * math.sqrt((1 / 48) * (47 / 48) / 6000)


def test_a_stronger_team_wins_more_often_wherever_it_is_drawn():
    """Strength, not position, decides: move one strong team around the draw and it stays the favourite."""
    fmt = _neutral_format()

    def batch_for(strong):
        def batch(fixtures):
            mats, la, lb, pp = [], [], [], []
            for a, b, _ in fixtures:
                x, y = (2.2 if a == strong else 1.2), (2.2 if b == strong else 1.2)
                mats.append(score_matrix(x, y, -0.05)); la.append(x); lb.append(y); pp.append(0.5)
            return np.array(mats), np.array(la), np.array(lb), np.array(pp)
        return batch

    for strong in ("A1", "F3", "L4"):
        out = simulate_fast(fmt, build_tensor(fmt.teams, (), batch_for(strong)), n_sims=6000, seed=9)["teams"]
        best = max(out, key=lambda t: out[t]["winner"])
        assert best == strong
        assert out[strong]["winner"] > 3 * (1 / 48)


def test_fixed_result_needs_a_shootout_winner_when_level(official, tensor):
    fmt, w = official
    fixed = wc2026.actual_results(fmt, w)
    level = [no for no, r in fixed.items() if no > 72 and r.goals_a == r.goals_b]
    assert level, "the real tournament had at least one shoot-out"
    broken = dict(fixed)
    broken[level[0]] = FixedResult(fixed[level[0]].goals_a, fixed[level[0]].goals_b, None)
    with pytest.raises(ValueError):
        simulate_fast(fmt, tensor, n_sims=2, seed=1, fixed=broken)


def test_pretournament_forecast_artifact_is_consistent(pre):
    """The committed forecast file matches what the bundle says about itself and is a proper distribution."""
    import json
    from app.ml.v3.inference import ART
    doc = json.loads((ART / "wc2026_pretournament_forecast.json").read_text(encoding="utf-8"))
    flat = json.dumps(doc)
    assert "2026-06-11" in flat
    assert pre.version in flat or pre.manifest["name"] in flat
