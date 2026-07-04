"""
Generate database/seed_wc2026.sql from the Data Engineering wave's processed
CSVs:
    backend/app/data/processed/teams_reference.csv
    backend/app/data/processed/matches_historical.csv
    backend/app/data/processed/match_team_stats.csv

This script does NOT connect to any database -- it is a pure text generator.
Run it locally, review the generated SQL, then execute seed_wc2026.sql
yourself against your Supabase/Postgres instance (e.g. via the Supabase SQL
editor or `psql -f database/seed_wc2026.sql`).

Usage:
    python database/generate_seed_wc2026.py

Requires: schema.sql (or migrations/002_wc2026_upgrade.sql) already applied
--  the target tables (teams, tournament_stages, matches, team_statistics)
must exist first.

Design notes
------------
- All three source CSVs have a UTF-8 BOM (mojibake-fixed by the Data
  Engineering wave, but the BOM byte itself remains) -- read with
  encoding='utf-8-sig' to strip it; a plain 'utf-8' read would leave a
  stray U+FEFF prepended to the first column's first value.
- Teams: teams_reference.csv's 48 rows become teams with rankings/elo
  populated. Additionally, every team name that appears in
  matches_historical.csv's home_team/away_team columns but is NOT one of
  the 48 (24 historical-only teams, e.g. "Italy", "Russia", "Wales") is
  also inserted, with confederation/fifa_ranking/elo_rating/fifa_code/
  wc2026_group left NULL -- they are real teams, just outside the 2026
  field, so no ranking data exists for them in our source data. This is
  NOT fabrication; it's a straightforward NULL for "unknown".
- The literal string "Unknown" (matches_historical.csv match_id=89's TBD
  Round-of-16 opponent placeholder) is explicitly excluded from the teams
  insert list and mapped to SQL NULL for away_team_id on that one match --
  it is a placeholder token in the source data, not a real team.
- Matches: all 419 rows from matches_historical.csv. team names are
  resolved to team rows by exact name match (case-sensitive; the Data
  Engineering wave already canonicalized names across all sources, see
  DATA_QUALITY_REPORT.md section (b)). tournament is synthesized as
  "FIFA World Cup {year}" since matches_historical.csv doesn't carry a
  separate tournament-name column (unlike the old broad seed.sql). venue
  is split into venue/city where the source has "Stadium, City" (2002-2022
  rows); 2026 rows have empty venue/city in the source (documented gap,
  DATA_QUALITY_REPORT.md) and are emitted as SQL NULL, not fabricated.
- team_statistics: all 132 rows from match_team_stats.csv, joined to
  matches via matches.external_match_id (only the 2026 matches have this
  populated with the same small-integer id space match_team_stats uses)
  and to teams via team name.
- Idempotency: matches and team_statistics use ON CONFLICT DO NOTHING
  against unique keys (external_match_id; match_id+team_name resolved to
  UUIDs at insert time via subqueries, so nothing needs a client-side
  UUID cache).
"""

import csv
import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "backend" / "app" / "data" / "processed"
OUTPUT_PATH = REPO_ROOT / "database" / "seed_wc2026.sql"

TEAMS_CSV = PROCESSED_DIR / "teams_reference.csv"
MATCHES_CSV = PROCESSED_DIR / "matches_historical.csv"
STATS_CSV = PROCESSED_DIR / "match_team_stats.csv"

UNKNOWN_TEAM_TOKEN = "Unknown"  # TBD-opponent placeholder, not a real team


def sql_str(value):
    """Render a Python value as a SQL literal: NULL for empty/None, else a
    single-quoted, escaped string literal."""
    if value is None or value == "":
        return "NULL"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def sql_int(value):
    if value is None or value == "":
        return "NULL"
    # Source scores/ranks are sometimes float-formatted strings ("0.0")
    return str(int(float(value)))


def sql_bool_default_false():
    return "FALSE"


def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_venue_city(venue_field):
    """matches_historical.csv 'venue' for 2002-2022 rows looks like
    'Seoul World Cup Stadium, Seoul' (stadium, city). Split on the last
    comma. Returns (venue_name, city) with either possibly None."""
    if not venue_field:
        return None, None
    if "," in venue_field:
        stadium, _, city = venue_field.rpartition(",")
        return stadium.strip(), city.strip()
    return venue_field.strip(), None


