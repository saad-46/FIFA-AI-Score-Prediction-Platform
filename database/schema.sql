-- ============================================================
-- FIFA AI Score Prediction Platform — Database Schema
-- PostgreSQL / Supabase
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search

-- ─── Teams ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    country         VARCHAR(100) NOT NULL,
    confederation   VARCHAR(50),
    fifa_ranking    INTEGER,
    logo_url        VARCHAR(500),
    founded_year    INTEGER,
    home_stadium    VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

-- GIN index for fast team name search
CREATE INDEX IF NOT EXISTS idx_teams_name_trgm ON teams USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_teams_confederation ON teams (confederation);

-- ─── Matches ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS matches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date            DATE NOT NULL,
    home_team_id    UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id    UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    home_score      SMALLINT,
    away_score      SMALLINT,
    tournament      VARCHAR(200) NOT NULL,
    stage           VARCHAR(100),
    neutral_venue   BOOLEAN NOT NULL DEFAULT FALSE,
    city            VARCHAR(100),
    country         VARCHAR(100),
    status          VARCHAR(20) NOT NULL DEFAULT 'completed'
                    CHECK (status IN ('scheduled', 'live', 'completed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_scores_non_negative
        CHECK (home_score >= 0 AND away_score >= 0),
    CONSTRAINT chk_different_teams
        CHECK (home_team_id != away_team_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches (date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches (home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches (away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches (tournament);
CREATE INDEX IF NOT EXISTS idx_matches_date_tournament ON matches (date, tournament);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches (status);

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

-- Teams and matches are public read
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "teams_public_read" ON teams FOR SELECT USING (true);
CREATE POLICY "matches_public_read" ON matches FOR SELECT USING (true);

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
JOIN teams at ON m.away_team_id = at.id
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
