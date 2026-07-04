-- ============================================================
-- Migration 002: WC 2026 Upgrade
-- FIFA AI Score Prediction Platform — PostgreSQL / Supabase
--
-- Purpose: evolve the existing schema (results.csv-era, "all competitions
-- 1872-2017" broad dataset) to support the WC-2026-focused data produced by
-- the Data Engineering wave:
--   backend/app/data/processed/teams_reference.csv       (48 rows)
--   backend/app/data/processed/matches_historical.csv    (419 rows)
--   backend/app/data/processed/match_team_stats.csv      (132 rows)
--
-- This migration is ADDITIVE and non-destructive:
--   - No existing table is dropped or renamed.
--   - No existing column is dropped or renamed.
--   - New nullable columns are added to `teams` and `matches`.
--   - Three new tables are created: tournament_stages, team_statistics,
--     and a supporting extension to `teams` for rankings (columns only,
--     see rationale below — no new ranking table).
--
-- Run this against the live Supabase Postgres instance via the SQL editor
-- or `psql`. Safe to re-run (uses IF NOT EXISTS / IF NOT EXISTS guards
-- throughout) except where noted.
--
-- Apply AFTER database/schema.sql (001) has already been applied.
-- ============================================================

BEGIN;

-- ─── 1. Rankings: extend `teams` with current FIFA ranking + Elo ─────────────
--
-- DESIGN DECISION (see DATABASE_SCHEMA.md for full rationale): we store
-- rankings as plain columns on `teams`, NOT a separate history/time-series
-- table. The only ranking data we have is a single pre-tournament snapshot
-- per team (teams_reference.csv: fifa_ranking_pre_tournament, elo_rating) —
-- there is no second snapshot to build a real history off of yet. Modeling
-- a history table today would mean a table with exactly one row per team
-- and no actual "over time" semantics, which is pure speculative
-- over-engineering. Instead:
--   - `fifa_ranking` and `elo_rating` become simple, updatable columns.
--   - `ranking_updated_at` timestamps the last update, so "updated easily
--     in future" is satisfied by a plain UPDATE statement changing the
--     value and bumping the timestamp (a trigger keeps this automatic).
--   - If a real time series is needed later (e.g. monthly FIFA ranking
--     pulls), a `team_ranking_history(team_id, snapshot_date, fifa_ranking,
--     elo_rating)` table can be added additively later without touching
--     these columns — this design does not block that evolution.
--
-- NOTE: `teams.fifa_ranking` already exists (INTEGER) from schema.sql v1.
-- We reuse it rather than adding a duplicate column. We only add elo_rating
-- and the bookkeeping columns needed for the "easily updatable" requirement,
-- plus columns to carry the other WC-2026-specific reference fields
-- (fifa_code, group letter) that teams_reference.csv provides.

ALTER TABLE teams ADD COLUMN IF NOT EXISTS fifa_code VARCHAR(3);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS wc2026_group CHAR(1);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS elo_rating SMALLINT;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS ranking_updated_at TIMESTAMPTZ;

-- fifa_code is unique when present (not all 73 teams in the historical data
-- have a code — only the current 48-team WC2026 field does), so a partial
-- unique index is used rather than a plain UNIQUE constraint.
CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_fifa_code_unique
    ON teams (fifa_code) WHERE fifa_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_teams_wc2026_group ON teams (wc2026_group)
    WHERE wc2026_group IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_teams_elo_rating ON teams (elo_rating);

COMMENT ON COLUMN teams.fifa_ranking IS
    'Current/most-recent known FIFA world ranking (lower is better). '
    'For the 2026 field this is the pre-tournament ranking from '
    'teams_reference.csv. Update in place as new rankings are published; '
    'ranking_updated_at is bumped automatically by trigger.';
COMMENT ON COLUMN teams.elo_rating IS
    'Elo rating snapshot (higher is better), sourced from '
    'teams_reference.csv (elo_rating) for the WC2026 field. NULL for '
    'historical-only teams not in the 2026 field.';
COMMENT ON COLUMN teams.fifa_code IS
    'FIFA 3-letter team code (e.g. MEX, RSA). Populated for the 48 '
    'WC2026 teams; NULL for historical-only teams.';
COMMENT ON COLUMN teams.wc2026_group IS
    'WC2026 group-stage letter (A-L). NULL for historical-only teams '
    'and for non-WC2026 context.';

-- Keep ranking_updated_at current automatically whenever fifa_ranking or
-- elo_rating changes (distinct from the generic updated_at trigger, which
-- fires on ANY column change).
CREATE OR REPLACE FUNCTION update_ranking_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.fifa_ranking IS DISTINCT FROM OLD.fifa_ranking)
       OR (NEW.elo_rating IS DISTINCT FROM OLD.elo_rating) THEN
        NEW.ranking_updated_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS teams_ranking_updated_at ON teams;
CREATE TRIGGER teams_ranking_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_ranking_timestamp();

