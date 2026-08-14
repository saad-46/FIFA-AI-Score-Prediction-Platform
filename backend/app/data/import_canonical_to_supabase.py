"""
Import the validated canonical v2 dataset into the Supabase staging tables.

Writes ONLY to the v2 staging tables:
    teams_v2, matches_v2, match_statistics_v2, wc2026_tournament_graph

The legacy production tables (matches, teams, team_statistics) are never read,
written, altered or deleted by this script. Every insert is idempotent via
ON CONFLICT DO NOTHING, so re-running is safe.

Refuses to run unless validation_report.json reports PASS.

Usage:
    backend/venv/Scripts/python.exe -m app.data.import_canonical_to_supabase [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = Path(__file__).resolve().parent
CANON = DATA_DIR / "canonical"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not url:
        sys.exit("DATABASE_URL not found in environment or backend/.env")
    # SQLAlchemy-style driver suffixes are not understood by psycopg2
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def i(value):
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "None", "NULL"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def s(value):
    if value is None:
        return None
    v = str(value).strip()
    return v or None


def b(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="roll back instead of committing")
    args = ap.parse_args()

    report = json.loads((CANON / "validation_report.json").read_text(encoding="utf-8"))
    if report.get("result") != "PASS":
        sys.exit(f"validation did not pass ({report.get('result')}): {report.get('failures')}")
    print(f"validation report: PASS ({report['counts']['total_matches']} matches)")

    teams = read_csv(CANON / "canonical_teams.csv")
    matches = read_csv(CANON / "canonical_matches.csv")
    stats = read_csv(CANON / "canonical_match_stats.csv")
    graph = json.loads((CANON / "wc2026_tournament_graph.json").read_text(encoding="utf-8"))

    conn = psycopg2.connect(load_database_url())
    conn.autocommit = False
    written = {}
    try:
        with conn.cursor() as cur:
            # ---------------------------------------------------------- teams
            execute_values(cur, """
                INSERT INTO public.teams_v2
                    (team_name, fifa_code, confederation, wc2026_group,
                     fifa_ranking_pre_wc2026, elo_rating_pre_wc2026,
                     is_wc2026_team, matches_played, first_match, last_match)
                VALUES %s
                ON CONFLICT (team_name) DO NOTHING
            """, [(
                t["team_name"], s(t["fifa_code"]), s(t["confederation"]),
                s(t["wc2026_group"]), i(t["fifa_ranking_pre_wc2026"]),
                i(t["elo_rating_pre_wc2026"]), b(t["is_wc2026_team"]),
                i(t["matches_played"]), s(t["first_match"]), s(t["last_match"]),
            ) for t in teams], page_size=200)
            written["teams_v2"] = cur.rowcount

            cur.execute("SELECT team_name, id FROM public.teams_v2")
            team_id = dict(cur.fetchall())
            missing = {m[k] for m in matches for k in ("home_team", "away_team")} - set(team_id)
            if missing:
                raise RuntimeError(f"teams referenced by matches but absent from teams_v2: {sorted(missing)}")

            # -------------------------------------------------------- matches
            execute_values(cur, """
                INSERT INTO public.matches_v2
                    (match_id, match_date, tournament_year, tournament, competition_type,
                     stage, is_knockout, stage_order, match_number, match_number_source,
                     group_name, home_team_id, away_team_id,
                     home_score_ft, away_score_ft, home_score_et, away_score_et,
                     home_penalties, away_penalties, result, winner_team_id,
                     result_method, is_replay, venue, city, host_country,
                     home_is_host, away_is_host, neutral_venue, kickoff_time_et,
                     attendance, referee, notes, source_dataset, source_file)
                VALUES %s
                ON CONFLICT (match_id) DO NOTHING
            """, [(
                m["match_id"], m["date"], i(m["year"]), m["tournament"],
                m["competition_type"], m["stage"], b(m["is_knockout"]), i(m["stage_order"]),
                i(m["match_number"]), s(m["match_number_source"]), s(m["group_name"]),
                team_id[m["home_team"]], team_id[m["away_team"]],
                i(m["home_score_ft"]), i(m["away_score_ft"]),
                i(m["home_score_et"]), i(m["away_score_et"]),
                i(m["home_penalties"]), i(m["away_penalties"]),
                s(m["result"]), team_id.get(s(m["winner_team"])) if s(m["winner_team"]) else None,
                s(m["result_method"]), b(m["is_replay"]),
                s(m["venue"]), s(m["city"]), s(m["host_country"]),
                b(m["home_is_host"]), b(m["away_is_host"]), b(m["neutral_venue"]),
                s(m["kickoff_time_et"]), i(m["attendance"]), s(m["referee"]), s(m["notes"]),
                m["source_dataset"], m["source_file"],
            ) for m in matches], page_size=200)
            written["matches_v2"] = cur.rowcount

            # ---------------------------------------------------------- stats
            execute_values(cur, """
                INSERT INTO public.match_statistics_v2
                    (match_id, team_id, opponent_id, is_home, possession,
                     shots_on_target, total_shots, saves, cards_yellow, cards_red,
                     fouls, corners, crosses, interceptions, offsides,
                     formation, manager, captain)
                VALUES %s
                ON CONFLICT (match_id, team_id) DO NOTHING
            """, [(
                r["match_id"], team_id[r["team"]], team_id[r["opponent"]], b(r["is_home"]),
                i(r["possession"]), i(r["sot"]), i(r["total_shots"]), i(r["saves"]),
                i(r["cards_yellow"]), i(r["cards_red"]), i(r["fouls"]), i(r["corners"]),
                i(r["crosses"]), i(r["interceptions"]), i(r["offsides"]),
                s(r["formation"]), s(r["manager"]), s(r["captain"]),
            ) for r in stats], page_size=200)
            written["match_statistics_v2"] = cur.rowcount

            # ---------------------------------------------------------- graph
            execute_values(cur, """
                INSERT INTO public.wc2026_tournament_graph
                    (match_number, stage, is_knockout, home_source_type, home_source_match,
                     away_source_type, away_source_match, feeds_winner_to, feeds_loser_to,
                     dependency_source)
                VALUES %s
                ON CONFLICT (match_number) DO NOTHING
            """, [(
                n["match_number"], n["stage"], n["is_knockout"],
                (n["home_source"] or {}).get("type"), (n["home_source"] or {}).get("match_number"),
                (n["away_source"] or {}).get("type"), (n["away_source"] or {}).get("match_number"),
                n["feeds_winner_to"], n["feeds_loser_to"], n["dependency_source"],
            ) for n in graph["nodes"]], page_size=200)
            written["wc2026_tournament_graph"] = cur.rowcount

        # execute_values reports rowcount for its final page only, so the true
        # totals are read back from the tables inside the same transaction.
        with conn.cursor() as cur:
            for table in ("teams_v2", "matches_v2", "match_statistics_v2",
                          "wc2026_tournament_graph"):
                cur.execute(f"SELECT count(*) FROM public.{table}")
                written[table] = cur.fetchone()[0]

        expected = {"teams_v2": len(teams), "matches_v2": len(matches),
                    "match_statistics_v2": len(stats),
                    "wc2026_tournament_graph": len(graph["nodes"])}
        mismatch = {k: {"in_db": written[k], "expected": v}
                    for k, v in expected.items() if written[k] != v}
        if mismatch:
            raise RuntimeError(f"row-count mismatch after insert: {mismatch}")

        if args.dry_run:
            conn.rollback()
            print("DRY RUN — rolled back")
        else:
            conn.commit()
            print("committed")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(json.dumps({"rows_inserted": written}, indent=2))


if __name__ == "__main__":
    main()
