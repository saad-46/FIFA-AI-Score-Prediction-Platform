"""
FIFA World Cup 2026 tournament-structure loader (V2 canonical data).
===================================================================

Read-only accessors that expose the canonical WC2026 data — already validated
and committed under ``app/data/canonical/`` — in the shapes the frontend
bracket, group-standings and backtest views need.

Why this module exists: ``V2_FRONTEND_CONTRACT.md`` §6 records that the
tournament graph, real fixture results and the frozen prediction ledger were
all in place but *not exposed over the API*. This is that exposure layer and
nothing more — it reads files, it does not touch the database, the model, or
the tournament simulator.

Distinct from ``app.data.fifa_2026``, which serves the pre-tournament
*wallchart* (groups + fixture list with ``W53``/``L101`` placeholders). That
module stays the source for "what was scheduled"; this one is the source for
"what the bracket actually is, how it connects, and what happened", built on
the canonical dataset rather than the wallchart.

Stdlib only (``csv``/``json``) and ``lru_cache``d, matching the conventions in
``app/data/fifa_2026/__init__.py`` — these are hot read-only endpoints and
should not pull pandas into the request path.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_APP_DIR = Path(__file__).resolve().parent.parent.parent  # -> app/
_CANONICAL_DIR = _APP_DIR / "data" / "canonical"
_ARTIFACTS_DIR = _APP_DIR / "ml" / "v2" / "artifacts"

_GRAPH_PATH = _CANONICAL_DIR / "wc2026_tournament_graph.json"
_MATCHES_PATH = _CANONICAL_DIR / "canonical_matches.csv"
_TEAMS_PATH = _CANONICAL_DIR / "canonical_teams.csv"
_PREDICTIONS_PATH = _ARTIFACTS_DIR / "wc2026_pretournament_predictions.csv"
_COMPARISON_PATH = _ARTIFACTS_DIR / "wc2026_actual_comparison.json"

WC2026_YEAR = 2026

# Ordering used everywhere a stage list is rendered. Third place sits between
# the semi-final and the final because that is the order it is played in.
STAGE_ORDER: List[str] = [
    "group_stage",
    "round_of_32",
    "round_of_16",
    "quarter_final",
    "semi_final",
    "third_place",
    "final",
]

_POINTS_WIN = 3
_POINTS_DRAW = 1


def _to_int(value: Any) -> Optional[int]:
    """CSV numerics arrive as strings and sometimes as floats ('12.0')."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def load_tournament_graph() -> Dict[str, Any]:
    """The authoritative 104-node progression model (source of truth for the
    bracket's shape — the frontend must never hardcode these relationships)."""
    with open(_GRAPH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_wc2026_matches() -> List[Dict[str, Any]]:
    """The 104 canonical WC2026 fixtures with real results, keyed for lookup
    by ``match_number``."""
    with open(_MATCHES_PATH, "r", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if _to_int(row.get("year")) == WC2026_YEAR]
    return rows


@lru_cache(maxsize=1)
def load_wc2026_teams() -> Dict[str, Dict[str, Any]]:
    """The 48 WC2026 teams with their pre-tournament Elo, FIFA ranking, group
    and 3-letter code, keyed by canonical team name.

    Elo and ranking are the *pre-tournament* values the frozen model actually
    saw, so displaying them next to a prediction is consistent with what
    produced it.
    """
    with open(_TEAMS_PATH, "r", encoding="utf-8") as f:
        out: Dict[str, Dict[str, Any]] = {}
        for row in csv.DictReader(f):
            if str(row.get("is_wc2026_team", "")).strip().lower() != "true":
                continue
            name = row.get("team_name")
            if not name:
                continue
            out[name] = {
                "team_name": name,
                "fifa_code": row.get("fifa_code") or None,
                "confederation": row.get("confederation") or None,
                "group": row.get("wc2026_group") or None,
                "fifa_ranking": _to_int(row.get("fifa_ranking_pre_wc2026")),
                "elo_rating": _to_float(row.get("elo_rating_pre_wc2026")),
            }
    return out


@lru_cache(maxsize=1)
def load_frozen_predictions() -> Dict[int, Dict[str, Any]]:
    """The frozen model's pre-tournament predictions for all 104 matches.

    Generated once by ``predict_wc2026_frozen.py`` before any 2026 result was
    compared against, and treated as immutable — this loader reads that ledger,
    it never recomputes it.
    """
    with open(_PREDICTIONS_PATH, "r", encoding="utf-8") as f:
        out: Dict[int, Dict[str, Any]] = {}
        for row in csv.DictReader(f):
            number = _to_int(row.get("match_number"))
            if number is None:
                continue
            out[number] = {
                "predicted_winner": row.get("predicted_winner"),
                "home_win_probability": _to_float(row.get("home_win_probability")),
                "draw_probability": _to_float(row.get("draw_probability")),
                "away_win_probability": _to_float(row.get("away_win_probability")),
                "predicted_home_goals": _to_float(row.get("predicted_home_goals")),
                "predicted_away_goals": _to_float(row.get("predicted_away_goals")),
                "most_likely_score": row.get("most_likely_score"),
                "model_version": row.get("model_version"),
            }
    return out


@lru_cache(maxsize=1)
def load_backtest_comparison() -> Dict[str, Any]:
    """The read-only scoring of the frozen ledger against real results."""
    with open(_COMPARISON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_status(row: Dict[str, Any]) -> str:
    return "completed" if _to_float(row.get("home_score_ft")) is not None else "scheduled"


def _display_score(row: Dict[str, Any]) -> Optional[str]:
    """Human-readable final score, annotated when the match went beyond 90.

    A knockout tie shown as a bare "0-0" beside a winner reads as broken data,
    so extra time and shootouts are made explicit: "1-0 (aet)", "1-1 (4-3 pens)".
    """
    home_ft, away_ft = _to_int(row.get("home_score_ft")), _to_int(row.get("away_score_ft"))
    if home_ft is None or away_ft is None:
        return None

    home_pens, away_pens = _to_int(row.get("home_penalties")), _to_int(row.get("away_penalties"))
    if home_pens is not None and away_pens is not None:
        return f"{home_ft}-{away_ft} ({home_pens}-{away_pens} pens)"

    home_et, away_et = _to_int(row.get("home_score_et")), _to_int(row.get("away_score_et"))
    if home_et is not None and away_et is not None:
        return f"{home_et}-{away_et} (aet)"

    return f"{home_ft}-{away_ft}"


@lru_cache(maxsize=1)
def build_bracket() -> Dict[str, Any]:
    """Join the progression graph, the real fixtures and the frozen predictions
    into the single payload the bracket UI renders from."""
    graph = load_tournament_graph()
    matches_by_number = {
        _to_int(row.get("match_number")): row
        for row in load_wc2026_matches()
        if _to_int(row.get("match_number")) is not None
    }
    predictions = load_frozen_predictions()

    nodes: List[Dict[str, Any]] = []
    for node in graph.get("nodes", []):
        number = node["match_number"]
        row = matches_by_number.get(number, {})
        prediction = predictions.get(number)

        home_score = _to_int(row.get("home_score_ft"))
        away_score = _to_int(row.get("away_score_ft"))
        status = _match_status(row) if row else "scheduled"

        nodes.append(
            {
                "match_number": number,
                "stage": node["stage"],
                "is_knockout": node["is_knockout"],
                "group": (row.get("group_name") or None),
                "date": (row.get("date") or None),
                "kickoff_time_et": (row.get("kickoff_time_et") or None),
                "venue": (row.get("venue") or None),
                "city": (row.get("city") or None),
                "home_team": (row.get("home_team") or None),
                "away_team": (row.get("away_team") or None),
                "home_score": home_score,
                "away_score": away_score,
                # Extra-time columns carry the full score *after* ET (e.g. the
                # final was 0-0 FT, 1-0 ET), not ET-only goals. Both are
                # exposed so the UI can show "0-0 (1-0 aet)" rather than
                # rendering a bare 0-0 next to a winner, which reads as a bug.
                "home_score_et": _to_int(row.get("home_score_et")),
                "away_score_et": _to_int(row.get("away_score_et")),
                "home_penalties": _to_int(row.get("home_penalties")),
                "away_penalties": _to_int(row.get("away_penalties")),
                "result_method": (row.get("result_method") or None),
                "winner_team": (row.get("winner_team") or None),
                "status": status,
                # Progression wiring — drives the bracket's connectors and the
                # hover path highlight. Straight from the graph, never inferred.
                "home_source": node.get("home_source"),
                "away_source": node.get("away_source"),
                "feeds_winner_to": node.get("feeds_winner_to"),
                "feeds_loser_to": node.get("feeds_loser_to"),
                "prediction": prediction,
            }
        )

    return {
        "format": graph.get("format"),
        "stage_ranges": graph.get("stage_ranges", []),
        "nodes": nodes,
    }


@lru_cache(maxsize=1)
def build_standings() -> List[Dict[str, Any]]:
    """Final group tables, computed from the canonical group-stage results.

    Ordering is points, then goal difference, then goals for, then name — the
    first three of FIFA's published tiebreakers. Head-to-head and fair-play,
    which sit between them in the real regulations, are deliberately not
    implemented: the tournament is complete and this ordering reproduces the
    actual final standings, so inventing a partial tiebreak chain would add
    failure modes without changing a single row.
    """
    tables: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for row in load_wc2026_matches():
        if row.get("stage") != "group_stage":
            continue
        group = (row.get("group_name") or "").replace("Group ", "").strip()
        if not group:
            continue
        home, away = row.get("home_team"), row.get("away_team")
        home_score, away_score = _to_int(row.get("home_score_ft")), _to_int(row.get("away_score_ft"))
        if not home or not away or home_score is None or away_score is None:
            continue

        table = tables.setdefault(group, {})
        for team in (home, away):
            table.setdefault(
                team,
                {
                    "team": team,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                },
            )

        home_entry, away_entry = table[home], table[away]
        home_entry["played"] += 1
        away_entry["played"] += 1
        home_entry["goals_for"] += home_score
        home_entry["goals_against"] += away_score
        away_entry["goals_for"] += away_score
        away_entry["goals_against"] += home_score

        if home_score > away_score:
            home_entry["won"] += 1
            away_entry["lost"] += 1
            home_entry["points"] += _POINTS_WIN
        elif away_score > home_score:
            away_entry["won"] += 1
            home_entry["lost"] += 1
            away_entry["points"] += _POINTS_WIN
        else:
            home_entry["drawn"] += 1
            away_entry["drawn"] += 1
            home_entry["points"] += _POINTS_DRAW
            away_entry["points"] += _POINTS_DRAW

    out: List[Dict[str, Any]] = []
    for group in sorted(tables):
        rows = list(tables[group].values())
        for entry in rows:
            entry["goal_difference"] = entry["goals_for"] - entry["goals_against"]
        rows.sort(
            key=lambda e: (-e["points"], -e["goal_difference"], -e["goals_for"], e["team"])
        )
        for index, entry in enumerate(rows, start=1):
            entry["position"] = index
        out.append({"group": group, "standings": rows})

    return out


@lru_cache(maxsize=1)
def _all_canonical_matches() -> List[Dict[str, Any]]:
    """Every canonical World Cup match, 1930-2026 (all 1,069 rows)."""
    with open(_MATCHES_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def world_cup_head_to_head(team_a: str, team_b: str) -> Dict[str, Any]:
    """
    World Cup meetings between two teams across the full canonical corpus.

    Why this exists: the head-to-head shown next to a prediction was computed
    from ``load_matches_dataframe()``, whose WC-tagged rows only start in
    **2002**. Spain v Argentina therefore reported "No previous meetings"
    despite meeting at the 1966 World Cup — factually wrong, not merely
    unhelpful. This reads the canonical 1930-2026 corpus instead, so the
    answer covers the whole tournament history.

    Scope is World Cup matches only, and the response says so explicitly via
    ``scope``/``scope_label`` — the canonical dataset contains no friendlies or
    qualifiers, so a bare "no meetings" would be misleading for two teams who
    have played each other many times outside the finals.

    ``load_matches_dataframe()`` is deliberately left untouched: it feeds model
    inference, and changing its population would be a train/serve skew.
    """
    rows = [
        row
        for row in _all_canonical_matches()
        if {row.get("home_team"), row.get("away_team")} == {team_a, team_b}
        and _to_int(row.get("home_score_ft")) is not None
    ]
    rows.sort(key=lambda r: r.get("date") or "")

    a_wins = b_wins = draws = a_goals = b_goals = 0
    meetings: List[Dict[str, Any]] = []
    for row in rows:
        home, away = row["home_team"], row["away_team"]
        # Score the tie on the phase that actually decided it, matching what
        # _display_score renders. A match won in extra time is a win, not a
        # draw (the 2026 final finished 1-0 aet); only a shootout leaves the
        # match itself drawn, with the winner recorded separately.
        decided_on_penalties = (
            _to_int(row.get("home_penalties")) is not None
            and _to_int(row.get("away_penalties")) is not None
        )
        home_et, away_et = _to_int(row.get("home_score_et")), _to_int(row.get("away_score_et"))
        if not decided_on_penalties and home_et is not None and away_et is not None:
            home_score, away_score = home_et, away_et
        else:
            home_score = _to_int(row.get("home_score_ft")) or 0
            away_score = _to_int(row.get("away_score_ft")) or 0

        # Orient every meeting from team_a's perspective so the tallies are
        # comparable regardless of which side was nominally at home.
        a_score, b_score = (home_score, away_score) if home == team_a else (away_score, home_score)
        a_goals += a_score
        b_goals += b_score

        if a_score > b_score:
            a_wins += 1
        elif b_score > a_score:
            b_wins += 1
        else:
            draws += 1

        meetings.append(
            {
                "date": row.get("date"),
                "year": _to_int(row.get("year")),
                "stage": row.get("stage"),
                "home_team": home,
                "away_team": away,
                "home_score": home_score,
                "away_score": away_score,
                "display_score": _display_score(row),
                "winner_team": row.get("winner_team") or None,
                "result_method": row.get("result_method") or None,
            }
        )

    return {
        "team_a": team_a,
        "team_b": team_b,
        "scope": "fifa_world_cup_1930_2026",
        "scope_label": "FIFA World Cup meetings, 1930-2026",
        "total_matches": len(meetings),
        "team_a_wins": a_wins,
        "team_b_wins": b_wins,
        "draws": draws,
        "team_a_goals": a_goals,
        "team_b_goals": b_goals,
        "meetings": meetings,
    }


@lru_cache(maxsize=1)
def build_backtest() -> Dict[str, Any]:
    """The frozen model's WC2026 scorecard, broken down by stage.

    This is a *historical evaluation* of a model frozen before any 2026 result
    was looked at — never a forecast. The API mirrors that framing so the UI
    cannot accidentally present it as one.
    """
    comparison = load_backtest_comparison()
    predictions = load_frozen_predictions()
    matches_by_number = {
        _to_int(row.get("match_number")): row
        for row in load_wc2026_matches()
        if _to_int(row.get("match_number")) is not None
    }
    # The comparison ledger is ordered identically to the prediction CSV
    # (both written in one pass over the same frame), so index alignment is
    # exact; match_number is carried through for the UI to link back.
    numbers = sorted(predictions)

    per_stage: Dict[str, Dict[str, int]] = {}
    matches: List[Dict[str, Any]] = []
    for index, entry in enumerate(comparison.get("matches", [])):
        stage = entry.get("stage", "unknown")
        bucket = per_stage.setdefault(stage, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if entry.get("correct"):
            bucket["correct"] += 1

        number = numbers[index] if index < len(numbers) else None
        prediction = predictions.get(number) if number is not None else None
        row = matches_by_number.get(number, {}) if number is not None else {}
        matches.append(
            {
                "match_number": number,
                "match": entry.get("match"),
                "stage": stage,
                "predicted": entry.get("predicted"),
                "actual": entry.get("actual"),
                "correct": bool(entry.get("correct")),
                "home_win_probability": (prediction or {}).get("home_win_probability"),
                "draw_probability": (prediction or {}).get("draw_probability"),
                "away_win_probability": (prediction or {}).get("away_win_probability"),
                "predicted_score": (prediction or {}).get("most_likely_score"),
                "actual_score": _display_score(row),
            }
        )

    by_stage = [
        {
            "stage": stage,
            "correct": per_stage[stage]["correct"],
            "total": per_stage[stage]["total"],
            "accuracy": round(per_stage[stage]["correct"] / per_stage[stage]["total"], 4)
            if per_stage[stage]["total"]
            else 0.0,
        }
        for stage in STAGE_ORDER
        if stage in per_stage
    ]

    model_version = next(
        (p.get("model_version") for p in predictions.values() if p.get("model_version")),
        None,
    )
    champion = next(
        (
            row.get("winner_team")
            for row in load_wc2026_matches()
            if row.get("stage") == "final" and row.get("winner_team")
        ),
        None,
    )
    predicted_champion = next(
        (
            predictions[number].get("predicted_winner")
            for number in numbers
            if matches_by_number.get(number, {}).get("stage") == "final"
        ),
        None,
    )

    return {
        "model_version": model_version,
        "n_matches_scored": comparison.get("n_matches_scored"),
        "accuracy": comparison.get("accuracy"),
        "correct": sum(bucket["correct"] for bucket in per_stage.values()),
        "by_stage": by_stage,
        "actual_champion": champion,
        "predicted_champion": predicted_champion,
        "note": comparison.get("note"),
        "matches": matches,
    }