-- ─── 2. tournament_stages lookup table ────────────────────────────────────────
--
-- Source: DATA_QUALITY_REPORT.md file #6 (tournament_stages.csv.xlsx),
-- 7 canonical stages with an is_knockout flag. `matches.stage` (existing
-- VARCHAR column) is preserved as-is for backward compatibility with
-- current API/service code (backend/app/services/match_service.py reads
-- Match.stage directly as a string) — we ADD a normalized stage_id FK
-- alongside it rather than replacing it, so existing reads keep working
-- while new/normalized consumers can join through stage_id instead of
-- matching on free-text strings.

CREATE TABLE IF NOT EXISTS tournament_stages (
    stage_id        SMALLINT PRIMARY KEY,
    stage_key       VARCHAR(30) NOT NULL UNIQUE,   -- e.g. 'group_stage', matches CSV vocabulary
    stage_name      VARCHAR(50) NOT NULL,           -- e.g. 'Group Stage', display label
    is_knockout     BOOLEAN NOT NULL,
    sort_order      SMALLINT NOT NULL
);

INSERT INTO tournament_stages (stage_id, stage_key, stage_name, is_knockout, sort_order) VALUES
    (1, 'group_stage',   'Group Stage',        FALSE, 1),
    (2, 'round_of_32',   'Round of 32',        TRUE,  2),
    (3, 'round_of_16',   'Round of 16',        TRUE,  3),
    (4, 'quarter_final', 'Quarter-finals',     TRUE,  4),
    (5, 'semi_final',    'Semi-finals',        TRUE,  5),
    (6, 'third_place',   'Third-place Match',  TRUE,  6),
    (7, 'final',         'Final',              TRUE,  7)
ON CONFLICT (stage_id) DO NOTHING;

ALTER TABLE tournament_stages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "tournament_stages_public_read" ON tournament_stages;
CREATE POLICY "tournament_stages_public_read" ON tournament_stages
    FOR SELECT USING (true);

ALTER TABLE matches ADD COLUMN IF NOT EXISTS stage_id SMALLINT
    REFERENCES tournament_stages(stage_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_matches_stage_id ON matches (stage_id);

-- Best-effort backfill of stage_id from the existing free-text `stage`
-- column for rows that already match the known vocabulary (older/legacy
-- data may use different casing/labels from the old Kaggle-derived seed,
-- e.g. 'FIFA World Cup' — those are intentionally left NULL rather than
-- guessed).
UPDATE matches m
SET stage_id = ts.stage_id
FROM tournament_stages ts
WHERE m.stage_id IS NULL
  AND lower(regexp_replace(m.stage, '[\s-]+', '_', 'g')) = ts.stage_key;

-- ─── 3. matches: identity + external id + xG + WC-year columns ────────────────
--
-- matches_historical.csv match_id is a string (either a synthesized
-- "hist_<sha1>" id for 2002-2022 rows, or a plain small integer for the
-- 89 real 2026 rows). It is NOT a UUID and is NOT the same value space as
-- matches.id (UUID PK) in the existing schema. We keep matches.id as the
-- UUID PK (unchanged — nothing referencing it breaks) and add a separate
-- external_match_id column to preserve traceability back to the source
-- CSV / to match_team_stats (which is keyed by the same small-integer
-- match_id space for the 2026 matches only).

ALTER TABLE matches ADD COLUMN IF NOT EXISTS external_match_id VARCHAR(50);
ALTER TABLE matches ADD COLUMN IF NOT EXISTS tournament_year SMALLINT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_xg NUMERIC(4,2);
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_xg NUMERIC(4,2);
ALTER TABLE matches ADD COLUMN IF NOT EXISTS data_source VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_external_id_unique
    ON matches (external_match_id) WHERE external_match_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_matches_tournament_year ON matches (tournament_year);

COMMENT ON COLUMN matches.external_match_id IS
    'Source-system match identifier from matches_historical.csv (either a '
    'synthesized "hist_<sha1prefix>" id for 2002-2022 rows, or the small '
    'integer match_id used by the 2026 live dataset and by '
    'match_team_stats.match_id). Not a surrogate for matches.id; kept for '
    'traceability/joins back to source CSVs and to team_statistics.';
COMMENT ON COLUMN matches.home_xg IS
    'Expected goals (home). NULL for 2002-2022 historical rows (xG not '
    'tracked/available for that era) and for not-yet-played 2026 fixtures '
    '-- these are genuine data gaps, not defects (see DATA_QUALITY_REPORT.md).';
COMMENT ON COLUMN matches.away_xg IS 'Expected goals (away). See home_xg.';
COMMENT ON COLUMN matches.data_source IS
    'Provenance tag from matches_historical.csv "source" column, e.g. '
    'wc_2002_2022_dataset or wc_2026_live.';

-- Allow away_team_id to be NULL: matches_historical.csv match_id=89 (Round
-- of 16, Canada vs TBD) has a genuinely unresolved opponent slot ("Unknown"
-- placeholder in the source, NOT inserted as a real team row — see seed
-- script/DATABASE_SCHEMA.md). The existing NOT NULL constraint must be
-- relaxed to represent this correctly instead of fabricating a placeholder
-- team.
ALTER TABLE matches ALTER COLUMN away_team_id DROP NOT NULL;

-- chk_different_teams already tolerates NULL (NULL != x is NULL/unknown,
-- which does not violate a CHECK), so no change needed there.

-- ─── 4. Tighten FK delete behavior for new relationships ──────────────────────
--
-- A prior audit flagged ON DELETE CASCADE from teams -> matches as a
-- data-loss footgun (deleting a team silently wipes match history). We do
-- NOT change the existing teams->matches FKs here (that would be a
-- separate, riskier migration touching live constraint definitions and is
-- out of scope for this additive upgrade) but we deliberately use
-- ON DELETE RESTRICT for every NEW foreign key introduced in this
-- migration (team_statistics -> matches/teams, matches -> tournament_stages)
-- so we do not introduce more of the same footgun going forward.

-- ─── 5. team_statistics: per-match, per-team stats ────────────────────────────
--
-- Grain matches the source exactly: one row per (match_id, team_id), i.e.
-- match_team_stats.csv's natural key. This is deliberately NOT
-- pre-aggregated (e.g. no "team season averages" table) -- aggregation is
-- a feature-engineering concern that belongs to the ML/backend layer, not
-- a storage-layer decision. team_statistics.match_id references
-- matches(id) (the UUID PK), resolved at seed-load time via
-- matches.external_match_id (see seed_wc2026.sql).

CREATE TABLE IF NOT EXISTS team_statistics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id            UUID NOT NULL REFERENCES matches(id) ON DELETE RESTRICT,
    team_id             UUID NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
    possession_pct      SMALLINT,
    total_shots         SMALLINT,
    shots_on_target     SMALLINT,
    corners             SMALLINT,
    fouls               SMALLINT,
    offsides            SMALLINT,
    saves               SMALLINT,
    player_of_the_match VARCHAR(150),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_team_statistics_match_team UNIQUE (match_id, team_id),
    CONSTRAINT chk_possession_pct_range
        CHECK (possession_pct IS NULL OR (possession_pct >= 0 AND possession_pct <= 100)),
    CONSTRAINT chk_stats_non_negative
        CHECK (
            (total_shots IS NULL OR total_shots >= 0) AND
            (shots_on_target IS NULL OR shots_on_target >= 0) AND
            (corners IS NULL OR corners >= 0) AND
            (fouls IS NULL OR fouls >= 0) AND
            (offsides IS NULL OR offsides >= 0) AND
            (saves IS NULL OR saves >= 0)
        )
);

