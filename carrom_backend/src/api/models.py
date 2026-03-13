"""
SQLAlchemy ORM models for the carrom game database.

Maps to the existing PostgreSQL tables:
- players, games, game_players, game_settings, turns, analytics_events
"""
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey,
    Text, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.api.database import Base


class Player(Base):
    """Represents a player (human or AI) in the carrom system."""
    __tablename__ = "players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    player_type = Column(String(20), nullable=False, default="human")
    ai_difficulty = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game_players = relationship("GamePlayer", back_populates="player")
    turns = relationship("Turn", back_populates="player")


class Game(Base):
    """Represents a carrom game session."""
    __tablename__ = "games"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode = Column(String(50), nullable=False, default="classic")
    status = Column(String(20), nullable=False, default="waiting")
    current_turn_player_id = Column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    game_players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")
    settings = relationship("GameSettings", back_populates="game", uselist=False, cascade="all, delete-orphan")
    turns = relationship("Turn", back_populates="game", cascade="all, delete-orphan", order_by="Turn.turn_number")
    current_turn_player = relationship("Player", foreign_keys=[current_turn_player_id])
    winner = relationship("Player", foreign_keys=[winner_id])

    __table_args__ = (
        Index("idx_games_status", "status"),
    )


class GamePlayer(Base):
    """Links players to games with score and turn order."""
    __tablename__ = "game_players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=False)
    score = Column(Integer, nullable=False, default=0)
    turn_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game = relationship("Game", back_populates="game_players")
    player = relationship("Player", back_populates="game_players")

    __table_args__ = (
        UniqueConstraint("game_id", "player_id"),
    )


class GameSettings(Base):
    """Configurable settings for a specific game."""
    __tablename__ = "game_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False, unique=True)
    sound_enabled = Column(Boolean, default=True)
    physics_speed = Column(Float, default=1.0)
    board_friction = Column(Float, default=0.98)
    striker_max_force = Column(Float, default=100.0)
    timer_per_turn = Column(Integer, default=30)
    scoring_mode = Column(String(50), default="standard")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    game = relationship("Game", back_populates="settings")


class Turn(Base):
    """Records a single turn/move in a game."""
    __tablename__ = "turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=False)
    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    striker_position_x = Column(Float, nullable=True)
    striker_position_y = Column(Float, nullable=True)
    striker_angle = Column(Float, nullable=True)
    striker_force = Column(Float, nullable=True)
    coins_pocketed = Column(ARRAY(Text), default=[])
    foul = Column(Boolean, default=False)
    foul_reason = Column(String(200), nullable=True)
    points_earned = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game = relationship("Game", back_populates="turns")
    player = relationship("Player", back_populates="turns")

    __table_args__ = (
        Index("idx_turns_game_id", "game_id"),
    )


class AnalyticsEvent(Base):
    """Tracks analytics and crash events for monitoring."""
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(UUID(as_uuid=True), ForeignKey("games.id"), nullable=True)
    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    event_data = Column(JSONB, default={})
    session_id = Column(String(100), nullable=True)
    device_info = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_analytics_events_created_at", "created_at"),
        Index("idx_analytics_events_game_id", "game_id"),
        Index("idx_analytics_events_type", "event_type"),
    )
