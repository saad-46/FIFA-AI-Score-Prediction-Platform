from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid


class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    country = Column(String(100), nullable=False)
    confederation = Column(String(50), nullable=True)
    fifa_ranking = Column(Integer, nullable=True)
    logo_url = Column(String(500), nullable=True)
    founded_year = Column(Integer, nullable=True)
    home_stadium = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False, index=True)
    home_team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    away_team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    tournament = Column(String(200), nullable=False, index=True)
    stage = Column(String(100), nullable=True)
    neutral_venue = Column(Boolean, default=False, nullable=False)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    status = Column(String(20), default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")

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


class SavedPrediction(Base):
    __tablename__ = "saved_predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # NOTE: user_id references Supabase's auth.users(id) (ON DELETE CASCADE — see
    # database/schema.sql). No SQLAlchemy ForeignKey/relationship is declared here
    # because auth.users lives in Supabase's own "auth" schema, is managed by
    # Supabase Auth (not by this app's models/migrations), and is not mapped as an
    # ORM entity in this codebase. The FK constraint still exists at the DB level.
    user_id = Column(String, nullable=False, index=True)
    prediction_id = Column(String, nullable=False)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    predicted_home_score = Column(Integer, nullable=False)
    predicted_away_score = Column(Integer, nullable=False)
    home_win_probability = Column(Float, nullable=False)
    draw_probability = Column(Float, nullable=False)
    away_win_probability = Column(Float, nullable=False)
    expected_home_goals = Column(Float, nullable=False)
    expected_away_goals = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    tournament = Column(String(200), nullable=True)
    neutral_venue = Column(Boolean, default=False)
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    was_correct = Column(Boolean, nullable=True)
    model_version = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
