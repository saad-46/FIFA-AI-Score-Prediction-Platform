"""
V2 feature-engine data sources: Supabase (production) and local CSV (dev).

Production inference must not depend on a CSV that may not exist in the
deployed container, so the default source is the Supabase v2 tables. The CSV
snapshot remains available as a development/offline fallback and — more
usefully — as the reference the Supabase loader is verified against
(see ``verify_consistency``).

Both loaders return frames with IDENTICAL schema, dtypes and row order to
``app.ml.v2.features.load_canonical``. That is the whole contract: the feature
engine must not be able to tell which source it was given. Anything less and
"switching to Supabase" silently becomes "changing the model's inputs".

Read-only: SELECT statements exclusively. Nothing here writes, alters or
deletes any table.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

CANON_DIR = Path(__file__).resolve().parents[2] / "data" / "canonical"
SourceName = Literal["supabase", "csv"]

# Column order must match canonical_matches.csv exactly so that downstream
# positional assumptions (and diffing against the CSV) stay valid.
_MATCH_COLUMNS = [
    "match_id", "date", "year", "tournament", "competition_type", "stage",
    "is_knockout", "stage_order", "match_number", "group_name",
    "home_team", "away_team",
    "home_score_ft", "away_score_ft", "home_score_et", "away_score_et",
    "home_penalties", "away_penalties", "result", "winner_team",
    "result_method", "is_replay", "venue", "city", "host_country",
    "home_is_host", "away_is_host", "neutral_venue", "kickoff_time_et",
    "attendance", "referee", "notes", "source_dataset", "source_file",
    "match_number_source",
]
_TEAM_COLUMNS = [
    "team_name", "fifa_code", "confederation", "wc2026_group",
    "fifa_ranking_pre_wc2026", "elo_rating_pre_wc2026", "is_wc2026_team",
    "matches_played", "first_match", "last_match",
]
_STAT_COLUMNS = [
    "match_id", "date", "team", "opponent", "is_home", "possession", "sot",
    "total_shots", "saves", "cards_yellow", "cards_red", "fouls", "corners",
    "crosses", "interceptions", "offsides", "formation", "manager", "captain",
]


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_file = Path(__file__).resolve().parents[3] / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not url:
        raise RuntimeError("DATABASE_URL not set — cannot use the Supabase V2 data source")
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


# ---------------------------------------------------------------- CSV source
def load_from_csv() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Local canonical snapshot — the development/offline source."""
    matches = pd.read_csv(CANON_DIR / "canonical_matches.csv", encoding="utf-8-sig")
    teams = pd.read_csv(CANON_DIR / "canonical_teams.csv", encoding="utf-8-sig")
    stats = pd.read_csv(CANON_DIR / "canonical_match_stats.csv", encoding="utf-8-sig")
    return _normalise(matches, teams, stats)


# ----------------------------------------------------------- Supabase source
_MATCH_SQL = """
SELECT m.match_id,
       m.match_date::text                AS date,
       m.tournament_year                 AS year,
       m.tournament, m.competition_type, m.stage, m.is_knockout, m.stage_order,
       m.match_number, m.group_name,
       ht.team_name                      AS home_team,
       at.team_name                      AS away_team,
       m.home_score_ft, m.away_score_ft, m.home_score_et, m.away_score_et,
       m.home_penalties, m.away_penalties, m.result,
       wt.team_name                      AS winner_team,
       m.result_method, m.is_replay, m.venue, m.city, m.host_country,
       m.home_is_host, m.away_is_host, m.neutral_venue, m.kickoff_time_et,
       m.attendance, m.referee, m.notes, m.source_dataset, m.source_file,
       m.match_number_source
FROM public.matches_v2 m
JOIN public.teams_v2 ht ON ht.id = m.home_team_id
JOIN public.teams_v2 at ON at.id = m.away_team_id
LEFT JOIN public.teams_v2 wt ON wt.id = m.winner_team_id
"""

_TEAM_SQL = """
SELECT team_name, fifa_code, confederation, wc2026_group,
       fifa_ranking_pre_wc2026, elo_rating_pre_wc2026, is_wc2026_team,
       matches_played, first_match::text AS first_match,
       last_match::text  AS last_match
FROM public.teams_v2
"""

