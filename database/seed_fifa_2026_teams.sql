-- ============================================================
-- FIFA World Cup 2026 -- Official 48-Team Field Seed Data
-- Source: official FIFA World Cup 2026 wallchart/schedule PDF provided by the
-- user, extracted into backend/app/data/fifa_2026/groups.json on 2026-07-02.
-- Only name/country are populated from that source. confederation,
-- fifa_ranking, founded_year, home_stadium, and logo_url are intentionally
-- left NULL (not present in the source data) -- do not backfill with guesses.
-- Idempotent: safe to re-run (ON CONFLICT (name) DO NOTHING matches the
-- UNIQUE constraint on teams.name in database/schema.sql).
-- Run after schema.sql.
-- ============================================================

-- Group A
INSERT INTO teams (name, country) VALUES ('Mexico', 'Mexico') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('South Africa', 'South Africa') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Korea Republic', 'Korea Republic') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Czechia', 'Czechia') ON CONFLICT (name) DO NOTHING;

-- Group B
INSERT INTO teams (name, country) VALUES ('Canada', 'Canada') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Bosnia & Herzegovina', 'Bosnia & Herzegovina') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Qatar', 'Qatar') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Switzerland', 'Switzerland') ON CONFLICT (name) DO NOTHING;

-- Group C
INSERT INTO teams (name, country) VALUES ('Brazil', 'Brazil') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Morocco', 'Morocco') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Haiti', 'Haiti') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Scotland', 'Scotland') ON CONFLICT (name) DO NOTHING;

-- Group D
INSERT INTO teams (name, country) VALUES ('USA', 'USA') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Paraguay', 'Paraguay') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Australia', 'Australia') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Türkiye', 'Türkiye') ON CONFLICT (name) DO NOTHING;

-- Group E
INSERT INTO teams (name, country) VALUES ('Germany', 'Germany') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Curaçao', 'Curaçao') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Côte d''Ivoire', 'Côte d''Ivoire') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Ecuador', 'Ecuador') ON CONFLICT (name) DO NOTHING;

-- Group F
INSERT INTO teams (name, country) VALUES ('Netherlands', 'Netherlands') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Japan', 'Japan') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Sweden', 'Sweden') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Tunisia', 'Tunisia') ON CONFLICT (name) DO NOTHING;

-- Group G
INSERT INTO teams (name, country) VALUES ('Belgium', 'Belgium') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Egypt', 'Egypt') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('IR Iran', 'IR Iran') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('New Zealand', 'New Zealand') ON CONFLICT (name) DO NOTHING;

-- Group H
INSERT INTO teams (name, country) VALUES ('Spain', 'Spain') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Cabo Verde', 'Cabo Verde') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Saudi Arabia', 'Saudi Arabia') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Uruguay', 'Uruguay') ON CONFLICT (name) DO NOTHING;

-- Group I
INSERT INTO teams (name, country) VALUES ('France', 'France') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Senegal', 'Senegal') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Iraq', 'Iraq') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Norway', 'Norway') ON CONFLICT (name) DO NOTHING;

-- Group J
INSERT INTO teams (name, country) VALUES ('Argentina', 'Argentina') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Algeria', 'Algeria') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Austria', 'Austria') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Jordan', 'Jordan') ON CONFLICT (name) DO NOTHING;

-- Group K
INSERT INTO teams (name, country) VALUES ('Portugal', 'Portugal') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Congo DR', 'Congo DR') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Uzbekistan', 'Uzbekistan') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Colombia', 'Colombia') ON CONFLICT (name) DO NOTHING;

-- Group L
INSERT INTO teams (name, country) VALUES ('England', 'England') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Croatia', 'Croatia') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Ghana', 'Ghana') ON CONFLICT (name) DO NOTHING;
INSERT INTO teams (name, country) VALUES ('Panama', 'Panama') ON CONFLICT (name) DO NOTHING;

-- Verify: expect 48 FIFA 2026 teams inserted (existing rows from other seeds are untouched)
SELECT COUNT(*) AS fifa_2026_teams_check FROM teams WHERE name IN (
    'Mexico',
    'South Africa',
    'Korea Republic',
    'Czechia',
    'Canada',
    'Bosnia & Herzegovina',
    'Qatar',
    'Switzerland',
    'Brazil',
    'Morocco',
    'Haiti',
    'Scotland',
    'USA',
    'Paraguay',
    'Australia',
    'Türkiye',
    'Germany',
    'Curaçao',
    'Côte d''Ivoire',
    'Ecuador',
    'Netherlands',
    'Japan',
    'Sweden',
    'Tunisia',
    'Belgium',
    'Egypt',
    'IR Iran',
    'New Zealand',
    'Spain',
    'Cabo Verde',
    'Saudi Arabia',
    'Uruguay',
    'France',
    'Senegal',
    'Iraq',
    'Norway',
    'Argentina',
    'Algeria',
    'Austria',
    'Jordan',
    'Portugal',
    'Congo DR',
    'Uzbekistan',
    'Colombia',
    'England',
    'Croatia',
    'Ghana',
    'Panama'
);
