-- ============================================================
-- FIFA AI Score Prediction Platform — Database Schema
-- PostgreSQL / Supabase
--
-- This file is the TARGET STATE for fresh installs (includes the WC2026
-- upgrade). If you are evolving an existing database that was created
-- from an earlier version of this file, do NOT re-run this file blindly —
-- use database/migrations/002_wc2026_upgrade.sql instead, which applies
-- the same end-state additively/non-destructively on top of an existing
-- schema. See DATABASE_SCHEMA.md at the repo root for full documentation
-- of every table/column and the reasoning behind the WC2026 additions
-- (rankings-as-columns vs. history table, team_statistics grain,
-- tournament_stages lookup, etc.).
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search

-- ─── Tournament Stages (lookup) ────────────────────────────────────────────────
-- Canonical stage vocabulary, sourced from tournament_stages.csv
-- (DATA_QUALITY_REPORT.md file #6). Declared before `matches` since matches
-- references it.

CREATE TABLE IF NOT EXISTS tournament_stages (
    stage_id        SMALLINT PRIMARY KEY,
    stage_key       VARCHAR(30) NOT NULL UNIQUE,   -- e.g. 'group_stage' — matches source CSV vocabulary
    stage_name      VARCHAR(50) NOT NULL,           -- e.g. 'Group Stage' — display label
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

-- ─── Teams ───────────────────────────────────────────────────────────────────
-- Rankings (fifa_ranking, elo_rating) are stored as plain, updatable columns
-- rather than a separate history table: we only have a single pre-tournament
-- snapshot per team, so a "history" table would have exactly one row per
-- team today — pure speculative over-engineering. ranking_updated_at is
-- maintained automatically by trigger whenever either value changes, which
-- satisfies "rankings should be updated easily in future" (a plain UPDATE).
-- See DATABASE_SCHEMA.md for the full rationale and the future-extensibility
-- path (an additive team_ranking_history table, if a real time series is
-- ever needed).

CREATE TABLE IF NOT EXISTS teams (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(100) NOT NULL UNIQUE,
    country             VARCHAR(100) NOT NULL,
    confederation       VARCHAR(50),
    fifa_ranking        INTEGER,
    elo_rating          SMALLINT,
    fifa_code           VARCHAR(3),
    wc2026_group        CHAR(1),
    ranking_updated_at  TIMESTAMPTZ,
    logo_url            VARCHAR(500),
    founded_year        INTEGER,
    home_stadium        VARCHAR(200),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

-- GIN index for fast team name search
CREATE INDEX IF NOT EXISTS idx_teams_name_trgm ON teams USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_teams_confederation ON teams (confederation);
CREATE INDEX IF NOT EXISTS idx_teams_elo_rating ON teams (elo_rating);
CREATE INDEX IF NOT EXISTS idx_teams_wc2026_group ON teams (wc2026_group)
    WHERE wc2026_group IS NOT NULL;

-- fifa_code is only populated for the 48 current WC2026 teams (historical-
-- only teams from 2002-2022 don't have one recorded) — partial unique index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_fifa_code_unique
    ON teams (fifa_code) WHERE fifa_code IS NOT NULL;

COMMENT ON COLUMN teams.fifa_ranking IS
    'Current/most-recent known FIFA world ranking (lower is better). '
    'Update in place as new rankings are published; ranking_updated_at is '
    'bumped automatically by trigger.';
COMMENT ON COLUMN teams.elo_rating IS
    'Elo rating snapshot (higher is better). NULL for historical-only '
    'teams not in the WC2026 field.';
COMMENT ON COLUMN teams.fifa_code IS 'FIFA 3-letter team code (e.g. MEX, RSA). WC2026 field only.';
COMMENT ON COLUMN teams.wc2026_group IS 'WC2026 group-stage letter (A-L). WC2026 field only.';

-- ─── Matches ─────────────────────────────────────────────────────────────────
-- NOTE on FK delete behavior: teams -> matches uses ON DELETE CASCADE,
-- inherited from the original schema. A prior audit flagged this as a
-- data-loss footgun (deleting a team silently wipes its match history) —
-- left unchanged here to avoid a destructive constraint-behavior change
-- outside the scope of this upgrade, but every NEW foreign key introduced
-- by this upgrade (matches -> tournament_stages, team_statistics -> *)
-- uses ON DELETE RESTRICT instead, so we don't add more of the same risk.

CREATE TABLE IF NOT EXISTS matches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date                DATE NOT NULL,
    home_team_id        UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id        UUID REFERENCES teams(id) ON DELETE CASCADE,
    home_score          SMALLINT,
    away_score          SMALLINT,
    tournament          VARCHAR(200) NOT NULL,
    stage               VARCHAR(100),
    stage_id            SMALLINT REFERENCES tournament_stages(stage_id) ON DELETE RESTRICT,
    tournament_year     SMALLINT,
    neutral_venue       BOOLEAN NOT NULL DEFAULT FALSE,
    city                VARCHAR(100),
    country             VARCHAR(100),
    home_xg             NUMERIC(4,2),
    away_xg             NUMERIC(4,2),
    external_match_id   VARCHAR(50),
    data_source         VARCHAR(50),
    status              VARCHAR(20) NOT NULL DEFAULT 'completed'
                        CHECK (status IN ('scheduled', 'live', 'completed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_scores_non_negative
        CHECK ((home_score IS NULL OR home_score >= 0) AND (away_score IS NULL OR away_score >= 0)),
    CONSTRAINT chk_different_teams
        CHECK (home_team_id != away_team_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches (home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches (away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches (tournament);
CREATE INDEX IF NOT EXISTS idx_matches_date_tournament ON matches (date, tournament);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches (status);
CREATE INDEX IF NOT EXISTS idx_matches_stage_id ON matches (stage_id);
CREATE INDEX IF NOT EXISTS idx_matches_tournament_year ON matches (tournament_year);
CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_external_id_unique
    ON matches (external_match_id) WHERE external_match_id IS NOT NULL;

COMMENT ON COLUMN matches.away_team_id IS
    'Nullable: a small number of bracket-stage fixtures have a genuinely '
    'unresolved opponent slot (e.g. WC2026 Round-of-16 TBD advancement) '
    'represented as NULL rather than a fabricated placeholder team.';
COMMENT ON COLUMN matches.external_match_id IS
    'Source-system match identifier from matches_historical.csv (either a '
    'synthesized "hist_<sha1prefix>" id for 2002-2022 rows, or the small '
    'integer match_id used by the 2026 live dataset and by '
    'team_statistics via matches.id). Kept for traceability/joins back to '
    'source CSVs.';
COMMENT ON COLUMN matches.home_xg IS
    'Expected goals (home). NULL for 2002-2022 historical rows (xG not '
    'tracked for that era) and for not-yet-played fixtures — documented '
    'data gap, not a defect.';
COMMENT ON COLUMN matches.data_source IS
    'Provenance tag, e.g. wc_2002_2022_dataset or wc_2026_live.';

-- ─── Team Statistics ─────────────────────────────────────────────────────────
-- Per-match, per-team box-score stats (possession, shots, corners, fouls,
-- offsides, saves), sourced from match_team_stats.csv. Grain intentionally
-- matches the source: one row per (match_id, team_id). Not pre-aggregated —
-- aggregation (e.g. season/tournament averages) is a feature-engineering
-- concern for the ML/backend layer, not a storage-layer decision.

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
    'Per-match, per-team box-score stats sourced from match_team_stats.csv. '
    '132 rows = 66 of the 76 completed 2026 matches x 2 teams; 10 completed '
    'matches have no stats rows (documented source gap, not '
    'backfilled/fabricated). possession_pct for the two rows of a match '
    'does not always sum to exactly 100 (real recorded data variance) — '
    'left as-is.';

-- ─── Profiles (extends Supabase auth.users) ───────────────────────────────────

CREATE TABLE IF NOT EXISTS profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name       VARCHAR(200),
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

-- ─── Saved Predictions ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS saved_predictions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prediction_id           VARCHAR(100) NOT NULL,
    home_team               VARCHAR(100) NOT NULL,
    away_team               VARCHAR(100) NOT NULL,
    predicted_home_score    SMALLINT NOT NULL,
    predicted_away_score    SMALLINT NOT NULL,
    home_win_probability    FLOAT NOT NULL,
    draw_probability        FLOAT NOT NULL,
    away_win_probability    FLOAT NOT NULL,
    expected_home_goals     FLOAT NOT NULL,
    expected_away_goals     FLOAT NOT NULL,
    confidence_score        FLOAT NOT NULL,
    tournament              VARCHAR(200),
    neutral_venue           BOOLEAN DEFAULT FALSE,
    actual_home_score       SMALLINT,
    actual_away_score       SMALLINT,
    was_correct             BOOLEAN,
    model_version           VARCHAR(20) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_predictions_user ON saved_predictions (user_id);
CREATE INDEX IF NOT EXISTS idx_saved_predictions_created ON saved_predictions (created_at DESC);

-- ─── Row Level Security ───────────────────────────────────────────────────────

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_predictions ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only read/update their own profile
CREATE POLICY "profiles_select_own" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "profiles_insert_own" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Saved predictions: users can only access their own
CREATE POLICY "saved_predictions_select_own" ON saved_predictions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "saved_predictions_insert_own" ON saved_predictions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "saved_predictions_delete_own" ON saved_predictions
    FOR DELETE USING (auth.uid() = user_id);

-- Teams, matches, tournament_stages, and team_statistics are public read
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE tournament_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_statistics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "teams_public_read" ON teams FOR SELECT USING (true);
CREATE POLICY "matches_public_read" ON matches FOR SELECT USING (true);
CREATE POLICY "tournament_stages_public_read" ON tournament_stages FOR SELECT USING (true);
CREATE POLICY "team_statistics_public_read" ON team_statistics FOR SELECT USING (true);

-- ─── Triggers ─────────────────────────────────────────────────────────────────

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER teams_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-update teams.ranking_updated_at whenever fifa_ranking or elo_rating
-- changes (distinct from the generic updated_at trigger above, which fires
-- on ANY column change). This is what makes "rankings updated easily in
-- future" concrete: a plain `UPDATE teams SET fifa_ranking = ... WHERE ...`
-- automatically timestamps itself.
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

CREATE TRIGGER teams_ranking_updated_at
    BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_ranking_timestamp();

-- ─── Useful Views ─────────────────────────────────────────────────────────────

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

-- Team statistics view
CREATE OR REPLACE VIEW team_overall_stats AS
WITH all_matches AS (
    SELECT
        home_team_id AS team_id,
        home_score AS goals_scored,
        away_score AS goals_conceded,
        CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS win,
        CASE WHEN home_score = away_score THEN 1 ELSE 0 END AS draw,
        CASE WHEN home_score < away_score THEN 1 ELSE 0 END AS loss
    FROM matches WHERE status = 'completed' AND home_score IS NOT NULL

    UNION ALL

    SELECT
        away_team_id AS team_id,
        away_score AS goals_scored,
        home_score AS goals_conceded,
        CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS win,
        CASE WHEN away_score = home_score THEN 1 ELSE 0 END AS draw,
        CASE WHEN away_score < home_score THEN 1 ELSE 0 END AS loss
    FROM matches WHERE status = 'completed' AND away_score IS NOT NULL
)
SELECT
    t.id AS team_id,
    t.name AS team_name,
    COUNT(*) AS matches_played,
    SUM(am.win) AS wins,
    SUM(am.draw) AS draws,
    SUM(am.loss) AS losses,
    SUM(am.goals_scored) AS goals_scored,
    SUM(am.goals_conceded) AS goals_conceded,
    SUM(am.goals_scored) - SUM(am.goals_conceded) AS goal_difference,
    ROUND(SUM(am.win)::NUMERIC / COUNT(*), 4) AS win_rate
FROM all_matches am
JOIN teams t ON am.team_id = t.id
GROUP BY t.id, t.name;
