from sqlalchemy import Column, String, Integer, SmallInteger, Numeric, Float, Boolean, Date, DateTime, ForeignKey, Index, CheckConstraint, Uuid

# Postgres stores every id/foreign-key column below as native `uuid` (see
# DATABASE_SCHEMA.md / `list_tables` against the live Supabase project) -- a
# plain `Column(String, ...)` here would compare/join as `character varying`
# against Postgres's `uuid` operator class and fail with
# `operator does not exist: uuid = character varying` at query time (this was
# undetected all session because the live DB was unreachable from the dev
# sandbox until raw network access was restored). `Uuid(as_uuid=False)` maps
# correctly to the native `uuid` column type while still returning plain
# Python `str` values everywhere else in the codebase already expects them
# (schemas, services, `default=lambda: str(uuid.uuid4())`), so no other file
# needs to change.
_UUID = Uuid(as_uuid=False)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid


class TournamentStage(Base):
    """Lookup table for WC stage vocabulary. See database/schema.sql
    (tournament_stages) — 7 rows, seeded via schema.sql/migration, not
    inserted by the ORM. sourced from tournament_stages.csv
    (DATA_QUALITY_REPORT.md file #6)."""

    __tablename__ = "tournament_stages"

    stage_id = Column(SmallInteger, primary_key=True)
    stage_key = Column(String(30), nullable=False, unique=True)
    stage_name = Column(String(50), nullable=False)
    is_knockout = Column(Boolean, nullable=False)
    sort_order = Column(SmallInteger, nullable=False)


class Team(Base):
    __tablename__ = "teams"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    country = Column(String(100), nullable=False)
    confederation = Column(String(50), nullable=True)
    # fifa_ranking / elo_rating are plain, directly-updatable current-value
    # columns rather than a history table — see database/DATABASE_SCHEMA.md
    # ("Rankings storage design") for the rationale: we only have a single
    # pre-tournament snapshot per team, not a real time series, so a history
    # table would be speculative over-engineering. ranking_updated_at is
    # maintained automatically by the teams_ranking_updated_at DB trigger
    # whenever fifa_ranking or elo_rating changes.
    fifa_ranking = Column(Integer, nullable=True)
    elo_rating = Column(SmallInteger, nullable=True)
    fifa_code = Column(String(3), nullable=True)
    wc2026_group = Column(String(1), nullable=True)
    ranking_updated_at = Column(DateTime(timezone=True), nullable=True)
    logo_url = Column(String(500), nullable=True)
    founded_year = Column(Integer, nullable=True)
    home_stadium = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")
    statistics = relationship("TeamStatistics", back_populates="team")