def main():
    teams_ref = load_csv(TEAMS_CSV)
    matches = load_csv(MATCHES_CSV)
    stats = load_csv(STATS_CSV)

    wc2026_names = {r["canonical_name"] for r in teams_ref}

    # Collect every distinct team name referenced in matches (home/away),
    # excluding the TBD placeholder token.
    all_match_team_names = set()
    for m in matches:
        if m["home_team"] and m["home_team"] != UNKNOWN_TEAM_TOKEN:
            all_match_team_names.add(m["home_team"])
        if m["away_team"] and m["away_team"] != UNKNOWN_TEAM_TOKEN:
            all_match_team_names.add(m["away_team"])

    historical_only_names = sorted(all_match_team_names - wc2026_names)

    lines = []
    lines.append("-- ============================================================")
    lines.append("-- WC 2026 Seed Data — GENERATED FILE, do not hand-edit")
    lines.append("-- Generated by database/generate_seed_wc2026.py from:")
    lines.append("--   backend/app/data/processed/teams_reference.csv")
    lines.append("--   backend/app/data/processed/matches_historical.csv")
    lines.append("--   backend/app/data/processed/match_team_stats.csv")
    lines.append("--")
    lines.append("-- This is the source of truth for WC match-history seed data,")
    lines.append("-- superseding database/seed.sql's broad 1872-2017 dataset for this")
    lines.append("-- WC-2026-focused upgrade (see comment at the top of seed.sql).")
    lines.append("--")
    lines.append("-- Run AFTER database/schema.sql (or migrations/002_wc2026_upgrade.sql)")
    lines.append("-- has been applied. Safe to re-run: all inserts use ON CONFLICT.")
    lines.append("-- ============================================================")
    lines.append("")
    lines.append("BEGIN;")
    lines.append("")

    # ─── Teams: the 48 WC2026 teams with rankings/elo/fifa_code/group ────────
    lines.append("-- ─── Teams: WC2026 field (48 teams, with rankings/elo/fifa_code/group) ───")
    for r in teams_ref:
        name = r["canonical_name"]
        confed = r["confederation"]
        fifa_rank = r["fifa_ranking_pre_tournament"]
        elo = r["elo_rating"]
        code = r["fifa_code"]
        group = r["group"]
        lines.append(
            "INSERT INTO teams (name, country, confederation, fifa_ranking, elo_rating, "
            "fifa_code, wc2026_group, ranking_updated_at) VALUES "
            f"({sql_str(name)}, {sql_str(name)}, {sql_str(confed)}, {sql_int(fifa_rank)}, "
            f"{sql_int(elo)}, {sql_str(code)}, {sql_str(group)}, NOW()) "
            "ON CONFLICT (name) DO UPDATE SET "
            "confederation = EXCLUDED.confederation, "
            "fifa_ranking = EXCLUDED.fifa_ranking, "
            "elo_rating = EXCLUDED.elo_rating, "
            "fifa_code = EXCLUDED.fifa_code, "
            "wc2026_group = EXCLUDED.wc2026_group, "
            "ranking_updated_at = NOW();"
        )
    lines.append("")

    # ─── Teams: historical-only teams (no ranking/elo data available) ────────
    lines.append("-- ─── Teams: historical-only (2002-2022), no WC2026 ranking/elo data ───")
    lines.append(f"-- {len(historical_only_names)} teams: real nations outside the 2026 field;")
    lines.append("-- confederation/fifa_ranking/elo_rating/fifa_code/wc2026_group are genuinely")
    lines.append("-- unknown from our source data (NULL), not fabricated.")
    for name in historical_only_names:
        lines.append(
            f"INSERT INTO teams (name, country) VALUES ({sql_str(name)}, {sql_str(name)}) "
            "ON CONFLICT (name) DO NOTHING;"
        )
    lines.append("")

    # ─── Matches ──────────────────────────────────────────────────────────────
    lines.append("-- ─── Matches: 419 rows (330 historical 2002-2022 + 89 WC2026 real matches) ───")
    n_matches = 0
    n_skipped = 0
    for m in matches:
        match_id = m["match_id"]
        home_team = m["home_team"]
        away_team = m["away_team"]
        home_score = m["home_score"]
        away_score = m["away_score"]
        date = m["date"]
        stage_key = m["stage"]
        tournament_year = m["tournament_year"]
        venue_field = m["venue"]
        city_field = m["city"]
        home_xg = m["home_xg"]
        away_xg = m["away_xg"]
        source = m["source"]
        status_raw = m["status"]

        if not home_team or home_team == UNKNOWN_TEAM_TOKEN:
            # No known case in the data today (home_team is always populated),
            # but guard defensively rather than insert a bogus row.
            n_skipped += 1
            continue

        away_team_expr = "NULL" if (not away_team or away_team == UNKNOWN_TEAM_TOKEN) else (
            f"(SELECT id FROM teams WHERE name = {sql_str(away_team)})"
        )

        venue_name, venue_city = split_venue_city(venue_field)
        # matches_historical.csv also carries an explicit 'city' column
        # (always empty in this dataset per DATA_QUALITY_REPORT.md — 2026
        # venue/city intentionally left null); prefer it if ever populated,
        # else fall back to the city parsed out of 'venue'.
        city_value = city_field or venue_city

        status = {"Completed": "completed", "Scheduled": "scheduled"}.get(status_raw, "completed")

        tournament_name = f"FIFA World Cup {tournament_year}"

        lines.append(
            "INSERT INTO matches (date, home_team_id, away_team_id, home_score, away_score, "
            "tournament, stage, tournament_year, city, home_xg, away_xg, external_match_id, "
            "data_source, status) VALUES ("
            f"{sql_str(date)}, "
            f"(SELECT id FROM teams WHERE name = {sql_str(home_team)}), "
            f"{away_team_expr}, "
            f"{sql_int(home_score)}, {sql_int(away_score)}, "
            f"{sql_str(tournament_name)}, {sql_str(stage_key)}, {sql_int(tournament_year)}, "
            f"{sql_str(city_value)}, "
            f"{home_xg if home_xg else 'NULL'}, {away_xg if away_xg else 'NULL'}, "
            f"{sql_str(match_id)}, {sql_str(source)}, {sql_str(status)}"
            ") ON CONFLICT (external_match_id) WHERE external_match_id IS NOT NULL DO NOTHING;"
        )
        n_matches += 1
    lines.append("")

    # Backfill stage_id from tournament_stages now that matches are loaded
    # (stage_key values used above already match tournament_stages.stage_key
    # exactly for every row in matches_historical.csv, so this is a full
    # backfill, not best-effort).
    lines.append("-- Backfill normalized stage_id from tournament_stages (stage_key matches exactly)")
    lines.append(
        "UPDATE matches m SET stage_id = ts.stage_id FROM tournament_stages ts "
        "WHERE m.stage_id IS NULL AND m.stage = ts.stage_key "
        "AND m.external_match_id IS NOT NULL;"
    )
    lines.append("")

    # ─── Team Statistics ──────────────────────────────────────────────────────
    lines.append("-- ─── Team Statistics: 132 rows (66 of 76 completed 2026 matches x 2 teams) ───")
    lines.append("-- Joined to matches via external_match_id (only 2026 matches have this set to")
    lines.append("-- the same small-integer id space match_team_stats.csv uses) and to teams via")
    lines.append("-- team_name. 10 completed matches have no stats rows in the source -- not")
    lines.append("-- inserted here, not fabricated (see DATA_QUALITY_REPORT.md).")
    n_stats = 0
    for s in stats:
        match_id = s["match_id"]
        team_name = s["team_name"]
        possession = s["possession_pct"]
        shots = s["total_shots"]
        shots_on_target = s["shots_on_target"]
        corners = s["corners"]
        fouls = s["fouls"]
        offsides = s["offsides"]
        saves = s["saves"]
        potm = s["player_of_the_match"]

        lines.append(
            "INSERT INTO team_statistics (match_id, team_id, possession_pct, total_shots, "
            "shots_on_target, corners, fouls, offsides, saves, player_of_the_match) VALUES ("
            f"(SELECT id FROM matches WHERE external_match_id = {sql_str(match_id)}), "
            f"(SELECT id FROM teams WHERE name = {sql_str(team_name)}), "
            f"{sql_int(possession)}, {sql_int(shots)}, {sql_int(shots_on_target)}, "
            f"{sql_int(corners)}, {sql_int(fouls)}, {sql_int(offsides)}, {sql_int(saves)}, "
            f"{sql_str(potm)}"
            ") ON CONFLICT (match_id, team_id) DO NOTHING;"
        )
        n_stats += 1
    lines.append("")

    lines.append("COMMIT;")
    lines.append("")
    lines.append("-- ─── Verification ─────────────────────────────────────────────────────────")
    lines.append(f"-- Expect: teams >= {len(teams_ref) + len(historical_only_names)}, "
                  f"matches with external_match_id = {n_matches}, team_statistics = {n_stats}")
    lines.append("SELECT COUNT(*) AS total_teams FROM teams;")
    lines.append("SELECT COUNT(*) AS wc2026_teams FROM teams WHERE fifa_code IS NOT NULL;")
    lines.append("SELECT COUNT(*) AS seeded_matches FROM matches WHERE external_match_id IS NOT NULL;")
    lines.append("SELECT COUNT(*) AS total_team_statistics FROM team_statistics;")
    lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH}")
    print(f"  teams (WC2026): {len(teams_ref)}")
    print(f"  teams (historical-only): {len(historical_only_names)}")
    print(f"  matches: {n_matches} (skipped: {n_skipped})")
    print(f"  team_statistics: {n_stats}")


if __name__ == "__main__":
    main()
