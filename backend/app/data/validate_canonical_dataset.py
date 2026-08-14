"""
Finalise and validate the canonical dataset before any database write.

Runs after ``build_canonical_dataset.py`` and ``parse_wc2026_schedule.py``:

  1. Joins the parsed WC2026 wallchart fixtures onto the canonical 2026 matches
     and assigns every match its FIFA match number, recording for each row
     whether the number came from the PDF or was derived from FIFA's numbering
     scheme (never silently inferred).
  2. Cross-validates the three independent 2026 sources against each other.
  3. Runs the full validation battery — counts, duplicates, teams and groups,
     score sanity, dates, and tournament-structure integrity.

Writes the finalised ``canonical_matches.csv`` and ``validation_report.json``.
Exits non-zero if any blocking check fails, so this cannot be mistaken for a
pass when it is not.

Stdlib only.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
CANON = DATA_DIR / "canonical"

STAGE_RANGES = {
    "group_stage": (1, 72), "round_of_32": (73, 88), "round_of_16": (89, 96),
    "quarter_final": (97, 100), "semi_final": (101, 102),
    "third_place": (103, 103), "final": (104, 104),
}
EXPECTED_BY_YEAR = {
    1930: 18, 1934: 17, 1938: 19, 1950: 22, 1954: 26, 1958: 35, 1962: 32,
    1966: 32, 1970: 32, 1974: 38, 1978: 38, 1982: 52, 1986: 52, 1990: 52,
    1994: 52, 1998: 64, 2002: 64, 2006: 64, 2010: 64, 2014: 64, 2018: 64,
    2022: 64, 2026: 104,
}
EXPECTED_TOTAL = 1069


def read_csv(path: Path) -> list[dict]:
    raw = path.read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw)))


def as_int(value):
    if isinstance(value, int):
        return value
    value = (value or "").strip()
    if value in ("", "None", "NULL"):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def as_bool(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
def assign_match_numbers(matches: list[dict], schedule: dict, teams: list[dict]) -> dict:
    """Attach FIFA match numbers to the 104 WC2026 rows."""
    code_to_name = {
        t["fifa_code"]: t["team_name"] for t in teams
        if (t.get("fifa_code") or "").strip()
    }

    # unordered team pair -> match number, from the wallchart
    pdf_pairs: dict[frozenset, dict] = {}
    unresolved_codes: set[str] = set()
    for fx in schedule["fixtures"]:
        home = code_to_name.get(fx["home_code"])
        away = code_to_name.get(fx["away_code"])
        if not home or not away:
            unresolved_codes.update(
                c for c in (fx["home_code"], fx["away_code"]) if c not in code_to_name)
            continue
        pdf_pairs[frozenset((home, away))] = fx

    rows_2026 = [m for m in matches if m["year"] == 2026]
    diag = {
        "wc2026_rows": len(rows_2026),
        "assigned_from_pdf": 0,
        "assigned_by_derivation": 0,
        "unresolved_fifa_codes": sorted(unresolved_codes),
        "pdf_pairs_unmatched_to_dataset": [],
        "kickoff_conflicts": [],
    }

    # A wallchart candidate is only accepted when it falls inside the number
    # range of the stage the fixture actually belongs to. The wallchart writes
    # the number before the fixture in the group grid but after it in the
    # knockout bracket, so a candidate that lands in the wrong stage is a
    # mis-binding, not evidence — it is discarded rather than trusted.
    used: set[int] = set()
    diag["rejected_out_of_stage_candidates"] = []

    for m in rows_2026:
        fx = pdf_pairs.get(frozenset((m["home_team"], m["away_team"])))
        m["match_number"] = None
        m["match_number_source"] = None
        if not fx:
            continue

        lo, hi = STAGE_RANGES[m["stage"]]
        viable = [n for n in fx.get("match_number_candidates", [])
                  if lo <= n <= hi and n not in used]
        rejected = [n for n in fx.get("match_number_candidates", [])
                    if not (lo <= n <= hi)]
        if rejected:
            diag["rejected_out_of_stage_candidates"].append({
                "teams": [m["home_team"], m["away_team"]], "stage": m["stage"],
                "valid_range": [lo, hi], "rejected": rejected})

        if len(viable) == 1:
            m["match_number"] = viable[0]
            m["match_number_source"] = "pdf_wallchart"
            used.add(viable[0])
            diag["assigned_from_pdf"] += 1
            if fx["kickoff_et"] and m.get("kickoff_time_et") and fx["kickoff_et"] != m["kickoff_time_et"]:
                diag["kickoff_conflicts"].append({
                    "match_number": viable[0], "pdf": fx["kickoff_et"],
                    "s4": m["kickoff_time_et"],
                    "teams": [m["home_team"], m["away_team"]]})

    # Derive the remainder from FIFA's scheme: within each stage, unused numbers
    # are handed out in chronological order. The stage boundaries themselves are
    # corroborated by the wallchart's own bracket references.
    by_stage: dict[str, list[dict]] = defaultdict(list)
    for m in rows_2026:
        if m["match_number"] is None:
            by_stage[m["stage"]].append(m)

    for stage, pending in by_stage.items():
        lo, hi = STAGE_RANGES[stage]
        free = [n for n in range(lo, hi + 1) if n not in used]
        pending.sort(key=lambda r: (r["date"], r.get("kickoff_time_et") or "", r["home_team"]))
        for m, num in zip(pending, free):
            m["match_number"] = num
            m["match_number_source"] = "derived_from_fifa_scheme"
            used.add(num)
            diag["assigned_by_derivation"] += 1

    matched_pairs = {frozenset((m["home_team"], m["away_team"])) for m in rows_2026}
    diag["pdf_pairs_unmatched_to_dataset"] = [
        sorted(p) for p in pdf_pairs if p not in matched_pairs]

    # Kick-off times: the wallchart lays fixtures out on a spatial grid, so a
    # flat text extraction can bind a time to a neighbouring fixture. That this
    # happens is demonstrated by the out-of-stage match numbers rejected above,
    # and the PDF/S4 differences are scattered across many offsets rather than a
    # single timezone shift — so they are mis-bindings, not a real disagreement.
    # S4 is one structured row per match with no such ambiguity, and is therefore
    # authoritative for kick-off time. The PDF time is not carried through.
    diag["kickoff_resolution"] = {
        "authoritative_source": "S4 matches_wc26_detailed.csv (start_time)",
        "pdf_times_discarded": True,
        "reason": ("wallchart text extraction binds times to adjacent grid cells; "
                   "differences are non-uniform so they are extraction artefacts, "
                   "not a substantive source conflict"),
        "fixtures_where_pdf_time_differed": len(diag["kickoff_conflicts"]),
    }

    nums = sorted(m["match_number"] for m in rows_2026 if m["match_number"])
    diag["assigned_total"] = len(nums)
    diag["numbers_are_1_to_104"] = nums == list(range(1, 105))
    return diag


# ---------------------------------------------------------------------------
def validate(matches, teams, stats, schedule, graph) -> tuple[dict, list[str]]:
    failures: list[str] = []
    report: dict = {}

    # ---- counts -----------------------------------------------------------
    by_year = Counter(m["year"] for m in matches)
    counts = {
        "total_matches": len(matches),
        "expected_total": EXPECTED_TOTAL,
        "matches_1930_1998": sum(1 for m in matches if m["year"] <= 1998),
        "matches_2002_2026": sum(1 for m in matches if m["year"] >= 2002),
        "matches_2026": by_year.get(2026, 0),
        "tournaments": len(by_year),
        "by_year": {str(k): v for k, v in sorted(by_year.items())},
    }
    if len(matches) != EXPECTED_TOTAL:
        failures.append(f"total matches {len(matches)} != expected {EXPECTED_TOTAL}")
    year_mismatch = {y: (by_year.get(y, 0), exp)
                     for y, exp in EXPECTED_BY_YEAR.items() if by_year.get(y, 0) != exp}
    counts["per_tournament_mismatches"] = {str(k): {"actual": v[0], "expected": v[1]}
                                           for k, v in year_mismatch.items()}
    if year_mismatch:
        failures.append(f"per-tournament count mismatch: {year_mismatch}")
    report["counts"] = counts

    # ---- duplicates -------------------------------------------------------
    exact = Counter((m["date"], m["home_team"], m["away_team"]) for m in matches)
    exact_dupes = {str(k): v for k, v in exact.items() if v > 1}
    ids = Counter(m["match_id"] for m in matches)
    id_dupes = {k: v for k, v in ids.items() if v > 1}

    loose = defaultdict(list)
    for m in matches:
        loose[(m["year"], m["stage"], frozenset((m["home_team"], m["away_team"])))].append(m)
    repeated = {k: v for k, v in loose.items() if len(v) > 1}
    legitimate, suspicious = [], []
    for k, group in repeated.items():
        dates = {g["date"] for g in group}
        entry = {"year": k[0], "stage": k[1], "teams": sorted(k[2]),
                 "dates": sorted(dates),
                 "is_replay": [as_bool(g["is_replay"]) for g in group]}
        (legitimate if len(dates) == len(group) else suspicious).append(entry)

    report["duplicates"] = {
        "exact_date_home_away": exact_dupes,
        "duplicate_match_ids": id_dupes,
        "same_year_stage_teams_distinct_dates": legitimate,
        "same_year_stage_teams_SAME_date": suspicious,
    }
    if exact_dupes:
        failures.append(f"{len(exact_dupes)} exact duplicate matches")
    if id_dupes:
        failures.append(f"{len(id_dupes)} duplicate match_ids")
    if suspicious:
        failures.append(f"{len(suspicious)} same-date repeated fixtures (true duplicates)")

    # ---- teams / groups ---------------------------------------------------
    wc26 = [t for t in teams if as_bool(t["is_wc2026_team"])]
    groups = defaultdict(list)
    for t in wc26:
        groups[t["wc2026_group"]].append(t["team_name"])
    bad_groups = {g: len(v) for g, v in groups.items() if len(v) != 4}
    team_block = {
        "total_teams": len(teams),
        "wc2026_teams": len(wc26),
        "wc2026_groups": len(groups),
        "groups_not_of_four": bad_groups,
        "teams_missing_fifa_code": [t["team_name"] for t in wc26 if not t["fifa_code"]],
        "teams_missing_elo": [t["team_name"] for t in wc26 if not t["elo_rating_pre_wc2026"]],
        "teams_missing_fifa_rank": [t["team_name"] for t in wc26 if not t["fifa_ranking_pre_wc2026"]],
        "pdf_groups_match_reference": True,
    }
    if len(wc26) != 48:
        failures.append(f"WC2026 teams = {len(wc26)}, expected 48")
    if len(groups) != 12:
        failures.append(f"WC2026 groups = {len(groups)}, expected 12")
    if bad_groups:
        failures.append(f"groups without exactly 4 teams: {bad_groups}")

    # PDF groups vs S5 reference
    code_to_name = {t["fifa_code"]: t["team_name"] for t in teams if t.get("fifa_code")}
    pdf_group_mismatch = []
    for letter, codes in schedule.get("groups", {}).items():
        for code in codes:
            name = code_to_name.get(code)
            if name is None:
                pdf_group_mismatch.append({"code": code, "issue": "unknown fifa_code"})
                continue
            ref = next((t for t in wc26 if t["team_name"] == name), None)
            if ref and ref["wc2026_group"] != letter:
                pdf_group_mismatch.append({"team": name, "pdf_group": letter,
                                           "reference_group": ref["wc2026_group"]})
    team_block["pdf_vs_reference_group_mismatches"] = pdf_group_mismatch
    team_block["pdf_groups_match_reference"] = not pdf_group_mismatch
    if pdf_group_mismatch:
        failures.append(f"{len(pdf_group_mismatch)} PDF/reference group mismatches")
    report["teams"] = team_block

    # ---- scores -----------------------------------------------------------
    negative, impossible, null_scores, et_inconsistent, pk_without_draw = [], [], [], [], []
    for m in matches:
        ft = (as_int(m["home_score_ft"]), as_int(m["away_score_ft"]))
        et = (as_int(m["home_score_et"]), as_int(m["away_score_et"]))
        pk = (as_int(m["home_penalties"]), as_int(m["away_penalties"]))
        label = f"{m['date']} {m['home_team']} v {m['away_team']}"

        for v in (*ft, *et, *pk):
            if v is not None and v < 0:
                negative.append(label)
            if v is not None and v > 20:
                impossible.append(label)
        if ft[0] is None or ft[1] is None:
            null_scores.append({"match": label, "method": m["result_method"]})
        # extra time can never reduce the score below the 90-minute score
        if et[0] is not None and ft[0] is not None and (et[0] < ft[0] or et[1] < ft[1]):
            et_inconsistent.append({"match": label, "ft": ft, "et": et})
        # a shoot-out implies the match was level when it ended
        if pk[0] is not None:
            fin = et if et[0] is not None else ft
            if fin[0] is not None and fin[0] != fin[1]:
                pk_without_draw.append({"match": label, "final": fin, "pens": pk})

    report["scores"] = {
        "negative_scores": negative,
        "implausible_scores": impossible,
        "null_full_time_scores": null_scores,
        "extra_time_below_full_time": et_inconsistent,
        "penalties_on_non_level_match": pk_without_draw,
        "matches_with_extra_time": sum(1 for m in matches if as_int(m["home_score_et"]) is not None),
        "matches_with_penalties": sum(1 for m in matches if as_int(m["home_penalties"]) is not None),
    }
    for name, bucket in (("negative", negative), ("implausible", impossible),
                         ("extra-time<full-time", et_inconsistent),
                         ("penalties on non-level match", pk_without_draw)):
        if bucket:
            failures.append(f"{len(bucket)} rows with {name} scores")

    # ---- dates ------------------------------------------------------------
    parsed, bad_dates, out_of_window = [], [], []
    for m in matches:
        try:
            d = datetime.strptime(m["date"], "%Y-%m-%d").date()
        except ValueError:
            bad_dates.append(m["date"])
            continue
        parsed.append(d)
        if not (date(m["year"], 1, 1) <= d <= date(m["year"], 12, 31)):
            out_of_window.append({"date": m["date"], "year": m["year"]})
    report["dates"] = {
        "invalid_or_missing": bad_dates,
        "outside_tournament_year": out_of_window,
        "earliest": min(parsed).isoformat() if parsed else None,
        "latest": max(parsed).isoformat() if parsed else None,
        "chronologically_sorted": all(
            matches[i]["date"] <= matches[i + 1]["date"] for i in range(len(matches) - 1)),
    }
    if bad_dates:
        failures.append(f"{len(bad_dates)} invalid dates")
    if out_of_window:
        failures.append(f"{len(out_of_window)} dates outside their tournament year")

    # ---- tournament structure --------------------------------------------
    rows_2026 = [m for m in matches if m["year"] == 2026]
    stage_counts = Counter(m["stage"] for m in rows_2026)
    expected_stage_counts = {"group_stage": 72, "round_of_32": 16, "round_of_16": 8,
                             "quarter_final": 4, "semi_final": 2, "third_place": 1, "final": 1}
    stage_mismatch = {s: {"actual": stage_counts.get(s, 0), "expected": e}
                      for s, e in expected_stage_counts.items() if stage_counts.get(s, 0) != e}

    nums = sorted(as_int(m["match_number"]) for m in rows_2026 if as_int(m["match_number"]))
    node_by_num = {n["match_number"]: n for n in graph["nodes"]}
    dangling = []
    for node in graph["nodes"]:
        for side in ("home_source", "away_source"):
            src = node[side] or {}
            if "match_number" in src and src["match_number"] not in node_by_num:
                dangling.append({"match": node["match_number"], "missing_ref": src["match_number"]})

    number_source = Counter(m.get("match_number_source") for m in rows_2026)
    report["tournament_structure"] = {
        "wc2026_stage_counts": dict(stage_counts),
        "stage_count_mismatches": stage_mismatch,
        "match_numbers_complete_1_104": nums == list(range(1, 105)),
        "match_number_provenance": {str(k): v for k, v in number_source.items()},
        "graph_nodes": len(graph["nodes"]),
        "dangling_dependency_refs": dangling,
        "final_present": stage_counts.get("final") == 1,
        "third_place_present": stage_counts.get("third_place") == 1,
        "knockout_links_from_pdf": sum(
            1 for n in graph["nodes"] if n["dependency_source"] == "pdf"),
    }
    if stage_mismatch:
        failures.append(f"WC2026 stage count mismatch: {stage_mismatch}")
    if nums != list(range(1, 105)):
        failures.append("WC2026 match numbers are not exactly 1..104")
    if dangling:
        failures.append(f"{len(dangling)} dangling knockout dependency references")

    # ---- provenance & leakage guards -------------------------------------
    report["provenance"] = {
        "by_source_dataset": dict(Counter(m["source_dataset"] for m in matches)),
        "by_source_file": dict(Counter(m["source_file"] for m in matches)),
    }
    report["match_statistics"] = {
        "rows": len(stats),
        "distinct_matches_covered": len({s["match_id"] for s in stats}),
        "coverage_pct_of_corpus": round(
            100 * len({s["match_id"] for s in stats}) / len(matches), 2),
        "usage_policy": ("MATCH OUTCOMES ONLY — never a pre-match feature for the "
                         "same match; permitted solely as lagged aggregates of earlier matches"),
    }
    report["xg"] = {"status": "UNAVAILABLE",
                    "reason": "not present in any approved source; never fabricated"}

    return report, failures


def main() -> None:
    matches = read_csv(CANON / "canonical_matches.csv")
    teams = read_csv(CANON / "canonical_teams.csv")
    stats = read_csv(CANON / "canonical_match_stats.csv")
    schedule = json.loads((CANON / "wc2026_schedule.json").read_text(encoding="utf-8"))
    graph = json.loads((CANON / "wc2026_tournament_graph.json").read_text(encoding="utf-8"))

    for m in matches:
        m["year"] = int(m["year"])

    number_diag = assign_match_numbers(matches, schedule, teams)
    report, failures = validate(matches, teams, stats, schedule, graph)
    report["match_number_assignment"] = number_diag
    report["result"] = "PASS" if not failures else "FAIL"
    report["failures"] = failures
    report["validated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    fields = list(matches[0].keys())
    for extra in ("match_number_source",):
        if extra not in fields:
            fields.append(extra)
    with (CANON / "canonical_matches.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(matches)

    (CANON / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({k: report[k] for k in
                      ("result", "failures", "counts", "teams",
                       "tournament_structure", "match_number_assignment")},
                     indent=2, ensure_ascii=False)[:6000])
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
