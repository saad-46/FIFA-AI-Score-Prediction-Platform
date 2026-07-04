-- ============================================================
-- Seed script — imports FIFA match data from CSV
-- Run after schema.sql
--
-- SUPERSEDED (WC2026 upgrade, 2026-07-03): this script seeds the old broad
-- "all competitions 1872-2017" Kaggle-derived dataset (results.csv). For
-- the WC-2026-focused platform, database/seed_wc2026.sql is now the
-- source of truth for match history (WC 2002-2026 only: 330 real
-- historical matches + 89 real 2026 matches, with rankings/elo/team-stats
-- populated from the Data Engineering wave's processed CSVs). This file
-- is left in place for reference / in case the broader historical dataset
-- is wanted again in the future, but it is NOT run as part of the current
-- WC2026 seed flow. See DATABASE_SCHEMA.md at the repo root for details.
-- ============================================================

-- The historical FIFA dataset (results.csv from Kaggle) has columns:
-- date, home_team, away_team, home_score, away_score, tournament, city, country, neutral

-- Step 1: Create a staging table
CREATE TEMP TABLE matches_staging (
    date            DATE,
    home_team       VARCHAR(100),
    away_team       VARCHAR(100),
    home_score      SMALLINT,
    away_score      SMALLINT,
    tournament      VARCHAR(200),
    city            VARCHAR(100),
    country         VARCHAR(100),
    neutral         BOOLEAN
);

-- Step 2: Copy CSV data (run from psql)
-- \COPY matches_staging FROM 'results.csv' CSV HEADER;

-- Step 3: Insert unique teams
INSERT INTO teams (name, country)
SELECT DISTINCT home_team, home_team FROM matches_staging
ON CONFLICT (name) DO NOTHING;

INSERT INTO teams (name, country)
SELECT DISTINCT away_team, away_team FROM matches_staging
ON CONFLICT (name) DO NOTHING;

-- Step 4: Insert matches
INSERT INTO matches (date, home_team_id, away_team_id, home_score, away_score, tournament, city, country, neutral_venue, status)
SELECT
    s.date,
    ht.id,
    at.id,
    s.home_score,
    s.away_score,
    s.tournament,
    s.city,
    s.country,
    s.neutral,
    'completed'
FROM matches_staging s
JOIN teams ht ON ht.name = s.home_team
JOIN teams at ON at.name = s.away_team
ON CONFLICT DO NOTHING;

-- Verify
SELECT COUNT(*) AS total_matches FROM matches;
SELECT COUNT(*) AS total_teams FROM teams;
