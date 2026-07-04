# Data Pipeline

End-to-end data flow for the FIFA World Cup 2026 AI Prediction Platform: raw
source files → normalized/processed CSVs → ML training / inference → database
seeding. Grounded in the current source as of 2026-07-04 (the Data
Engineering / Database Engineering / ML retraining waves). See
`backend/app/data/processed/DATA_QUALITY_REPORT.md` for the exhaustive,
row-level version of section 1 below; this document is the map of how the
pieces connect.

**Update, later on 2026-07-04:** the live Supabase database became reachable
from this dev environment for the first time today. Sections 2.2, 2.3, and 5
below were originally written on the (accurate, at the time) assumption that
the DB was unreachable and `seed_wc2026.sql` had never been run — that has
since changed. The seed **has** been applied and verified (419 `matches`
rows with `data_source` set, 132 `team_statistics` rows — see
`DATABASE_SCHEMA.md`'s "Open questions" for the full verification), and the
backend has been booted against the live DB and used to serve real
predictions and tournament simulations. One real bug was found and fixed in
the inference-time query described in §2.2 as a direct result of this — see
the correction inline below and `CHANGELOG.md`.

---

## 1. Raw source files → processed CSVs

Seven raw files at the repo root, none of them touched or modified in place:

| # | File | Rows | Content |
|---|---|---|---|
| 1 | `FIFA_World_Cup_Matches(b42022).xlsx` (sheet "Cleaned Data") | 330 | WC matches 2002-2022 |
| 2 | `matches.csv.xlsx` (sheet "matches") | 89 | 2026 matches, IDs |
| 3 | `matches_detailed.csv.xlsx` (sheet "matches_detailed") | 89 | 2026 matches, names |
| 4 | `match_team_stats.csv.xlsx` (sheet "match_team_stats") | 132 | 2026 per-match team box-score stats |
| 5 | `teams(group_rank).csv.xlsx` (sheet "teams") | 48 | 2026 team roster |
| 6 | `tournament_stages.csv.xlsx` (sheet "tournament_stages") | 7 | Stage lookup |
| 7 | `wc_2026_fixtures(b4ro32).xlsx` (sheet "wc_2026_fixtures") | 104 | Pre-tournament fixture template |

A one-time Data Engineering pass normalized, cross-checked, and merged these
into three processed outputs under `backend/app/data/processed/`:

| Output | Rows | Produced from |
|---|---|---|
| `matches_historical.csv` | 419 (330 historical 2002-2022 + 89 real 2026) | Files #1 + #2/#3 |
| `teams_reference.csv` | 48 | File #5 |
| `match_team_stats.csv` | 132 | File #4 |

Normalization work performed (full detail in `DATA_QUALITY_REPORT.md`):
mojibake/double-UTF-8 fixes (`Türkiye`, `Curaçao`, `Côte d'Ivoire`), team-name
canonicalization across all 7 sources onto one 79-entry mapping table (e.g.
`Czech Republic` → `Czechia`, `Turkey` → `Türkiye`, `United States` → `USA`),
and a synthesized deterministic `match_id` for the 330 pre-2026 rows
(`hist_<sha1(...)[:10]>`, zero collisions verified) since file #1 has no
native match ID. `database/schema.sql`, `database/seed.sql`, and the trusted
`app/data/fifa_2026/*.json` reference files were **not** touched by this pass
— see §3.

**No fabrication policy**: every gap below was left as a genuine `NULL`/
absence rather than backfilled with a plausible-looking guess. This is the
same policy the Database Engineering wave followed when seeding these CSVs
into Postgres (`DATABASE_SCHEMA.md`).

### `matches_historical.csv` schema

```
match_id, home_team, away_team, home_score, away_score, date, stage,
tournament_year, venue, city, home_xg, away_xg, source, status
```

- `match_id`: `hist_<sha1prefix>` for 2002-2022 rows, small integer (same
  space as `match_team_stats.csv.match_id`) for 2026 rows.
- `status`: `Completed` or `Scheduled` (13 not-yet-played 2026 fixtures).
- `home_xg`/`away_xg`: populated only for played 2026 matches; `NULL` for all
  2002-2022 rows (not tracked by that source) and unplayed 2026 fixtures.
- `venue`/`city`: for 2002-2022 rows, split from the source's `"Stadium,
  City"` string; `NULL` for all 2026 rows — neither file #2 nor file #3 (the
  two 2026 sources used) carry venue/city, and a trial join against file #7
  by (date, team-pair) only resolved unambiguously for 46/88 matches given
  documented date/pairing discrepancies between file #7 and the trusted
  `schedule.json` (§3) — populating the rest would have meant asserting
  unverified data as fact, so it was left `NULL`.
