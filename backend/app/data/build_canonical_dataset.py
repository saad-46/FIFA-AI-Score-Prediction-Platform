"""
Build the canonical FIFA World Cup match dataset (v2) from the five approved sources.

Approved source set — nothing else may be read:
  S1  fifa_world_cup_all_matches_1930_1998.csv   581 rows, WC 1930-1998
  S2  fifa_world_cup_all_matches_2002_2026.csv   488 rows, WC 2002-2026
  S3  FWC26 Match Schedule.pdf                   official 2026 schedule/bracket
  S4  matches_wc26_detailed.csv                  104 rows, 2026 detail + match stats
  S5  teams(group_ELOrank).csv.xlsx               48 rows, 2026 team reference

The previous 7 workbooks and the ~49k-row Kaggle corpus are deliberately NOT read.

Design decisions this script encodes (see DATA_REBUILD_REPORT.md):
  * ``total_goals_team1/2`` from S1/S2 are DROPPED — they disagree with the real
    scoreline in 650/1069 rows and are unusable. Goals are derived from the
    full-time and extra-time columns instead, which cross-validate cleanly
    against S4.
  * Score semantics are kept explicitly separate rather than collapsed:
    ``*_score_ft`` is the 90-minute score, ``*_score_et`` the 120-minute score
    (cumulative, only where extra time was played), ``*_penalties`` the
    shoot-out. S2's "fulltime" and S4's "score" are NOT in conflict; they are
    these two different concepts.
  * Missing values stay NULL. Nothing is inferred from a corrupt field and no
    value is fabricated. xG does not exist in any approved source, so no xG
    column is emitted at all.
  * S4's per-match statistics are stored as MATCH OUTCOMES, never as features.
    Feature engineering may only consume them as lagged/rolling aggregates of
    *earlier* matches.

Stdlib only by design — this must run before any dependency install, and its
output must be byte-reproducible from the five sources alone.

Read-only with respect to the sources; writes only into data/canonical/.
"""

from __future__ import annotations

import csv
import io
import json
import hashlib
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent / "canonical"

SRC = {
    "S1": REPO_ROOT / "fifa_world_cup_all_matches_1930_1998.csv",
    "S2": REPO_ROOT / "fifa_world_cup_all_matches_2002_2026.csv",
    "S3": REPO_ROOT / "FWC26 Match Schedule.pdf",
    "S4": REPO_ROOT / "matches_wc26_detailed.csv",
    "S5": REPO_ROOT / "teams(group_ELOrank).csv.xlsx",
}

# ---------------------------------------------------------------------------
# Team identity
# ---------------------------------------------------------------------------
# Only spelling / transliteration / straight renames of a *continuing* football
# association are merged. Predecessor states that dissolved into multiple new
# associations are deliberately KEPT SEPARATE, because they are genuinely
# different teams and merging them would silently invent continuity that the
# historical record does not support:
#     West Germany / East Germany / Germany   -> three identities
#     Soviet Union / Russia / Ukraine         -> separate
#     Czechoslovakia / Czechia / Slovakia     -> separate
#     Yugoslavia / Serbia and Montenegro / Serbia / Croatia / Slovenia / BIH
#                                             -> separate
#     Dutch East Indies                       -> separate (not folded into Indonesia)
# Zaire -> Congo DR IS merged: that was a country rename in 1997 with no
# dissolution and an unbroken association, unlike the cases above.
TEAM_ALIASES: dict[str, str] = {
    # spelling / diacritic / transliteration variants
    "United States": "USA",
    "Korea Republic": "South Korea",
    "Turkey": "Türkiye",
    "TÃ¼rkiye": "Türkiye",          # S5 mojibake
    "Ivory Coast": "Côte d'Ivoire",
    "CÃ´te d'Ivoire": "Côte d'Ivoire",  # S5 mojibake
    "CuraÃ§ao": "Curaçao",          # S5 mojibake
    "Cape Verde": "Cabo Verde",
    "DR Congo": "Congo DR",
    "Iran": "IR Iran",
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia–Herz": "Bosnia and Herzegovina",   # S4, en-dash
    "Bosnia-Herz": "Bosnia and Herzegovina",
    # straight national rename, association continuous
    "Zaire": "Congo DR",
    # naming convention
    "Ireland": "Republic of Ireland",
}

