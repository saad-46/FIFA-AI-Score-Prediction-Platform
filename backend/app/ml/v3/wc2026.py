"""
The 2026 World Cup as inputs to the tournament engine.

Groups come from the committed team reference; fixtures, venues and (for
conditional forecasts and the replay test) real results come from the match
corpus. Two cut-off dates matter and are kept apart on purpose:

    FORECAST_CUTOFF   2026-06-11, the opening day. A pre-tournament forecast may
                      use only matches strictly before it.
    TOURNAMENT_END    2026-07-19, the final. The tournament is over; the app
                      must present it as history, not as an upcoming event.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from app.ml.v3.data import load_matches
from app.ml.v3.tournament import (FixedResult, GroupFixture, R32_SLOTS_2026, KNOCKOUT_LINKS_2026,
                                  TournamentFormat, rank_group, rank_third_placed, wc2026_format)

FORECAST_CUTOFF = pd.Timestamp("2026-06-11")
TOURNAMENT_END = pd.Timestamp("2026-07-19")
HOSTS = ("USA", "Mexico", "Canada")

_REFERENCE = Path(__file__).resolve().parents[2] / "data" / "processed" / "teams_reference.csv"

# Knockout matches staged outside the United States (official match schedule):
# Monterrey 75; Mexico City 79 and 92; Toronto 83; Vancouver 85 and 96.
_KO_VENUE_EXCEPTIONS = {75: "Mexico", 79: "Mexico", 92: "Mexico", 83: "Canada", 85: "Canada", 96: "Canada"}
KO_VENUE_COUNTRY = {no: _KO_VENUE_EXCEPTIONS.get(no, "USA") for no in range(73, 105)}


@lru_cache(maxsize=1)
def team_reference() -> pd.DataFrame:
    return pd.read_csv(_REFERENCE, encoding="utf-8-sig")


@lru_cache(maxsize=1)
def code_to_name() -> dict[str, str]:
    ref = team_reference()
    return dict(zip(ref["fifa_code"], ref["canonical_name"]))


@lru_cache(maxsize=1)
def name_to_code() -> dict[str, str]:
    return {v: k for k, v in code_to_name().items()}


@lru_cache(maxsize=1)
def display_name_to_name() -> dict[str, str]:
    """
    Display names from the official 2026 groups data (what the UI shows), case-
    folded, mapped to corpus names through the FIFA code. Two differ from the
    team reference: "Korea Republic" and "Bosnia & Herzegovina".
    """
    from app.data.fifa_2026 import load_groups
    by_code = code_to_name()
    return {t["name"].casefold(): by_code[t["code"]]
            for teams in load_groups().values() for t in teams if t["code"] in by_code}


def groups() -> dict[str, list[str]]:
    ref = team_reference()
    return {g: list(sub["canonical_name"]) for g, sub in ref.groupby("group", sort=True)}


def wc2026_matches(matches: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    m = load_matches() if matches is None else matches
    w = m[(m["tournament"] == "FIFA World Cup") & (m["date"] >= FORECAST_CUTOFF) & (m["date"] <= TOURNAMENT_END)]
    return w.sort_values(["date", "source_row"]).reset_index(drop=True)


def build_format(matches: Optional[pd.DataFrame] = None) -> tuple[TournamentFormat, pd.DataFrame]:
    """
    The 2026 format plus the tournament's own match rows. Group fixtures are the
    72 matches between two teams of the same group; they are numbered 1..72 in
    date order (group match numbers carry no meaning for the rules).
    """
    w = wc2026_matches(matches)
    grp = groups()
    team_group = {t: g for g, ts in grp.items() for t in ts}
    same_group = [team_group.get(a) is not None and team_group.get(a) == team_group.get(b)
                  for a, b in zip(w.team_a, w.team_b)]
    # A group pair can meet again in the knockout rounds; the group match is the earlier one.
    gs = w[same_group].drop_duplicates(subset=["team_a", "team_b"], keep="first")
    seen, keep = set(), []
    for i, (a, b) in enumerate(zip(gs.team_a, gs.team_b)):
        pair = frozenset((a, b))
        keep.append(pair not in seen)
        seen.add(pair)
    gs = gs[keep].reset_index(drop=True)
    fixtures = [
        GroupFixture(i + 1, team_group[r.team_a], r.team_a, r.team_b,
                     r.venue_country if r.venue_country in HOSTS else None)
        for i, r in enumerate(gs.itertuples(index=False))
    ]
    fmt = wc2026_format(grp, fixtures, dict(KO_VENUE_COUNTRY))
    return fmt, w


def actual_results(fmt: TournamentFormat, w: pd.DataFrame) -> dict[int, FixedResult]:
    """
    The real tournament expressed as ``{match number: FixedResult}``.

    Group matches map directly. Knockout matches are located by replaying the
    bracket: the real standings fix the Round-of-32 pairings, each pairing's
    real result fixes who advanced, and so on to the final -- so a knockout
    result is attached to its official match number without trusting any
    numbering in the source data.
    """
    import numpy as np
    rng = np.random.default_rng(0)
    by_pair: dict[frozenset, list] = {}
    for r in w.itertuples(index=False):
        by_pair.setdefault(frozenset((r.team_a, r.team_b)), []).append(r)

    fixed: dict[int, FixedResult] = {}
    used: set[str] = set()
    results_by_group: dict[str, list] = {g: [] for g in fmt.groups}
    for f in fmt.group_fixtures:
        r = by_pair[frozenset((f.team_a, f.team_b))][0]
        ga, gb = (r.goals_a, r.goals_b) if r.team_a == f.team_a else (r.goals_b, r.goals_a)
        fixed[f.match_number] = FixedResult(int(ga), int(gb))
        used.add(r.match_id)
        results_by_group[f.group].append((f.team_a, f.team_b, int(ga), int(gb)))

    winner, runner, thirds = {}, {}, []
    for g, ts in fmt.groups.items():
        order, stats = rank_group(ts, results_by_group[g], rng)
        winner[g], runner[g] = order[0], order[1]
        thirds.append((g, order[2], stats[order[2]]))
    third_of = dict(rank_third_placed(thirds, rng)[: fmt.n_third_qualifiers])
    alloc = fmt.third_place_allocation["".join(sorted(third_of))]

    def slot(s):
        kind, g = s
        return winner[g] if kind == "W" else runner[g] if kind == "R" else third_of[alloc[g]]

    mw, ml = {}, {}

    def record(no: int, a: str, b: str) -> None:
        cands = [r for r in by_pair.get(frozenset((a, b)), []) if r.match_id not in used]
        if not cands:
            raise LookupError(f"match {no}: no real result found for {a} v {b}")
        r = cands[0]
        used.add(r.match_id)
        ga, gb = (r.goals_a, r.goals_b) if r.team_a == a else (r.goals_b, r.goals_a)
        adv = None
        if ga == gb:
            adv = r.shootout_winner
            if adv not in (a, b):
                raise LookupError(f"match {no}: level score for {a} v {b} but no shoot-out winner on record")
        fixed[no] = FixedResult(int(ga), int(gb), adv)
        mw[no], ml[no] = ((a, b) if (ga > gb or adv == a) else (b, a))

    for no in sorted(R32_SLOTS_2026):
        sa, sb = R32_SLOTS_2026[no]
        record(no, slot(sa), slot(sb))
    for no in sorted(KNOCKOUT_LINKS_2026):
        (ka, na), (kb, nb) = KNOCKOUT_LINKS_2026[no]
        record(no, mw[na] if ka == "winner_of" else ml[na], mw[nb] if kb == "winner_of" else ml[nb])
    return fixed


def group_stage_results(fmt: TournamentFormat, w: pd.DataFrame) -> tuple[dict[int, FixedResult], pd.Timestamp]:
    """
    The 72 real group results and the first date on which all of them are
    known (the day after the last group match). A forecast conditioned on the
    group stage may use matches strictly before that date and nothing later.
    """
    n_group = len(fmt.group_fixtures)
    fixed = {no: r for no, r in actual_results(fmt, w).items() if no <= n_group}
    pairs = {frozenset((f.team_a, f.team_b)) for f in fmt.group_fixtures}
    seen: set[frozenset] = set()
    last = None
    for r in w.itertuples(index=False):
        pair = frozenset((r.team_a, r.team_b))
        if pair in pairs and pair not in seen:
            seen.add(pair)
            last = r.date
    known_from = pd.Timestamp(last) + pd.Timedelta(days=1)
    knockout = w[w["date"] >= known_from]
    if len(seen) != n_group or len(knockout) != len(w) - n_group:
        raise AssertionError("group stage and knockout rounds overlap in time; cannot condition cleanly")
    return fixed, known_from
