"""
FIFA World Cup 2026 reference data loader.
=========================================

Thin, dependency-free accessors for the static reference data checked into
this directory (``groups.json``, ``schedule.json``, ``venues.json``). See
``README.md`` in this directory for provenance and documented assumptions.

These functions read from disk relative to this module's own location
(``pathlib.Path(__file__).parent``), so they work regardless of the current
working directory the app is started from.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parent

_GROUPS_PATH = _DATA_DIR / "groups.json"
_SCHEDULE_PATH = _DATA_DIR / "schedule.json"
_VENUES_PATH = _DATA_DIR / "venues.json"


@lru_cache(maxsize=1)
def load_groups() -> Dict[str, List[Dict[str, str]]]:
    """
    Load the official 12 FIFA World Cup 2026 groups (A-L), 4 teams each.

    Returns a dict mapping group letter -> list of {"code": ..., "name": ...}.
    """
    with open(_GROUPS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_schedule() -> List[Dict[str, Any]]:
    """Load all 104 official FIFA World Cup 2026 fixtures."""
    with open(_SCHEDULE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_venues() -> Dict[str, Any]:
    """Load the 16 host cities and their region groupings."""
    with open(_VENUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_groups_as_team_codes() -> Dict[str, List[str]]:
    """
    Convenience accessor returning groups as {"A": ["MEX", "RSA", ...], ...}
    i.e. team codes only, suitable for feeding directly into
    ``TournamentSimulator.simulate_tournament``.
    """
    groups = load_groups()
    return {group_name: [team["code"] for team in teams] for group_name, teams in groups.items()}


def filter_schedule(
    stage: Optional[str] = None,
    venue_city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return schedule fixtures optionally filtered by stage and/or venue_city."""
    matches = load_schedule()

    if stage is not None:
        matches = [m for m in matches if m.get("stage") == stage]

    if venue_city is not None:
        matches = [m for m in matches if m.get("venue_city") == venue_city]

    return matches
