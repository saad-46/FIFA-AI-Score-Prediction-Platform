"""
Tournament simulation on the V3 pipeline.

Three questions can be asked, and the response always says which one was
answered:

    pre_tournament      The official 2026 groups, forecast from information
                        available before the opening match (2026-06-11). Every
                        one of the 104 matches is simulated.
    after_group_stage   The real group results are taken as given; team
                        ratings absorb them as they would have in real time;
                        the knockout rounds are simulated on the bracket those
                        results actually produced.
    custom_groups       Twelve caller-chosen groups of real national teams, on
                        the 2026 format at neutral venues, from the most recent
                        ratings. A hypothetical, labelled as one.

The 2026 tournament is over. Neither official mode predicts the future: one
shows what a pre-tournament forecast looked like, the other what the knockout
stage looked like from the end of the group stage. Real results live on the
bracket endpoints.

Nothing here knows which teams are hosts beyond the venue of each match, and
no team is special-cased. A team the corpus has never seen is rejected rather
than given an invented rating.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from itertools import combinations
from typing import Any, Optional

from app.ml.v3 import wc2026
from app.ml.v3.inference import ForecastService, get_service
from app.ml.v3.tournament import GroupFixture, TournamentFormat, wc2026_format
from app.ml.v3.tournament_fast import MatchTensor, simulate_fast

logger = logging.getLogger(__name__)

DEFAULT_SEED = 20260611
PRE_TOURNAMENT_BUNDLE = "wc2026_pretournament"
WORLD_CUP_TIER = 5
_GROUP_LETTERS = "ABCDEFGHIJKL"

NOTES = {
    "pre_tournament": (
        "Pre-tournament forecast: uses only matches played before 11 June 2026. The tournament has since been "
        "played; this is what the model would have said beforehand, not a prediction of something still to come."
    ),
    "after_group_stage": (
        "Conditional forecast: the real 2026 group results are taken as given and the knockout rounds are "
        "simulated on the bracket they produced, using ratings as of the end of the group stage. No knockout "
        "result is used."
    ),
    "custom_groups": (
        "Hypothetical tournament: caller-chosen groups on the 2026 format, every match at a neutral venue, "
        "from the most recent ratings."
    ),
}

_lock = threading.Lock()
_prepared: dict[str, tuple[ForecastService, TournamentFormat, MatchTensor, dict]] = {}
_results: "OrderedDict[tuple, tuple[dict, dict]]" = OrderedDict()
_RESULT_CACHE_SIZE = 32


class InvalidGroups(ValueError):
    """The caller's groups cannot be simulated (unknown team, wrong shape)."""


def reset_cache() -> None:
    with _lock:
        _prepared.clear()
        _results.clear()


def _prepare_official(mode: str):
    """Service, format, pairwise tensor and fixed results for an official mode (cached)."""
    with _lock:
        if mode in _prepared:
            return _prepared[mode]
    base = get_service(PRE_TOURNAMENT_BUNDLE)
    fmt, w = wc2026.build_format(base.matches_all)
    if mode == "pre_tournament":
        svc, fixed = base, {}
    else:
        fixed, known_from = wc2026.group_stage_results(fmt, w)
        svc = base.advanced_to(known_from, "group-stage")
    tensor = svc.tensor(fmt.teams, hosts=wc2026.HOSTS, tier=WORLD_CUP_TIER)
    prepared = (svc, fmt, tensor, fixed)
    with _lock:
        _prepared[mode] = prepared
    return prepared