_STAT_SQL = """
SELECT s.match_id,
       m.match_date::text  AS date,
       t.team_name         AS team,
       o.team_name         AS opponent,
       s.is_home, s.possession,
       s.shots_on_target   AS sot,
       s.total_shots, s.saves, s.cards_yellow, s.cards_red, s.fouls,
       s.corners, s.crosses, s.interceptions, s.offsides,
       s.formation, s.manager, s.captain
FROM public.match_statistics_v2 s
JOIN public.matches_v2 m ON m.match_id = s.match_id
JOIN public.teams_v2 t   ON t.id = s.team_id
JOIN public.teams_v2 o   ON o.id = s.opponent_id
"""


def load_from_supabase() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the canonical corpus from the Supabase V2 tables (read-only)."""
    # A SQLAlchemy engine rather than a raw psycopg2 connection: pandas only
    # officially supports SQLAlchemy connectables, and the rest of this
    # codebase is already SQLAlchemy-based.
    from sqlalchemy import create_engine

    engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            matches = pd.read_sql_query(_MATCH_SQL, conn)
            teams = pd.read_sql_query(_TEAM_SQL, conn)
            stats = pd.read_sql_query(_STAT_SQL, conn)
    finally:
        engine.dispose()
    return _normalise(matches, teams, stats)


# ------------------------------------------------------------- normalisation
def _normalise(matches, teams, stats):
    """
    Force both sources onto identical schema, dtype and ordering.

    Postgres returns real NULLs and native bools/ints where the CSV round-trip
    produces NaN and object/float columns. Without this the two sources would
    differ in ways that never show up as an error but do change feature values
    — the exact failure the consistency check exists to prevent.
    """
    matches = matches.reindex(columns=_MATCH_COLUMNS)
    teams = teams.reindex(columns=_TEAM_COLUMNS)
    stats = stats.reindex(columns=_STAT_COLUMNS)

    matches["date"] = pd.to_datetime(matches["date"])
    matches["year"] = matches["year"].astype(int)
    for col in ("is_knockout", "is_replay", "home_is_host", "away_is_host", "neutral_venue"):
        matches[col] = matches[col].map(_to_bool).astype(bool)
    for col in ("home_score_ft", "away_score_ft", "home_score_et", "away_score_et",
                "home_penalties", "away_penalties", "match_number", "stage_order",
                "attendance"):
        matches[col] = pd.to_numeric(matches[col], errors="coerce")
    for col in ("group_name", "winner_team", "result_method", "venue", "city",
                "host_country", "kickoff_time_et", "referee", "notes",
                "match_number_source", "result"):
        matches[col] = matches[col].astype(object).where(matches[col].notna(), None)

    # The feature engine sorts by (date, match_id); applying it here means both
    # sources are byte-comparable rather than merely set-equal.
    matches = matches.sort_values(["date", "match_id"]).reset_index(drop=True)

    teams["is_wc2026_team"] = teams["is_wc2026_team"].map(_to_bool).astype(bool)
    for col in ("fifa_ranking_pre_wc2026", "elo_rating_pre_wc2026", "matches_played"):
        teams[col] = pd.to_numeric(teams[col], errors="coerce")
    teams = teams.sort_values("team_name").reset_index(drop=True)

    stats["is_home"] = stats["is_home"].map(_to_bool).astype(bool)
    for col in ("possession", "sot", "total_shots", "saves", "cards_yellow",
                "cards_red", "fouls", "corners", "crosses", "interceptions", "offsides"):
        stats[col] = pd.to_numeric(stats[col], errors="coerce")
    stats = stats.sort_values(["match_id", "team"]).reset_index(drop=True)

    # Decisive score, same rule the CSV path uses: extra time where played.
    matches["home_goals"] = matches["home_score_et"].fillna(matches["home_score_ft"])
    matches["away_goals"] = matches["away_score_et"].fillna(matches["away_score_ft"])
    return matches, teams, stats


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    return str(v).strip().lower() in ("true", "t", "1", "yes")


# ------------------------------------------------------------------ dispatch
def load_canonical_from(source: SourceName) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if source == "supabase":
        return load_from_supabase()
    if source == "csv":
        return load_from_csv()
    raise ValueError(f"unknown V2 data source: {source!r}")


# -------------------------------------------------------------- consistency
def verify_consistency(sample_size: int = 25) -> dict:
    """
    Prove the two sources are interchangeable before production relies on it.

    Compares counts, team/tournament cardinality, date ranges, and then — the
    part that actually matters — real feature vectors built independently from
    each source for a sample of matches. Equal row counts with different
    feature values would be a silent model change, so the feature comparison
    is the pass/fail criterion, not the counts.
    """
    from app.ml.v2.features import build_dataset, feature_columns

    csv_m, csv_t, csv_s = load_from_csv()
    sb_m, sb_t, sb_s = load_from_supabase()

    report: dict = {"checks": {}, "passed": True}

    def check(name: str, csv_val, sb_val):
        ok = csv_val == sb_val
        report["checks"][name] = {"csv": csv_val, "supabase": sb_val, "match": ok}
        if not ok:
            report["passed"] = False

    check("match_rows", len(csv_m), len(sb_m))
    check("team_rows", len(csv_t), len(sb_t))
    check("stat_rows", len(csv_s), len(sb_s))
    check("distinct_teams", int(csv_m[["home_team", "away_team"]].stack().nunique()),
          int(sb_m[["home_team", "away_team"]].stack().nunique()))
    check("distinct_tournaments", int(csv_m["year"].nunique()), int(sb_m["year"].nunique()))
    check("earliest_date", str(csv_m["date"].min().date()), str(sb_m["date"].min().date()))
    check("latest_date", str(csv_m["date"].max().date()), str(sb_m["date"].max().date()))
    check("wc2026_teams", int(csv_t["is_wc2026_team"].sum()), int(sb_t["is_wc2026_team"].sum()))
    check("match_id_set", sorted(csv_m["match_id"]) == sorted(sb_m["match_id"]), True)
    check("total_goals", float(csv_m["home_goals"].sum(skipna=True)),
          float(sb_m["home_goals"].sum(skipna=True)))

    # per-tournament row counts
    csv_by_year = csv_m["year"].value_counts().sort_index().to_dict()
    sb_by_year = sb_m["year"].value_counts().sort_index().to_dict()
    report["checks"]["per_tournament_counts"] = {
        "match": csv_by_year == sb_by_year,
        "csv": {str(k): int(v) for k, v in csv_by_year.items()},
        "supabase": {str(k): int(v) for k, v in sb_by_year.items()},
    }
    if csv_by_year != sb_by_year:
        report["passed"] = False

    # ---- feature-state equality (the real test) ---------------------------
    groups = ("strength", "form", "history", "context")
    csv_feats = build_dataset(csv_m, csv_t, csv_s, groups=groups)
    sb_feats = build_dataset(sb_m, sb_t, sb_s, groups=groups)
    cols = feature_columns(csv_feats)

    same_cols = cols == feature_columns(sb_feats)
    report["checks"]["feature_columns_identical"] = {
        "match": same_cols, "n_features": len(cols)}
    if not same_cols:
        report["passed"] = False
        return report

    rng = pd.Series(range(len(csv_feats)))
    idx = rng.sample(n=min(sample_size, len(rng)), random_state=42).tolist()
    a = csv_feats.iloc[idx][cols].to_numpy(dtype=float)
    b = sb_feats.iloc[idx][cols].to_numpy(dtype=float)
    both_nan = pd.isna(a) & pd.isna(b)
    close = (abs(a - b) <= 1e-9) | both_nan
    mismatches = int((~close).sum())

    report["checks"]["sampled_feature_values"] = {
        "match": mismatches == 0,
        "sampled_matches": len(idx),
        "values_compared": int(a.size),
        "mismatched_values": mismatches,
    }
    if mismatches:
        report["passed"] = False
        bad = [{"row": int(idx[r]), "feature": cols[c],
                "csv": float(a[r, c]), "supabase": float(b[r, c])}
               for r, c in zip(*(~close).nonzero())][:10]
        report["checks"]["sampled_feature_values"]["examples"] = bad

    # full-frame equality across every match, not just the sample
    full_a = csv_feats[cols].to_numpy(dtype=float)
    full_b = sb_feats[cols].to_numpy(dtype=float)
    full_close = (abs(full_a - full_b) <= 1e-9) | (pd.isna(full_a) & pd.isna(full_b))
    full_mismatch = int((~full_close).sum())
    report["checks"]["all_feature_values"] = {
        "match": full_mismatch == 0,
        "values_compared": int(full_a.size),
        "mismatched_values": full_mismatch,
    }
    if full_mismatch:
        report["passed"] = False

    return report


if __name__ == "__main__":
    import json
    print(json.dumps(verify_consistency(), indent=2, default=str))