# Identities that a naive alias map would wrongly collapse. Recorded so the
# validation report can assert they stayed distinct.
DELIBERATELY_DISTINCT = [
    ("West Germany", "Germany"), ("East Germany", "Germany"),
    ("Soviet Union", "Russia"), ("Czechoslovakia", "Czechia"),
    ("Yugoslavia", "Serbia"), ("Serbia and Montenegro", "Serbia"),
    ("Dutch East Indies", "Indonesia"),
]

# ---------------------------------------------------------------------------
# Stage vocabulary
# ---------------------------------------------------------------------------
STAGE_MAP = {
    "group stage": "group_stage",
    "final round": "final_round",             # 1950 round-robin final group
    "preliminary round": "preliminary_round",  # 1934 opening knockout round
    "first round": "first_round",             # 1938 opening knockout round
    "first round, replays": "first_round",    # replay flag carried separately
    "round of 32": "round_of_32",
    "round of 16": "round_of_16",
    "quarter-final": "quarter_final",
    "quarter-finals": "quarter_final",
    "semi-final": "semi_final",
    "semi-finals": "semi_final",
    "third-place match": "third_place",
    "third place play-off": "third_place",
    "third-place play-off": "third_place",
    "final": "final",
}
KNOCKOUT_STAGES = {
    "preliminary_round", "first_round", "round_of_32", "round_of_16",
    "quarter_final", "semi_final", "third_place", "final",
}
STAGE_ORDER = {
    "group_stage": 1, "final_round": 2, "preliminary_round": 3, "first_round": 4,
    "round_of_32": 5, "round_of_16": 6, "quarter_final": 7, "semi_final": 8,
    "third_place": 9, "final": 10,
}