- One row (`match_id=89`, WC2026 Round of 16) has `away_team = "Unknown"` in
  the raw merge — the genuinely undetermined TBD opponent for Canada's
  advancement. Downstream consumers (feature engineering, the DB seed script)
  treat this token as a placeholder, never as a real team.
- File `#1`'s known gap: every 2002-2022 tournament has only ~55 of the
  expected 64 matches (missing ~9 per tournament, concentrated in the group
  stage, plus the entire 2002 third-place match) — a pre-existing gap in the
  source dataset itself, not introduced by this merge and not backfilled.

### `teams_reference.csv` schema

```
canonical_name, fifa_code, group, confederation, fifa_ranking_pre_tournament, elo_rating
```

48 rows, one per 2026 World Cup team only (does not cover the ~25 additional
nations that appear only in the 2002-2022 portion of `matches_historical.csv`
— see `RANKINGS_INTEGRATION.md` §5 for the exact list and how feature
engineering handles that gap with `NaN`, never a fabricated rank).

**Read with `encoding="utf-8-sig"`** — the file is Excel-exported and starts
with a UTF-8 BOM; reading with plain `utf-8` silently renames the first
column to `"﻿canonical_name"`, and every dict-based lookup keyed on
`"canonical_name"` then misses 100% of the time with no error. All three
processed CSVs share this requirement; every current reader
(`feature_engineering.py::_load_teams_reference()`,
`train.py::load_data()`, `generate_seed_wc2026.py`) reads them correctly.

### `match_team_stats.csv` schema

```
match_id, team_id, team_name, possession_pct, total_shots, shots_on_target,
corners, fouls, offsides, saves, player_of_the_match
```

