# Database Schema — WC 2026 Upgrade

FIFA AI Score Prediction Platform. PostgreSQL / Supabase. Written 2026-07-03
by the Database Engineering wave.

This document describes the target-state schema after the WC2026 upgrade,
what changed vs. the original schema, and the reasoning behind the new
design decisions. It complements (does not replace) the inline comments in
`database/schema.sql` and `database/migrations/002_wc2026_upgrade.sql`.

**Update 2026-07-04 — applied and verified against the live database.**
Raw network access to the live Supabase project (`<project-ref>`)
became reachable from this dev environment for the first time today. The
migration and seed described in this document **have been run** against
that live instance: `team_statistics` and `tournament_stages` exist, the new
`teams`/`matches` columns are present, and a direct query confirms 419 rows
in `matches` with a non-NULL `data_source` (330 `wc_2002_2022_dataset` + 89
`wc_2026_live`) and 132 rows in `team_statistics` — exactly matching the
expected counts below. Two real bugs surfaced only once the live DB was
queryable (previously undetectable, since there was no live DB to run
against): the inference-time query in `app/ml/data/loader.py` needed an
explicit `data_source IS NOT NULL` filter (the `matches` table also still
carries ~49,389 rows from the superseded broad 1872-2017 seed, which would
otherwise leak into live inference), and `app/models/match.py`'s SQLAlchemy
columns were typed `String` against what are actually native Postgres
`uuid` columns, breaking joins. Both are fixed — see `CHANGELOG.md`. The
former "not reachable" framing throughout the rest of this document (below)
describes the state as of 2026-07-03, when it was written and true; it is
left as historical record within each section rather than rewritten, but do
not take "not reachable" / "never applied" statements below at face value —
see "Open questions" at the end for the current, corrected status.

---

## Files produced / changed