CREATE INDEX IF NOT EXISTS idx_team_statistics_match ON team_statistics (match_id);
CREATE INDEX IF NOT EXISTS idx_team_statistics_team ON team_statistics (team_id);

COMMENT ON TABLE team_statistics IS
    'Per-match, per-team box-score stats sourced from match_team_stats.csv '
    '(132 rows = 66 of the 76 completed 2026 matches x 2 teams; 10 '
    'completed matches have no stats rows -- documented gap, not '
    'backfilled/fabricated). Grain intentionally matches the source '
    '(match_id, team_id); pre-aggregated views/tables are a '
    'feature-engineering concern, not modeled here.';
COMMENT ON COLUMN team_statistics.possession_pct IS
    'Ball-possession percentage for this team in this match. Note: the '
    'two rows for a match do not always sum to exactly 100 (real recorded '
    'data variance) -- left as-is, not normalized to sum to 100.';

ALTER TABLE team_statistics ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "team_statistics_public_read" ON team_statistics;
CREATE POLICY "team_statistics_public_read" ON team_statistics
    FOR SELECT USING (true);

-- Note: team_statistics deliberately has no updated_at column / trigger --
-- these are immutable match facts (recorded once, post-match), not
-- evolving records, so there is nothing to keep "updated" over time.

-- ─── 6. Refresh dependent views to surface the new columns/tables ─────────────

CREATE OR REPLACE VIEW match_results AS
SELECT
    m.id,
    m.date,
    ht.name AS home_team,
    at.name AS away_team,
    m.home_score,
    m.away_score,
    m.tournament,
    m.stage,
    ts.stage_name,
    ts.is_knockout,
    m.neutral_venue,
    m.city,
    m.country,
    CASE
        WHEN m.home_score > m.away_score THEN 'home_win'
        WHEN m.home_score = m.away_score THEN 'draw'
        WHEN m.home_score < m.away_score THEN 'away_win'
        ELSE 'unknown'
    END AS result
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
LEFT JOIN teams at ON m.away_team_id = at.id  -- away_team_id may be NULL (unresolved bracket slot)
LEFT JOIN tournament_stages ts ON m.stage_id = ts.stage_id
WHERE m.status = 'completed';

COMMIT;