def _prepare_custom(groups: dict[str, list[str]]):
    svc = get_service()                      # most recent ratings
    if len(groups) != 12 or any(len(ts) != 4 for ts in groups.values()):
        raise InvalidGroups("the 2026 format needs exactly 12 groups of 4 teams")
    labels: dict[str, str] = {}              # corpus name -> caller's label
    unknown: list[str] = []
    for ts in groups.values():
        for label in ts:
            name = svc.resolve(label)
            if name is None:
                unknown.append(label)
            elif name in labels:
                raise InvalidGroups(f"{label!r} and {labels[name]!r} are the same team")
            else:
                labels[name] = label
    if unknown:
        shown = ", ".join(sorted(unknown)[:12]) + (" ..." if len(unknown) > 12 else "")
        raise InvalidGroups(
            f"no match history for {len(unknown)} team(s): {shown}. Custom groups must be national teams "
            "(FIFA code or name); a forecast cannot be made for a team with no recorded matches."
        )
    # The bracket's slot map is written in terms of groups A-L. If the caller's
    # groups are not already lettered A-L they take those letters in the order given.
    names = list(groups)
    if sorted(names) == list(_GROUP_LETTERS):
        lettered = {n: n for n in names}
    else:
        lettered = dict(zip(names, _GROUP_LETTERS))
    by_label = {v: k for k, v in labels.items()}
    fmt_groups = {lettered[g]: [by_label[t] for t in groups[g]] for g in sorted(names, key=lambda n: lettered[n])}
    fixtures, no = [], 0
    for letter, ts in fmt_groups.items():
        for a, b in combinations(ts, 2):
            no += 1
            fixtures.append(GroupFixture(no, letter, a, b, None))
    fmt = wc2026_format(fmt_groups, fixtures, {})          # no venue information: every match neutral
    tensor = svc.tensor(fmt.teams, hosts=(), tier=WORLD_CUP_TIER)
    return svc, fmt, tensor, {}, labels, lettered


def simulate_tournament(*, official: bool, use_real_results: bool, groups: Optional[dict[str, list[str]]],
                        n_simulations: int, seed: Optional[int]) -> tuple[dict[str, dict], dict[str, Any]]:
    """
    Returns ``(probabilities, meta)``. Probabilities are keyed by FIFA code for
    the official groups and by the caller's own labels for custom groups.
    Raises ``ModelUnavailable`` (bundle missing/inconsistent) or ``InvalidGroups``.
    """
    t0 = time.time()
    seed = DEFAULT_SEED if seed is None else int(seed)
    extra: dict[str, Any] = {}
    if official:
        mode = "after_group_stage" if use_real_results else "pre_tournament"
        key = (mode, n_simulations, seed)
        with _lock:
            if key in _results:
                _results.move_to_end(key)
                return _results[key]
        svc, fmt, tensor, fixed = _prepare_official(mode)
        to_code = wc2026.name_to_code()
        relabel = {t: to_code[t] for t in fmt.teams}
    else:
        mode, key = "custom_groups", None
        svc, fmt, tensor, fixed, relabel, lettered = _prepare_custom(groups or {})
        if any(k != v for k, v in lettered.items()):
            extra["group_letters"] = lettered

    out = simulate_fast(fmt, tensor, n_sims=n_simulations, seed=seed, fixed=fixed)
    diag = out["diagnostics"]
    if abs(diag["champion_probability_sum"] - 1.0) > 1e-9:
        raise RuntimeError("champion probabilities do not sum to 1")
    probabilities = {relabel[t]: stats for t, stats in out["teams"].items()}
    meta = {
        "engine": "v3", "mode": mode, "model_version": svc.version,
        "information_cutoff": str(svc.cutoff.date()), "data_through": svc.data_through,
        "n_simulations": n_simulations, "seed": seed, "fixed_matches": len(fixed),
        "champion_probability_sum": diag["champion_probability_sum"],
        "max_champion_standard_error": diag["max_champion_standard_error"],
        "knockout_resolution": diag["knockout_resolution"],
        "tournament_status": "completed" if official else "hypothetical",
        "note": NOTES[mode], **extra,
    }
    logger.info("v3 simulate mode=%s n=%d seed=%d model=%s cutoff=%s fixed=%d latency_ms=%.0f",
                mode, n_simulations, seed, svc.version, meta["information_cutoff"], len(fixed),
                (time.time() - t0) * 1000)
    result = (probabilities, meta)
    if key is not None:
        with _lock:
            _results[key] = result
            while len(_results) > _RESULT_CACHE_SIZE:
                _results.popitem(last=False)
    return result