| File | Status | Purpose |
|---|---|---|
| `database/schema.sql` | Modified | Target-state DDL for a fresh install (includes all WC2026 additions) |
| `database/migrations/002_wc2026_upgrade.sql` | New | Additive `ALTER`/`CREATE` statements to evolve an existing (already-deployed) database to the target state, without dropping/renaming anything |
| `database/generate_seed_wc2026.py` | New | Reads the 3 processed CSVs, emits `seed_wc2026.sql` (pure text generator, no DB connection) |
| `database/seed_wc2026.sql` | New (generated) | INSERT statements: 72 teams, 419 matches, 132 team_statistics rows |
| `database/seed.sql` | Modified (header only) | Marked superseded for the WC2026-only focus; left in place, unrun |
| `database/seed_fifa_2026_teams.sql` | Unchanged | Still valid — `seed_wc2026.sql`'s team UPSERT enriches the same rows (matches on `name`) rather than conflicting with them |
| `backend/app/models/match.py` | Modified | SQLAlchemy models updated to match the new DDL exactly (kept truthful per the file's own stated purpose) |

Run order for a **fresh database**: `schema.sql` → `seed_wc2026.sql` (optionally `seed_fifa_2026_teams.sql` first/instead, since `seed_wc2026.sql`'s UPSERT is a superset of it).

Run order to **upgrade an existing database**: `migrations/002_wc2026_upgrade.sql` → `seed_wc2026.sql`.

---

## New / changed tables and columns (for the Backend/API wave)

### `teams` (existing table, columns added)

| Column | Type | Notes |
|---|---|---|
| `fifa_ranking` | `INTEGER` | **Existing column, reused** — now populated from `teams_reference.csv.fifa_ranking_pre_tournament` for the 48 WC2026 teams. |
| `elo_rating` | `SMALLINT` | **New.** From `teams_reference.csv.elo_rating`. NULL for historical-only teams. |
| `fifa_code` | `VARCHAR(3)` | **New.** e.g. `MEX`, `RSA`. NULL for historical-only teams. Partial unique index (unique only where non-NULL). |
| `wc2026_group` | `CHAR(1)` | **New.** Group letter A-L. NULL outside the 2026 field. |
| `ranking_updated_at` | `TIMESTAMPTZ` | **New.** Auto-maintained by trigger `teams_ranking_updated_at` whenever `fifa_ranking` or `elo_rating` changes. |

New indexes: `idx_teams_elo_rating`, `idx_teams_wc2026_group` (partial), `idx_teams_fifa_code_unique` (partial unique).

### `matches` (existing table, columns added, one constraint relaxed)

| Column | Type | Notes |
|---|---|---|
| `away_team_id` | `UUID`, **now nullable** | Was `NOT NULL`. Relaxed because one real fixture (WC2026 Round-of-16, Canada vs. TBD advancement) has a genuinely unresolved opponent — represented as `NULL`, not a fabricated placeholder team. `chk_different_teams` still holds (`NULL != x` does not violate the CHECK). |
| `stage_id` | `SMALLINT` FK → `tournament_stages(stage_id)`, `ON DELETE RESTRICT` | **New.** Normalized alongside the existing `stage` VARCHAR column (kept as-is — `app/services/match_service.py` reads `Match.stage` directly as a string today; nothing breaks). Backfilled where `stage` text matches the known vocabulary. |
| `tournament_year` | `SMALLINT` | **New.** From `matches_historical.csv.tournament_year`. |
| `home_xg`, `away_xg` | `NUMERIC(4,2)` | **New.** Expected goals. NULL for 2002-2022 rows (not tracked) and for unplayed fixtures — documented gap, not fabricated. |
| `external_match_id` | `VARCHAR(50)`, partial unique | **New.** Preserves the source `match_id` from `matches_historical.csv` (either a synthesized `hist_<sha1prefix>` string for 2002-2022 rows, or the small integer used by the 2026 live dataset — the same integer space `match_team_stats.csv.match_id` uses). This is the join key `seed_wc2026.sql` uses to attach `team_statistics` rows to the correct match; it is not a replacement for the UUID `id` primary key. |
| `data_source` | `VARCHAR(50)` | **New.** Provenance tag, e.g. `wc_2002_2022_dataset` / `wc_2026_live`. |

New indexes: `idx_matches_stage_id`, `idx_matches_tournament_year`, `idx_matches_external_id_unique` (partial unique).

`chk_scores_non_negative` was widened to explicitly tolerate NULL scores (it already worked correctly for NULL under three-valued CHECK logic, but is now spelled out for clarity).

### `tournament_stages` (new lookup table)

```
stage_id     SMALLINT PRIMARY KEY   -- 1-7
stage_key    VARCHAR(30) UNIQUE     -- 'group_stage', 'round_of_32', 'round_of_16',
                                    -- 'quarter_final', 'semi_final', 'third_place', 'final'
stage_name   VARCHAR(50)            -- 'Group Stage', 'Round of 32', ...
is_knockout  BOOLEAN
sort_order   SMALLINT
```

Seeded with exactly 7 rows (matches `DATA_QUALITY_REPORT.md` file #6 / `tournament_stages.csv` exactly). Public read RLS policy, like `teams`/`matches`.

### `team_statistics` (new table)

```
id                   UUID PRIMARY KEY
match_id             UUID NOT NULL REFERENCES matches(id) ON DELETE RESTRICT
team_id              UUID NOT NULL REFERENCES teams(id) ON DELETE RESTRICT
possession_pct       SMALLINT   (0-100, CHECK)
total_shots          SMALLINT   (>= 0, CHECK)
shots_on_target      SMALLINT   (>= 0, CHECK)
corners              SMALLINT   (>= 0, CHECK)
fouls                SMALLINT   (>= 0, CHECK)
offsides             SMALLINT   (>= 0, CHECK)
saves                SMALLINT   (>= 0, CHECK)
player_of_the_match  VARCHAR(150)
created_at           TIMESTAMPTZ

UNIQUE (match_id, team_id)
```

132 rows seeded (66 matches × 2 teams). 10 completed 2026 matches have no
rows here — a documented source gap (`match_team_stats.csv` simply doesn't
have them), not backfilled. Public read RLS policy.

**Grain decision**: one row per `(match_id, team_id)`, matching the source
CSV exactly. No pre-aggregated "team season averages" table was added —
aggregating per-match stats into rolling/season features is a
feature-engineering concern that belongs in the ML/backend layer (which can
compute whatever rolling windows its models need from this raw grain), not
a storage-layer decision that would bake in one particular aggregation
scheme.

---

## Design rationale

### 1. Why rankings are plain columns, not a history table

The task asks that "rankings should be updated easily in future." Two
designs were considered:

- **(A) Columns on `teams`** (`fifa_ranking`, `elo_rating`,
  `ranking_updated_at`) — chosen.
- **(B) A `team_ranking_history(team_id, snapshot_date, fifa_ranking,
  elo_rating)` table** — rejected for now.

The data we actually have (`teams_reference.csv`) is **one snapshot per
team** — a single pre-tournament ranking and Elo rating, not a time series.
A history table populated with exactly one row per team has no real "over
time" semantics; it's schema complexity paying for a capability the data
doesn't exercise. Design (A):

- Satisfies "updated easily" literally: `UPDATE teams SET fifa_ranking = X
  WHERE id = ...` is all a future ranking refresh needs.
- `ranking_updated_at` is maintained automatically by the
  `teams_ranking_updated_at` trigger (fires only when `fifa_ranking` or
  `elo_rating` actually changes, distinct from the generic `updated_at`
  trigger which fires on any column change) — so "when was this last
  updated" is answerable without extra application logic.
- Does not block adding design (B) later: if a real time series is ever
  needed (e.g. a monthly FIFA ranking ingestion job), `team_ranking_history`
  can be added additively in a future migration without touching these
  columns. Nothing about today's design paints that path shut.

This is a deliberate "build for the data you have, not the data you might
have" call — flagged explicitly in case the Backend/API wave disagrees.

### 2. Why `team_statistics` is a new table at `(match_id, team_id)` grain

`match_team_stats.csv` is already at this grain (132 rows = 66 matches × 2
teams, one row per team per match). Storing it any other way (e.g. wide
columns like `home_possession_pct`/`away_possession_pct` directly on
`matches`) would require picking home/away at write time and would break
the source's natural per-team independence (a team's stats don't care
whether it was designated "home" or "away" for that fixture). Keeping the
source grain:

- Makes the seed script a straight, lossless 1:1 row transcription (simpler
  to verify, easier to re-run/refresh from a newer CSV drop).
- Lets any future query aggregate however it needs (`GROUP BY team_id`,
  `GROUP BY match_id`, join to `matches` for home/away context, etc.)
  without the storage layer having pre-committed to one shape.

### 3. Why `tournament_stages` is a lookup table, not just a CHECK constraint on `matches.stage`

The existing `matches.stage` (free-text `VARCHAR(100)`, no CHECK) allows any
string. A `CHECK (stage IN (...))` would validate values but couldn't carry
the `is_knockout` flag or a display name / sort order — all of which the
source data (`tournament_stages.csv`) already provides and which downstream
consumers (e.g. bracket visualizations, "knockout stage only" filters) will
plausibly want. A proper lookup table normalizes this correctly at
negligible cost (7 static rows).

`matches.stage` (the string column) was **deliberately kept**, not dropped,
because `backend/app/services/match_service.py` reads `Match.stage`
directly as a string today (`stage=m.stage` in `get_matches`). Dropping it
would be a breaking change to code this wave was told not to touch. The new
`stage_id` FK is additive; a future wave can migrate reads to join through
`stage_id` → `tournament_stages` (e.g. for `is_knockout` filtering) at its
own pace.

### 4. Why `away_team_id` became nullable

One real fixture in `matches_historical.csv` (`match_id=89`, WC2026 Round of
16) has an away team that is a literal `"Unknown"` placeholder in the
source — the actual opponent hasn't been determined yet (advancement TBD).
Two options: fabricate a placeholder "TBD" team row and point
`away_team_id` at it, or represent the fact honestly as `NULL`. The task's
"no fabrication" principle (also followed throughout by the Data
Engineering wave) points at `NULL`. The existing `chk_different_teams`
CHECK (`home_team_id != away_team_id`) is unaffected — under SQL
three-valued logic, `home_team_id != NULL` evaluates to `NULL`/unknown,
which does **not** fail a CHECK constraint (CHECKs only fail on an explicit
`FALSE`).

### 5. FK delete behavior — `ON DELETE RESTRICT` for everything new

A prior audit flagged `teams → matches` using `ON DELETE CASCADE` as a
data-loss footgun (deleting a team row silently deletes all its match
history). This upgrade does **not** change that existing constraint
(altering a live FK's delete behavior is a separate, more invasive
migration outside this task's scope), but every **new** foreign key
introduced here — `matches.stage_id → tournament_stages`,
`team_statistics.match_id → matches`, `team_statistics.team_id → teams` —
uses `ON DELETE RESTRICT`, so a delete that would orphan stats/stage data
fails loudly instead of cascading silently. Recommend the Backend/API or a
future ops wave revisit the original `teams → matches` `CASCADE` separately.

### 6. `external_match_id` as a traceability key, not a new primary key

`matches.id` (UUID) remains the primary key — nothing that already
references `matches.id` breaks. `external_match_id` is an additional,
independently-unique column that preserves the source CSV's `match_id`
(string) purely for traceability and as the join key the seed script uses
to attach `team_statistics` rows. It intentionally is **not** used as a FK
target from `team_statistics` (which references `matches.id` directly) —
`external_match_id` is provenance metadata, not a relational key.

---

## `teams` population summary (from `seed_wc2026.sql`)

- **48 WC2026 teams**: full row from `teams_reference.csv` — `confederation`,
  `fifa_ranking`, `elo_rating`, `fifa_code`, `wc2026_group` all populated,
  `ranking_updated_at` set to the seed run time.
- **24 historical-only teams** (e.g. Italy, Russia, Wales, Poland — real
  2002-2022 participants not in the 2026 field): inserted with only
  `name`/`country` populated; `confederation`/`fifa_ranking`/`elo_rating`/
  `fifa_code`/`wc2026_group` are `NULL` — genuinely unknown from the
  available source data, not guessed.
- The literal token `"Unknown"` (the one TBD-opponent placeholder) is
  **never** inserted as a team row.
- 72 teams total (48 + 24).

## `matches` population summary

- 419 rows: 330 historical (2002-2022, `data_source = wc_2002_2022_dataset`)
  + 89 real 2026 rows (`data_source = wc_2026_live`).
- `tournament` synthesized as `"FIFA World Cup {tournament_year}"` (the
  source CSV doesn't carry a separate tournament-name column).
- `venue`/`city`: for 2002-2022 rows, the source `venue` field
  (`"Stadium Name, City"`) is split on the last comma into a city value;
  for 2026 rows, `venue`/`city` are `NULL` in the source (documented,
  intentional gap — see `DATA_QUALITY_REPORT.md`, unresolved venue/city
  source conflicts) and are seeded as `NULL`, not fabricated.
- `home_xg`/`away_xg`: `NULL` for all 2002-2022 rows and for not-yet-played
  2026 fixtures; populated for played 2026 matches.
- `stage_id` backfilled for all 419 rows (the source `stage` vocabulary
  matches `tournament_stages.stage_key` exactly, so this is a full
  backfill, not best-effort).

## `team_statistics` population summary

- 132 rows, all for 2026 matches (matched via `external_match_id`).
- 10 completed 2026 matches have zero stats rows — left absent, not
  backfilled (documented in `DATA_QUALITY_REPORT.md`).
- `possession_pct` for a match's two rows does not always sum to 100 (real
  recorded variance) — left as-is.

---

## Known limitations / things intentionally NOT done

- The old `database/seed.sql` (broad 1872-2017 dataset) was left in place,
  unmodified except for a header comment marking it superseded. It is not
  deleted and not run as part of the WC2026 flow.
- The existing `teams → matches` `ON DELETE CASCADE` was **not** changed
  (see rationale #5 above) — flagged for a future, more surgical migration
  if the team wants to fix it.
- `matches.stage` (VARCHAR) was **not** dropped, only supplemented by
  `stage_id` — a future wave can migrate reads off the free-text column.
- Historical (2002-2022) match rows have no `xG`, no venue detail beyond
  city, and — per the Data Engineering wave's report — the source dataset
  itself is missing ~9 matches per tournament (concentrated in the group
  stage). None of this was fabricated or "fixed" here; it's carried through
  as-is from `matches_historical.csv`.

## Open questions — updated 2026-07-04 with live-DB findings

1. **RESOLVED — the migration has now been run against the real database.**
   As of 2026-07-04, `migrations/002_wc2026_upgrade.sql` and
   `seed_wc2026.sql` have been applied to the live Supabase project
   (`<project-ref>`) and the verification counts confirmed directly:
   48 teams with `elo_rating`/`wc2026_group` populated (the WC2026 upsert
   target — `teams` itself has 335 rows total, since it was seeded into a
   pre-existing broader table; see item 2 below), 419 matches with
   `external_match_id`/`data_source` set (330 `wc_2002_2022_dataset` + 89
   `wc_2026_live`), 132 `team_statistics` rows. Spot-checked against real
   history (Brazil 2-0 Germany, 2002 final; Brazil 1-7 Germany, 2014
   semi-final — both correct) and canonical team naming (`Türkiye`, `Cabo
   Verde`, `USA`).
2. **RESOLVED, with a live-data nuance — existing production data.** The
   live database did already have rows in `matches`/`teams` from the old
   broad seed (1872-2017 dataset) before this migration: `matches` has
   49,389 total rows today, of which only 419 carry a non-NULL
   `data_source` (the WC-only rows this document describes). The old rows
   were **kept, not purged** — `seed_wc2026.sql`'s team UPSERT merged
   cleanly on `name` as anticipated, and the pre-existing non-WC rows
   coexist unchanged alongside the new WC-only rows exactly as this section
   predicted. The query-layer filtering this item asked about has been
   decided **for the ML pipeline** (`app/ml/data/loader.py` now filters
   `WHERE data_source IS NOT NULL`) but **not yet for the public API** —
   `GET /api/v1/matches` and `/analytics/dashboard` still query/count the
   full unfiltered table. This is now the single most significant open item
   from this pass — see `KNOWN_ASSUMPTIONS.md` for the full writeup; it's a
   product decision, not something resolved here.
3. **`teams → matches` `ON DELETE CASCADE`**: still unresolved from the
   prior audit; left untouched here as out of scope, but worth a dedicated
   migration if team deletion is ever a real operational path.
4. **File #7 fifa_ranking disagreement**: `DATA_QUALITY_REPORT.md` notes
   34/48 teams have a different FIFA ranking in the wallchart source
   (file #7) vs. `teams_reference.csv` (file #5), likely two different
   ranking-list dates. This upgrade seeds only `teams_reference.csv`'s
   ranking, per the Data Engineering wave's instructions — flagging again
   here in case a later reconciliation pass is wanted.