class Match(Base):
    __tablename__ = "matches"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False, index=True)
    home_team_id = Column(_UUID, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nullable: a small number of bracket-stage fixtures have a genuinely
    # unresolved opponent slot (e.g. WC2026 Round-of-16 TBD advancement,
    # matches_historical.csv match_id=89) represented as NULL rather than a
    # fabricated placeholder team.
    away_team_id = Column(_UUID, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    tournament = Column(String(200), nullable=False, index=True)
    stage = Column(String(100), nullable=True)
    # New, normalized alongside `stage` for backward compatibility — existing
    # code (app/services/match_service.py) reads Match.stage as a string
    # directly, so that column is kept as-is. stage_id is the normalized FK
    # for new/future consumers; backfilled best-effort from `stage` where the
    # text matches known vocabulary (see migrations/002_wc2026_upgrade.sql).
    stage_id = Column(SmallInteger, ForeignKey("tournament_stages.stage_id", ondelete="RESTRICT"), nullable=True, index=True)
    tournament_year = Column(SmallInteger, nullable=True)
    neutral_venue = Column(Boolean, default=False, nullable=False)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    home_xg = Column(Numeric(4, 2), nullable=True)
    away_xg = Column(Numeric(4, 2), nullable=True)
    external_match_id = Column(String(50), nullable=True, index=True)
    data_source = Column(String(50), nullable=True)
    status = Column(String(20), default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    stage_ref = relationship("TournamentStage")
    statistics = relationship("TeamStatistics", back_populates="match")

    # Composite index + CHECK constraints — names and shape mirror database/schema.sql
    # exactly (schema.sql is the DDL actually applied to Supabase; these declarations
    # exist so the ORM mapping stays truthful and so Base.metadata would reproduce the
    # same schema if ever used against a fresh DB). No home_team_id+away_team_id
    # composite index: no query in app/services/*.py filters matches by both columns
    # together (head-to-head lookups resolve team ids first, then filter the in-memory
    # match dataframe by team name), so idx_matches_home_team / idx_matches_away_team
    # (single-column, declared via index=True above) already cover actual access
    # patterns without the overhead of an extra composite index.
    __table_args__ = (
        Index("idx_matches_date_tournament", "date", "tournament"),
        CheckConstraint("status IN ('scheduled', 'live', 'completed')", name="chk_status_valid"),
        CheckConstraint(
            "(home_score IS NULL OR home_score >= 0) AND (away_score IS NULL OR away_score >= 0)",
            name="chk_scores_non_negative",
        ),
        CheckConstraint("home_team_id != away_team_id", name="chk_different_teams"),
    )


class TeamStatistics(Base):
    """Per-match, per-team box-score stats. See database/schema.sql
    (team_statistics) — grain matches match_team_stats.csv exactly: one row
    per (match_id, team_id). Deliberately not pre-aggregated; aggregation is
    a feature-engineering concern owned by the ML layer, not this model."""

    __tablename__ = "team_statistics"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    match_id = Column(_UUID, ForeignKey("matches.id", ondelete="RESTRICT"), nullable=False, index=True)
    team_id = Column(_UUID, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)
    possession_pct = Column(SmallInteger, nullable=True)
    total_shots = Column(SmallInteger, nullable=True)
    shots_on_target = Column(SmallInteger, nullable=True)
    corners = Column(SmallInteger, nullable=True)
    fouls = Column(SmallInteger, nullable=True)
    offsides = Column(SmallInteger, nullable=True)
    saves = Column(SmallInteger, nullable=True)
    player_of_the_match = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match", foreign_keys=[match_id], back_populates="statistics")
    team = relationship("Team", foreign_keys=[team_id], back_populates="statistics")

    __table_args__ = (
        Index("uq_team_statistics_match_team", "match_id", "team_id", unique=True),
        CheckConstraint(
            "possession_pct IS NULL OR (possession_pct >= 0 AND possession_pct <= 100)",
            name="chk_possession_pct_range",
        ),
        CheckConstraint(
            "(total_shots IS NULL OR total_shots >= 0) AND "
            "(shots_on_target IS NULL OR shots_on_target >= 0) AND "
            "(corners IS NULL OR corners >= 0) AND "
            "(fouls IS NULL OR fouls >= 0) AND "
            "(offsides IS NULL OR offsides >= 0) AND "
            "(saves IS NULL OR saves >= 0)",
            name="chk_stats_non_negative",
        ),
    )


class SavedPrediction(Base):
    __tablename__ = "saved_predictions"

    id = Column(_UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    # NOTE: user_id references Supabase's auth.users(id) (ON DELETE CASCADE — see
    # database/schema.sql). No SQLAlchemy ForeignKey/relationship is declared here
    # because auth.users lives in Supabase's own "auth" schema, is managed by
    # Supabase Auth (not by this app's models/migrations), and is not mapped as an
    # ORM entity in this codebase. The FK constraint still exists at the DB level.
    user_id = Column(_UUID, nullable=False, index=True)
    prediction_id = Column(String, nullable=False)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    predicted_home_score = Column(Integer, nullable=False)
    predicted_away_score = Column(Integer, nullable=False)
    home_win_probability = Column(Float, nullable=False)
    draw_probability = Column(Float, nullable=False)
    away_win_probability = Column(Float, nullable=False)
    # Python attribute name kept as `expected_home_goals`/`expected_away_goals`
    # (matches every consumer in schemas/services/endpoints and database/schema.sql),
    # but the live Supabase table's actual columns are named
    # `home_expected_goals`/`away_expected_goals` (verified via
    # information_schema.columns against the live Supabase project) --
    # without this explicit name override every SavedPrediction query 500s
    # with `UndefinedColumnError`. Found by the Code Review pass; this table
    # predates this session's schema.sql fix and was never migrated to match it.
    expected_home_goals = Column("home_expected_goals", Float, nullable=False)
    expected_away_goals = Column("away_expected_goals", Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    tournament = Column(String(200), nullable=True)
    neutral_venue = Column(Boolean, default=False)
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    was_correct = Column(Boolean, nullable=True)
    model_version = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