132 rows = 66 matches × 2 teams. Covers **only 2026 matches**, and only 66 of
the 76 completed 2026 matches at that — 10 completed matches
(`match_id ∈ {53,54,55,57,58,59,60,61,62,63}`) have no stats rows at all, a
gap in the source file itself (`DATA_QUALITY_REPORT.md` §a file #4), left
absent rather than backfilled. `possession_pct` for a match's two rows does
not always sum to 100 (real recorded variance, left as-is).

This file is **not** currently consumed by feature engineering or training
(see `FEATURE_ENGINEERING.md` §3 — box-score stats were evaluated and
explicitly excluded as a candidate feature source, both for sparsity — only
16% of historical matches have any row — and leakage risk, since
possession/shots/corners are in-match outcome stats, not known before
kickoff). Its only current consumer is the database seed path (§3) and the
`team_statistics` table it feeds, which `GET /matches/{match_id}` reads back
out (`app/services/match_service.py::get_match_by_id`).

---

## 2. How the ML pipeline consumes the processed data

There are **two separate readers** of match data in this codebase, serving
different purposes, and they currently read from **different sources**:

### 2.1 Training — `backend/app/ml/train.py::load_data()`

Reads `backend/app/data/processed/matches_historical.csv` **directly**, not
the Postgres `matches` table. This was a deliberate choice at the time, not
a fallback: the live Supabase DB was unreachable from the sandbox the
2026-07-03/04 retrain was done in (confirmed `ENOTFOUND` on the pooler
host), and `database/seed_wc2026.sql` (§3) loads this exact same CSV content
into Postgres, so CSV-based and DB-based training were expected to produce
the same feature matrix once the DB became reachable — reading the CSV
directly was not a lesser substitute for this dataset.

**Update 2026-07-04, later the same day:** the DB is now reachable and the
seed has been applied and verified (§3, §5). Training still defaults to the
CSV path described here — that has not changed — but the "once the DB is
reachable" condition above has now actually been met, and `load_data_from_db()`
is a genuine, usable alternative today, not just a placeholder for a future
environment.

- Reads with `encoding="utf-8-sig"`.
- Filters to `status == "Completed"` (case-insensitive) with non-null scores
  — the same "completed matches only" contract a DB-backed query would
  enforce via `WHERE m.status = 'completed'`.
- Synthesizes `tournament = "FIFA World Cup"` and `neutral_venue = True` for
  every row (the CSV has no such columns — every row is a WC match by
  construction, and nearly all WC matches are neutral-site for at least one
  side).
- Sorts ascending by `date`.
- `MIN_HISTORY = 30` rows are skipped as warmup before the first feature row
  is built (reduced from the old broad-dataset default of 100, since this
  WC-only corpus starts at 2002 with no prior history — skipping 100 would
  discard almost two entire tournaments).
- A DB-backed alternative, `load_data_from_db()`, is kept in the same module
  for environments where Postgres *is* reachable and for future
  parity/reconciliation checks — it runs the equivalent
  `SELECT ... FROM matches JOIN teams ...` query the old pipeline used, but
  is **not** called by `main()` by default today.

### 2.2 Inference — `backend/app/ml/data/loader.py::load_matches_dataframe()`

Reads from the **Postgres `matches`/`teams` tables**, not the processed
CSVs — this is the request-time path used by every live prediction
(`prediction_service.py`) and by the tournament simulator
(`tournament.py`'s `_get_simulator_dependencies()`):

```sql
SELECT m.date, ht.name AS home_team, at.name AS away_team,
       m.home_score, m.away_score, m.tournament, m.neutral_venue,
       m.city, m.country, m.stage
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
JOIN teams at ON m.away_team_id = at.id
WHERE m.status = 'completed'
  AND m.data_source IS NOT NULL
ORDER BY m.date ASC
```

- Cached in-process with a 6-hour TTL (`CACHE_TTL_HOURS`), refreshed lazily
  on the first request after expiry — not a per-request DB round-trip.
- `compute_dynamic_elo(df)` is run once here, immediately before caching
  (see `ELO_SYSTEM.md` for the bug this fixed) — both the predictor and the
  tournament simulator consume the same enriched, cached DataFrame.
- **Fixed 2026-07-04 — `data_source IS NOT NULL` filter added.** Now that the
  live DB is reachable, this query was found to omit a scope filter: the
  live `matches` table holds 49,389 total rows, of which only 419 carry a
  non-NULL `data_source` (the WC-only corpus this document describes — 330
  `wc_2002_2022_dataset` + 89 `wc_2026_live`). Without the filter, this query
  would have handed every live prediction and tournament simulation a
  ~49k-row, non-WC-scoped DataFrame — a severe train/serve skew versus the
  419-row corpus the shipped model was actually trained on (§2.1) — silently,
  since nothing before today could exercise this query against real data to
  notice. The filter is now in place; see `CHANGELOG.md`'s 2026-07-04
  validation-pass entry.
- **Live-verified 2026-07-04**: `database/seed_wc2026.sql` (§3) has been run
  against the live database and confirmed — 419 WC-scoped `matches` rows, 132
  `team_statistics` rows — and the backend was booted directly against this
  live DB and used to serve real predictions (6 matchups) and tournament
  simulations (100/1000/5000 iterations), all successful. Inference no
  longer depends on a hypothetical future seed run; it is running against
  live, seeded data today.

### 2.3 Net effect: training and inference are on two different sources, now verified consistent

Training (CSV) and inference (DB) reading from different places is
consistent *only* as long as `seed_wc2026.sql` has been run against the
target Postgres instance with matching content, **and** the inference query
is correctly scoped to the same WC-only rows. As of 2026-07-04, both
conditions are confirmed true: the seed has been applied (§3, §5), and the
`data_source IS NOT NULL` filter fixed in §2.2 keeps the inference query
scoped to the same 419-row WC-only corpus training reads from the CSV.
Before this filter was added, the two sources would *not* actually have
matched even with the seed applied — the DB query would have returned the
full ~49,389-row legacy table, not the 419-row WC-only slice. That gap is
now closed for the ML pipeline specifically. It is **not** closed for the
public API — `GET /api/v1/matches` and `/analytics/dashboard` still query
the full unfiltered table; see `KNOWN_ASSUMPTIONS.md` for that open item.

---

## 3. Official schedule/groups reference — separate from the match-history pipeline

`backend/app/data/fifa_2026/{groups.json, schedule.json, venues.json}` are a
**separate, trusted, hand-extracted reference dataset** — sourced from the
official FIFA World Cup 2026 Match Schedule wallchart PDF (extracted
2026-07-02), not from any of the 7 raw xlsx/csv files and not regenerated by
the Data Engineering merge above. They were treated as read-only ground
truth throughout this session's work:

- The Data Engineering wave's own cross-check (`DATA_QUALITY_REPORT.md` §d)
  compared `groups.json`/`schedule.json` against the raw fixture template
  (file #7) and found the group-letter assignments and total/per-stage match
  counts agree exactly, but documented several date/venue/matchup
  discrepancies between `schedule.json` and file #7 (notably a genuine
  Group C matchday-2 pairing conflict) — left unresolved for a future wave
  to adjudicate against an authoritative source, not silently picked one
  side.
- The tournament simulator (`tournament_simulator.py`) uses
  `get_groups_as_team_codes()` (from `groups.json`) as its default bracket
  source, and `schedule.json` directly to resolve the *real* Round-of-32
  bracket pairings once the group stage is complete (`_load_real_r32_bracket`
  — see `TOURNAMENT_ENGINE.md`), bridging team names between
  `matches_historical.csv`'s display names and `schedule.json`'s fifa_codes
  via `teams_reference.csv`'s `canonical_name → fifa_code` map.
- Loaded via `app/data/fifa_2026/__init__.py`'s `lru_cache`-wrapped
  accessors, resolved relative to the module's own file location (works
  regardless of process working directory). Full provenance and documented
  gaps (no stadium names, all kickoff times ET, one placeholder-code
  inference for the bronze final/final) live in
  `backend/app/data/fifa_2026/README.md` and `KNOWN_ASSUMPTIONS.md` item (a).

---

## 4. Known, documented data gaps (summary)

Full detail in `backend/app/data/processed/DATA_QUALITY_REPORT.md`; summarized
here as the gaps that matter for anyone consuming the processed data or the
database:

| Gap | Scope | Handling |
|---|---|---|
| ~9 missing matches per WC tournament (2002-2022) | `matches_historical.csv`, ~330-row historical portion | Not backfilled — pre-existing gap in the Kaggle-derived source (file #1) itself |
| 2002 third-place match entirely missing | Same | Not backfilled |
| 10 completed 2026 matches with no team-stats rows | `match_team_stats.csv` (`match_id` 53-55, 57-63) | Left absent, not backfilled |
| 2026 `venue`/`city` are `NULL` | `matches_historical.csv`, all 89 2026 rows | Not fabricated — see §1's `venue`/`city` note |
| One `away_team = "Unknown"` (TBD Round-of-16 opponent) | `matches_historical.csv` match_id 89 | Treated as a placeholder token everywhere downstream, never a real team; seeded as SQL `NULL` for `away_team_id` |
| `teams_reference.csv` covers only 48 of ~73 historical teams | Feature engineering (`fifa_rank_diff`, `same_confederation`) | `NaN` for the ~25 historical-only teams, never a fabricated rank — see `RANKINGS_INTEGRATION.md` §5 |
| File #7 `fifa_rank` disagrees with `teams_reference.csv` for 34/48 teams | Raw source only — not merged | `teams_reference.csv`'s ranking (file #5) is the only one seeded/used anywhere; file #7's is unused |
| Encoding: UTF-8 BOM on all 3 processed CSVs | `matches_historical.csv`, `teams_reference.csv`, `match_team_stats.csv` | Must read with `encoding="utf-8-sig"` everywhere — silent, no-error failure mode if read as plain `utf-8` |

---

## 5. Database seeding path

```
teams_reference.csv, matches_historical.csv, match_team_stats.csv
        │
        ▼  (pure text generator, no DB connection)
database/generate_seed_wc2026.py
        │
        ▼
database/seed_wc2026.sql   (72 teams, 419 matches, 132 team_statistics rows)
```

Run order:
- **Fresh database**: `database/schema.sql` → `database/seed_wc2026.sql`.
- **Upgrading an existing database**: `database/migrations/002_wc2026_upgrade.sql`
  → `database/seed_wc2026.sql`.

`generate_seed_wc2026.py` reads all three CSVs with `encoding="utf-8-sig"`,
resolves team names to rows via the same canonicalized names
`DATA_QUALITY_REPORT.md` established, joins `match_team_stats.csv` to
`matches` via `external_match_id` (the small-integer 2026 match ID space),
and emits idempotent `INSERT ... ON CONFLICT` statements — safe to re-run.

**Applied and verified against the live Supabase instance, 2026-07-04.** The
database became reachable from this dev environment for the first time
today; `seed_wc2026.sql` and the migration (previously hand-reviewed,
verified-by-inspection SQL waiting on live access — see `DATABASE_SCHEMA.md`'s
"Open questions") have now actually been run. The verification counts were
checked directly against the live database: 419 `matches` rows with
`external_match_id`/`data_source` set (330 `wc_2002_2022_dataset` + 89
`wc_2026_live`), 132 `team_statistics` rows, 48 teams with `elo_rating`/
`wc2026_group` populated — all matching expectations. The live `matches`/
`teams` tables now do reflect this WC-only corpus (alongside the
pre-existing ~49,389-row legacy table, which was not purged — see §2.3 and
`KNOWN_ASSUMPTIONS.md` for the resulting open item on API scope).

---

## 6. Summary diagram

```
Repo root (7 raw xlsx/csv files)
        │  one-time Data Engineering normalization/merge
        ▼
backend/app/data/processed/
  ├── matches_historical.csv   (419 rows)
  ├── teams_reference.csv      (48 rows)
  ├── match_team_stats.csv     (132 rows)
  └── DATA_QUALITY_REPORT.md   (full provenance report)
        │                                   │
        │ train.py::load_data()             │ generate_seed_wc2026.py
        ▼ (direct CSV read)                 ▼ (pure text generator)
  Model training (train.py)          database/seed_wc2026.sql
        │                                   │
        │ writes                            │ APPLIED 2026-07-04 to
        ▼                                   ▼ live Supabase (verified)
  xgboost_model.pkl, scaler.pkl      matches / teams / team_statistics
                                            │
                                            │ loader.py::load_matches_dataframe()
                                            ▼ (DB read, WHERE data_source IS
                                              NOT NULL, 6h TTL cache)
                                      Live prediction / tournament simulation

app/data/fifa_2026/{groups,schedule,venues}.json
        (separate, hand-extracted, trusted reference —
         official schedule/groups/venues, not derived from
         the 7 raw files or the processed CSVs above)
```