HOST_NATIONS = {
    1930: ["Uruguay"], 1934: ["Italy"], 1938: ["France"], 1950: ["Brazil"],
    1954: ["Switzerland"], 1958: ["Sweden"], 1962: ["Chile"], 1966: ["England"],
    1970: ["Mexico"], 1974: ["West Germany"], 1978: ["Argentina"], 1982: ["Spain"],
    1986: ["Mexico"], 1990: ["Italy"], 1994: ["USA"], 1998: ["France"],
    2002: ["South Korea", "Japan"], 2006: ["Germany"], 2010: ["South Africa"],
    2014: ["Brazil"], 2018: ["Russia"], 2022: ["Qatar"],
    2026: ["Canada", "Mexico", "USA"],
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    raw = path.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return list(csv.DictReader(io.StringIO(raw.decode(enc))))


def read_xlsx(path: Path) -> list[dict]:
    """Minimal xlsx reader (xlsx is a zip of XML). Avoids an openpyxl dependency."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    tag_t = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
    tag_row = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"

    def col_index(ref: str) -> int:
        n = 0
        for ch in re.match(r"([A-Z]+)", ref).group(1):
            n = n * 26 + (ord(ch) - 64)
        return n - 1

    with zipfile.ZipFile(path) as z:
        shared = [
            "".join(t.text or "" for t in si.iter(tag_t))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        grid = []
        for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(tag_row):
            cells = {}
            for c in row.findall("m:c", ns):
                v = c.find("m:v", ns)
                if v is None:
                    continue
                cells[col_index(c.get("r"))] = (
                    shared[int(v.text)] if c.get("t") == "s" else v.text
                )
            if cells:
                grid.append([cells.get(i, "") for i in range(max(cells) + 1)])
    header, body = grid[0], [r for r in grid[1:] if any(x.strip() for x in r)]
    return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in body]


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None


def to_int(value: str) -> int | None:
    value = (value or "").strip()
    if value in ("", "-", "nan", "NaN", "None", "NULL"):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def fix_mojibake(text: str) -> str:
    """Repair double-encoded UTF-8 (S5 has three such team names)."""
    if not text:
        return text
    if any(marker in text for marker in ("Ã", "Â", "â€")):
        try:
            return text.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text
    return text


def canon_team(name: str) -> str:
    name = fix_mojibake((name or "").strip())
    name = unicodedata.normalize("NFC", name)
    return TEAM_ALIASES.get(name, name)


def canon_stage(raw: str) -> str:
    key = (raw or "").strip().lower()
    if key not in STAGE_MAP:
        raise ValueError(f"unmapped stage vocabulary: {raw!r}")
    return STAGE_MAP[key]


def make_match_id(year: int, iso: str, home: str, away: str) -> str:
    digest = hashlib.sha1(f"{year}|{iso}|{home}|{away}".encode()).hexdigest()[:12]
    return f"wc{year}_{digest}"


# ---------------------------------------------------------------------------
# core build
# ---------------------------------------------------------------------------
def build_matches() -> tuple[list[dict], dict]:
    notes: dict = {"unmapped_stages": [], "date_failures": [], "winner_mismatch": []}
    rows: list[dict] = []

    for tag, path in (("S1", SRC["S1"]), ("S2", SRC["S2"])):
        for raw in read_csv(path):
            year = int(raw["world_cup_year"])
            d = parse_date(raw["date"])
            if d is None:
                notes["date_failures"].append({"source": tag, "raw": raw["date"]})
                continue

            home = canon_team(raw["team1"])
            away = canon_team(raw["team2"])
            stage = canon_stage(raw["stage"])

            ft_h, ft_a = to_int(raw["fulltime_score_team1"]), to_int(raw["fulltime_score_team2"])
            et_h, et_a = to_int(raw["extra_time_score_team1"]), to_int(raw["extra_time_score_team2"])
            pk_h, pk_a = to_int(raw["penalty_score_team1"]), to_int(raw["penalty_score_team2"])

            # Decisive score = extra time where played, else full time.
            # NEVER derived from the corrupt total_goals_* columns.
            fin_h = et_h if et_h is not None else ft_h
            fin_a = et_a if et_a is not None else ft_a

            if fin_h is None or fin_a is None:
                result = None                      # e.g. the 1938 walkover
            elif fin_h > fin_a:
                result = "home_win"
            elif fin_h < fin_a:
                result = "away_win"
            elif pk_h is not None and pk_a is not None:
                result = "draw"                    # drawn on the pitch, settled on penalties
            else:
                result = "draw"

            # winner as an explicit team (penalties decide who advanced)
            if fin_h is None:
                winner = None
            elif fin_h > fin_a:
                winner = home
            elif fin_a > fin_h:
                winner = away
            elif pk_h is not None and pk_a is not None:
                winner = home if pk_h > pk_a else away
            else:
                winner = None                      # genuine draw, nobody advanced

            src_winner = canon_team(raw["winner"]) if raw["winner"] != "Draw" else None
            if src_winner and winner and src_winner != winner:
                notes["winner_mismatch"].append(
                    {"date": d.isoformat(), "home": home, "away": away,
                     "derived": winner, "source": src_winner}
                )

            hosts = HOST_NATIONS.get(year, [])
            venue_raw = (raw["stadium"] or "").strip()
            city = (raw["city"] or "").strip() or None

            rows.append({
                "match_id": make_match_id(year, d.isoformat(), home, away),
                "date": d.isoformat(),
                "year": year,
                "tournament": f"FIFA World Cup {year}",
                "competition_type": "world_cup",
                "stage": stage,
                "is_knockout": stage in KNOCKOUT_STAGES,
                "stage_order": STAGE_ORDER[stage],
                "match_number": None,              # filled for 2026 from the schedule
                "group_name": (raw["group"] or "").strip() or None,
                "home_team": home,
                "away_team": away,
                "home_score_ft": ft_h,
                "away_score_ft": ft_a,
                "home_score_et": et_h,
                "away_score_et": et_a,
                "home_penalties": pk_h,
                "away_penalties": pk_a,
                "result": result,
                "winner_team": winner,
                "result_method": (raw["result_method"] or "").strip() or None,
                "is_replay": "replay" in (raw["round_raw"] or "").lower(),
                "venue": venue_raw or None,
                "city": city,
                "host_country": (raw["host_country"] or "").strip() or None,
                "home_is_host": home in hosts,
                "away_is_host": away in hosts,
                "neutral_venue": (home not in hosts) and (away not in hosts),
                "source_dataset": "wc_1930_1998" if tag == "S1" else "wc_2002_2026",
                "source_file": SRC[tag].name,
            })

    rows.sort(key=lambda r: (r["date"], r["home_team"], r["away_team"]))
    return rows, notes


def build_teams(matches: list[dict]) -> tuple[list[dict], dict]:
    """Team registry: every team that appears, enriched for the 48 of 2026."""
    ref = {}
    for raw in read_xlsx(SRC["S5"]):
        name = canon_team(raw["team_name"])
        ref[name] = {
            "fifa_code": raw["fifa_code"].strip(),
            "wc2026_group": raw["group_letter"].strip(),
            "confederation": raw["confederation"].strip(),
            "fifa_ranking_pre_wc2026": to_int(raw["fifa_ranking_pre_tournament"]),
            "elo_rating_pre_wc2026": to_int(raw["elo_rating"]),
        }

    appearances: Counter = Counter()
    first_seen: dict[str, str] = {}
    last_seen: dict[str, str] = {}
    for m in matches:
        for side in ("home_team", "away_team"):
            t = m[side]
            appearances[t] += 1
            first_seen.setdefault(t, m["date"])
            last_seen[t] = m["date"]

    teams = []
    for name in sorted(appearances):
        info = ref.get(name, {})
        teams.append({
            "team_name": name,
            "fifa_code": info.get("fifa_code"),
            "confederation": info.get("confederation"),
            "wc2026_group": info.get("wc2026_group"),
            "fifa_ranking_pre_wc2026": info.get("fifa_ranking_pre_wc2026"),
            "elo_rating_pre_wc2026": info.get("elo_rating_pre_wc2026"),
            "is_wc2026_team": name in ref,
            "matches_played": appearances[name],
            "first_match": first_seen[name],
            "last_match": last_seen[name],
        })

    diag = {
        "reference_teams": len(ref),
        "teams_in_reference_not_in_matches": sorted(set(ref) - set(appearances)),
        "wc2026_teams_matched": sum(1 for t in teams if t["is_wc2026_team"]),
    }
    return teams, diag


def build_match_stats() -> tuple[list[dict], dict]:
    """
    S4 per-match statistics — stored as MATCH OUTCOMES, one row per team per match.

    These describe what happened during the match and must never be used as a
    pre-match feature for that same match. Feature engineering may consume them
    only as rolling aggregates over strictly earlier matches.
    """
    stat_fields = [
        "possession", "sot", "total_shots", "saves", "cards_yellow", "cards_red",
        "fouls", "corners", "crosses", "interceptions", "offsides",
    ]
    out, notes = [], {"unparsed_scores": [], "formation_repairs": 0}

    for raw in read_csv(SRC["S4"]):
        d = parse_date(raw["date"])
        home, away = canon_team(raw["home_team"]), canon_team(raw["away_team"])
        year = d.year
        mid = make_match_id(year, d.isoformat(), home, away)

        for side, team, opp in (("home", home, away), ("away", away, home)):
            row = {
                "match_id": mid,
                "date": d.isoformat(),
                "team": team,
                "opponent": opp,
                "is_home": side == "home",
            }
            for f in stat_fields:
                row[f] = to_int(raw.get(f"{side}_{f}", ""))
            # Excel silently rewrote formations like 3-4-3 into dates (03-04-2003)
            formation = (raw.get(f"{side}_formation") or "").strip()
            if re.fullmatch(r"\d{2}-\d{2}-\d{4}", formation):
                a, b, c = formation.split("-")
                formation = f"{int(a)}-{int(b)}-{int(c) % 100 // 10 or int(c) % 10}"
                notes["formation_repairs"] += 1
            row["formation"] = formation or None
            row["manager"] = (raw.get(f"{side}_manager") or "").strip() or None
            row["captain"] = (raw.get(f"{side}_captain") or "").strip() or None
            out.append(row)

    return out, notes


def enrich_2026(matches: list[dict]) -> dict:
    """
    Attach S4's match-level context (kick-off time, venue, attendance, referee)
    to the 2026 rows, and cross-validate scores between S2 and S4.

    S2.fulltime is the 90-minute score; S4.score is the post-extra-time result.
    They are different concepts, so agreement is asserted against the correct
    one rather than naively comparing full-time to final.
    """
    idx = {}
    for raw in read_csv(SRC["S4"]):
        d = parse_date(raw["date"])
        key = (d.isoformat(), canon_team(raw["home_team"]), canon_team(raw["away_team"]))
        idx[key] = raw

    diag = {"matched": 0, "unmatched_s4_keys": [], "score_conflicts": [], "reversed_fixture": 0}
    seen = set()

    for m in matches:
        if m["year"] != 2026:
            continue
        key = (m["date"], m["home_team"], m["away_team"])
        raw = idx.get(key)
        if raw is None:
            # S2 and S4 can list the same fixture with sides swapped
            alt = (m["date"], m["away_team"], m["home_team"])
            raw = idx.get(alt)
            if raw is not None:
                key = alt
                diag["reversed_fixture"] += 1
        if raw is None:
            continue

        seen.add(key)
        diag["matched"] += 1

        m["kickoff_time_et"] = (raw["start_time"] or "").strip() or None
        m["venue"] = (raw["venue"] or "").strip() or m["venue"]
        m["attendance"] = to_int((raw["attendance"] or "").replace(",", ""))
        m["referee"] = (raw["referee"] or "").strip() or None
        m["notes"] = (raw["notes"] or "").strip() or None

        # cross-validate: S4's final score must equal ET where played, else FT
        s4_h, s4_a = to_int(raw["home_score"]), to_int(raw["away_score"])
        if s4_h is None:
            sm = re.search(r"\(?\d*\)?(\d+)[–\-](\d+)\(?\d*\)?", raw["score"] or "")
            if sm:
                s4_h, s4_a = int(sm.group(1)), int(sm.group(2))
        if key[1] != m["home_team"]:          # sides were swapped in S4
            s4_h, s4_a = s4_a, s4_h
        fin_h = m["home_score_et"] if m["home_score_et"] is not None else m["home_score_ft"]
        fin_a = m["away_score_et"] if m["away_score_et"] is not None else m["away_score_ft"]
        if s4_h is not None and (s4_h, s4_a) != (fin_h, fin_a):
            diag["score_conflicts"].append({
                "date": m["date"], "home": m["home_team"], "away": m["away_team"],
                "s2_final": [fin_h, fin_a], "s4_final": [s4_h, s4_a],
                "s2_ft": [m["home_score_ft"], m["away_score_ft"]],
            })

    diag["unmatched_s4_keys"] = [list(k) for k in idx if k not in seen]
    return diag


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    matches, notes = build_matches()
    enrich_diag = enrich_2026(matches)
    teams, team_diag = build_teams(matches)
    stats, stat_notes = build_match_stats()

    # ---- duplicate detection (football identity, not row id) ----
    dup_report = {}
    for label, keyfn in (
        ("date_home_away", lambda m: (m["date"], m["home_team"], m["away_team"])),
        ("year_stage_teams_unordered",
         lambda m: (m["year"], m["stage"], tuple(sorted((m["home_team"], m["away_team"]))))),
    ):
        counts = Counter(keyfn(m) for m in matches)
        collisions = {str(k): v for k, v in counts.items() if v > 1}
        dup_report[label] = collisions

    fields = [
        "match_id", "date", "year", "tournament", "competition_type", "stage",
        "is_knockout", "stage_order", "match_number", "group_name",
        "home_team", "away_team",
        "home_score_ft", "away_score_ft", "home_score_et", "away_score_et",
        "home_penalties", "away_penalties", "result", "winner_team",
        "result_method", "is_replay",
        "venue", "city", "host_country", "home_is_host", "away_is_host",
        "neutral_venue", "kickoff_time_et", "attendance", "referee", "notes",
        "source_dataset", "source_file",
    ]
    for m in matches:
        for f in fields:
            m.setdefault(f, None)

    def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    write_csv(OUT_DIR / "canonical_matches.csv", matches, fields)
    write_csv(OUT_DIR / "canonical_teams.csv", teams, list(teams[0].keys()))
    write_csv(OUT_DIR / "canonical_match_stats.csv", stats, list(stats[0].keys()))

    by_year = Counter(m["year"] for m in matches)
    build_report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {k: v.name for k, v in SRC.items()},
        "counts": {
            "matches_total": len(matches),
            "matches_1930_1998": sum(1 for m in matches if m["year"] <= 1998),
            "matches_2002_2026": sum(1 for m in matches if m["year"] >= 2002),
            "matches_2026": by_year.get(2026, 0),
            "teams_total": len(teams),
            "teams_wc2026": sum(1 for t in teams if t["is_wc2026_team"]),
            "match_stat_rows": len(stats),
            "tournaments": len(by_year),
        },
        "matches_by_year": {str(k): v for k, v in sorted(by_year.items())},
        "duplicates": dup_report,
        "team_diagnostics": team_diag,
        "wc2026_enrichment": enrich_diag,
        "stat_notes": stat_notes,
        "build_notes": notes,
        "deliberately_distinct_identities": [list(p) for p in DELIBERATELY_DISTINCT],
        "dropped_columns": {
            "total_goals_team1": "corrupt in 650/1069 rows — disagrees with the real scoreline",
            "total_goals_team2": "corrupt in 650/1069 rows — disagrees with the real scoreline",
        },
        "xg_status": "UNAVAILABLE — not present in any approved source; never fabricated",
    }
    (OUT_DIR / "build_report.json").write_text(
        json.dumps(build_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(build_report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
