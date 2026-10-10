"""
Data contract for the V3 pipeline.

Source
------
``app/data/raw/international_results/`` -- the open "international_results"
dataset (github.com/martj42/international_results, CC0). ``results.csv`` holds
one row per men's senior full international since 1872; ``shootouts.csv`` holds
the winner of every penalty shoot-out. Provenance (upstream commit, download
date, sha256) is recorded in ``SOURCE.json`` next to the files.

Target population
-----------------
Men's senior "A" internationals. The upstream file contains nothing else at the
age-group/women's level, but it does contain matches between non-FIFA
representative sides (CONIFA tournaments, island games). Those are kept, flagged
``is_fifa_recognised_competition = False``, and given the lowest importance
weight: dropping them would leave gaps in the rating history of teams that also
play FIFA opponents, while the flag lets every evaluation slice exclude them.

Score semantics (the prediction target)
---------------------------------------
Upstream scores are the result **after extra time, excluding penalty
shoot-outs**. That is the target definition used everywhere in V3:

    result = "A" if goals_a > goals_b, "D" if equal, "B" otherwise

so a knockout tie decided on penalties is a draw for the outcome model, and the
shoot-out winner is carried separately in ``shootout_winner``. This matters for
the tournament engine, which samples 90 minutes, extra time and penalties as
three distinct steps, and it means the 90-minute and after-extra-time scores
cannot be told apart in the training data -- a documented limitation, not
something this module papers over.

Team identity
-------------
Upstream already resolves historical names to the current association (West
Germany -> Germany, Soviet Union -> Russia, Zaire -> DR Congo) and keeps
genuinely dissolved teams separate (Yugoslavia, Czechoslovakia). V3 inherits
that policy rather than second-guessing it. The only renaming done here is
``DATASET_TO_REGISTRY``: seven upstream spellings mapped to the names the
application's WC2026 registry uses, verified by set difference -- no fuzzy
matching anywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "international_results"
RESULTS_CSV = RAW_DIR / "results.csv"
SHOOTOUTS_CSV = RAW_DIR / "shootouts.csv"
SOURCE_JSON = RAW_DIR / "SOURCE.json"

# Upstream spelling -> application registry spelling. Exactly the seven names
# for which ``set(registry) - set(upstream)`` was non-empty.
DATASET_TO_REGISTRY: dict[str, str] = {
    "United States": "USA",
    "Cape Verde": "Cabo Verde",
    "DR Congo": "Congo DR",
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire",
    "Iran": "IR Iran",
    "Turkey": "Türkiye",
}
REGISTRY_TO_DATASET = {v: k for k, v in DATASET_TO_REGISTRY.items()}

# ── Competition importance ───────────────────────────────────────────────────
# Tiers follow the World Football Elo convention (eloratings.net): the weight a
# result carries grows with how much the match was worth. The absolute K is a
# tuned hyper-parameter (ratings.EloConfig.k_scale); only the *ratios* live here.
TIER_WORLD_CUP = 5          # World Cup finals
TIER_CONTINENTAL = 4        # continental championship finals, Confederations Cup
TIER_QUALIFIER = 3          # World Cup / continental qualifiers, Nations League
TIER_MINOR_TOURNAMENT = 2   # every other tournament
TIER_FRIENDLY = 1           # friendlies and non-FIFA competitions

TIER_WEIGHT = {5: 60.0, 4: 50.0, 3: 40.0, 2: 30.0, 1: 20.0}

_CONTINENTAL_FINALS = {
    "UEFA Euro", "Copa América", "African Cup of Nations", "AFC Asian Cup",
    "Gold Cup", "CONCACAF Championship", "Oceania Nations Cup",
    "Confederations Cup", "CONMEBOL–UEFA Cup of Champions",
}
_NATIONS_LEAGUES = {"UEFA Nations League", "CONCACAF Nations League"}


def competition_tier(tournament: str) -> int:
    t = tournament.strip()
    if t == "FIFA World Cup":
        return TIER_WORLD_CUP
    if t in _CONTINENTAL_FINALS:
        return TIER_CONTINENTAL
    if t == "Friendly" or "CONIFA" in t or "ConIFA" in t:
        return TIER_FRIENDLY
    if "qualification" in t or t in _NATIONS_LEAGUES:
        return TIER_QUALIFIER
    return TIER_MINOR_TOURNAMENT


def is_fifa_recognised(tournament: str) -> bool:
    t = tournament.lower()
    return not any(k in t for k in ("conifa", "island games", "viva world cup", "inter games"))


# ── Validation ───────────────────────────────────────────────────────────────

@dataclass
class ValidationReport:
    rows_in: int = 0
    rows_out: int = 0
    issues: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, key: str, n: int) -> None:
        if n:
            self.issues[key] = self.issues.get(key, 0) + int(n)

    def to_dict(self) -> dict[str, Any]:
        return {"rows_in": self.rows_in, "rows_out": self.rows_out,
                "issues": self.issues, "notes": self.notes}


def _match_id(date: str, a: str, b: str, tournament: str, seq: int) -> str:
    raw = f"{date}|{a}|{b}|{tournament}|{seq}"
    return "m_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]


def load_matches(
    results_csv: Path = RESULTS_CSV,
    shootouts_csv: Path = SHOOTOUTS_CSV,
    return_report: bool = False,
):
    """
    Load, validate and normalise the match corpus.

    Returns a frame sorted by (date, upstream row order) with one row per match
    and the columns of the data contract. Rows that violate a hard rule
    (unparseable date, missing/negative score, a team playing itself) are
    dropped and counted; nothing is repaired by guessing.
    """
    rep = ValidationReport()
    raw = pd.read_csv(results_csv, encoding="utf-8")
    rep.rows_in = len(raw)
    raw["_row"] = np.arange(len(raw))

    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    bad_date = raw["date"].isna()
    rep.add("invalid_date_dropped", bad_date.sum())

    for c in ("home_score", "away_score"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    bad_score = raw["home_score"].isna() | raw["away_score"].isna() | (raw["home_score"] < 0) | (raw["away_score"] < 0)
    rep.add("missing_or_negative_score_dropped", (bad_score & ~bad_date).sum())

    self_match = raw["home_team"].astype(str).str.strip() == raw["away_team"].astype(str).str.strip()
    rep.add("team_plays_itself_dropped", self_match.sum())

    blank_team = raw["home_team"].isna() | raw["away_team"].isna()
    rep.add("missing_team_dropped", blank_team.sum())

    df = raw[~(bad_date | bad_score | self_match | blank_team)].copy()

    implausible = (df["home_score"] > 20) | (df["away_score"] > 20)
    rep.add("score_above_20_kept_flagged", implausible.sum())

    df["team_a"] = df["home_team"].str.strip().replace(DATASET_TO_REGISTRY)
    df["team_b"] = df["away_team"].str.strip().replace(DATASET_TO_REGISTRY)
    df["goals_a"] = df["home_score"].astype(int)
    df["goals_b"] = df["away_score"].astype(int)
    df["tournament"] = df["tournament"].astype(str).str.strip()
    df["venue_country"] = df["country"].astype(str).str.strip().replace(DATASET_TO_REGISTRY)

    neutral = df["neutral"].astype(str).str.strip().str.upper().isin(("TRUE", "1"))
    # venue: +1 team_a is at home, 0 neutral. Upstream never lists the home side
    # second, so -1 only ever arises when a caller swaps the orientation.
    df["venue"] = np.where(neutral, 0, 1).astype(int)
    df["neutral"] = neutral
    df["a_is_host_country"] = df["venue_country"] == df["team_a"]
    df["b_is_host_country"] = df["venue_country"] == df["team_b"]
    rep.add("neutral_flag_but_team_a_in_own_country", (neutral & df["a_is_host_country"]).sum())
    rep.add("home_flag_but_venue_country_differs", (~neutral & ~df["a_is_host_country"]).sum())

    df["tier"] = df["tournament"].map(competition_tier).astype(int)
    df["importance"] = df["tier"].map(TIER_WEIGHT).astype(float)
    df["is_fifa_recognised_competition"] = df["tournament"].map(is_fifa_recognised)

    df["result"] = np.where(df.goals_a > df.goals_b, "A", np.where(df.goals_a < df.goals_b, "B", "D"))

    df = df.sort_values(["date", "_row"], kind="stable").reset_index(drop=True)

    # Same teams, same day, same competition: two legitimate matches exist in
    # the source (Tahiti v New Caledonia, 1974-02-17). Keep both, disambiguated
    # by a sequence number, and report the count instead of deleting either.
    key = df["date"].dt.strftime("%Y-%m-%d") + "|" + df.team_a + "|" + df.team_b + "|" + df.tournament
    df["_seq"] = df.groupby(key).cumcount()
    rep.add("same_day_same_fixture_pairs_kept", (df["_seq"] > 0).sum())
    df["match_id"] = [
        _match_id(d.strftime("%Y-%m-%d"), a, b, t, s)
        for d, a, b, t, s in zip(df.date, df.team_a, df.team_b, df.tournament, df._seq)
    ]
    assert df["match_id"].is_unique

    # Shoot-outs: who advanced when the recorded score was level.
    df["shootout_winner"] = None
    if shootouts_csv.exists():
        so = pd.read_csv(shootouts_csv, encoding="utf-8")
        so["date"] = pd.to_datetime(so["date"], errors="coerce")
        for c in ("home_team", "away_team", "winner"):
            so[c] = so[c].astype(str).str.strip().replace(DATASET_TO_REGISTRY)
        so = so.dropna(subset=["date"]).drop_duplicates(["date", "home_team", "away_team"])
        merged = df.merge(
            so[["date", "home_team", "away_team", "winner"]],
            left_on=["date", "team_a", "team_b"], right_on=["date", "home_team", "away_team"],
            how="left", suffixes=("", "_so"),
        )
        df["shootout_winner"] = merged["winner"].where(merged["winner"].notna(), None).values
        rep.add("shootout_rows_unmatched_to_a_result", len(so) - df["shootout_winner"].notna().sum())
        not_level = df["shootout_winner"].notna() & (df.goals_a != df.goals_b)
        rep.add("shootout_recorded_but_score_not_level", not_level.sum())

    df["source"] = "martj42/international_results"
    df["source_row"] = df["_row"].astype(int)

    cols = [
        "match_id", "date", "team_a", "team_b", "goals_a", "goals_b", "result",
        "shootout_winner", "tournament", "tier", "importance",
        "is_fifa_recognised_competition", "venue", "neutral", "venue_country",
        "a_is_host_country", "b_is_host_country", "source", "source_row",
    ]
    out = df[cols].copy()
    rep.rows_out = len(out)
    rep.notes.append("scores are after extra time and exclude penalty shoot-outs (upstream definition)")
    rep.notes.append("kick-off times are not in the source; ordering within a day follows upstream row order")
    return (out, rep) if return_report else out


@lru_cache(maxsize=1)
def source_provenance() -> dict[str, Any]:
    if SOURCE_JSON.exists():
        return json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    return {}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_fingerprint() -> str:
    """Identifies the exact data snapshot a model was trained on."""
    return file_sha256(RESULTS_CSV)[:16]
