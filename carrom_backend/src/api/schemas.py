"""
Pydantic schemas for the carrom backend API.

Defines request/response models for games, players, turns,
settings, and analytics endpoints.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ---- Player Schemas ----

class PlayerBase(BaseModel):
    """Base schema for player data."""
    name: str = Field(..., description="Player display name", max_length=100)
    player_type: str = Field(default="human", description="Player type: 'human' or 'ai'")
    ai_difficulty: Optional[str] = Field(default=None, description="AI difficulty: 'easy', 'medium', 'hard'")


# PUBLIC_INTERFACE
class PlayerCreate(PlayerBase):
    """Schema for creating a new player."""
    pass


# PUBLIC_INTERFACE
class PlayerResponse(PlayerBase):
    """Schema for player API response."""
    id: uuid.UUID = Field(..., description="Unique player identifier")
    created_at: Optional[datetime] = Field(None, description="Player creation timestamp")

    model_config = {"from_attributes": True}


# ---- Game Settings Schemas ----

class GameSettingsBase(BaseModel):
    """Base schema for game settings."""
    sound_enabled: bool = Field(default=True, description="Whether sound is enabled")
    physics_speed: float = Field(default=1.0, description="Physics simulation speed multiplier")
    board_friction: float = Field(default=0.98, description="Board friction coefficient")
    striker_max_force: float = Field(default=100.0, description="Maximum striker force")
    timer_per_turn: int = Field(default=30, description="Seconds allowed per turn")
    scoring_mode: str = Field(default="standard", description="Scoring mode: 'standard', 'freestyle'")


# PUBLIC_INTERFACE
class GameSettingsUpdate(BaseModel):
    """Schema for updating game settings (all fields optional)."""
    sound_enabled: Optional[bool] = Field(None, description="Whether sound is enabled")
    physics_speed: Optional[float] = Field(None, description="Physics simulation speed multiplier")
    board_friction: Optional[float] = Field(None, description="Board friction coefficient")
    striker_max_force: Optional[float] = Field(None, description="Maximum striker force")
    timer_per_turn: Optional[int] = Field(None, description="Seconds allowed per turn")
    scoring_mode: Optional[str] = Field(None, description="Scoring mode")


# PUBLIC_INTERFACE
class GameSettingsResponse(GameSettingsBase):
    """Schema for game settings API response."""
    id: uuid.UUID = Field(..., description="Settings record identifier")
    game_id: uuid.UUID = Field(..., description="Associated game identifier")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Game Player Schemas ----

# PUBLIC_INTERFACE
class GamePlayerResponse(BaseModel):
    """Schema for a player within a game context."""
    id: uuid.UUID = Field(..., description="Game-player link identifier")
    game_id: uuid.UUID = Field(..., description="Game identifier")
    player_id: uuid.UUID = Field(..., description="Player identifier")
    score: int = Field(default=0, description="Player's current score")
    turn_order: int = Field(default=0, description="Player's turn order")
    player: Optional[PlayerResponse] = Field(None, description="Player details")

    model_config = {"from_attributes": True}


# ---- Turn Schemas ----

# PUBLIC_INTERFACE
class TurnCreate(BaseModel):
    """Schema for submitting a move/turn."""
    player_id: uuid.UUID = Field(..., description="ID of the player making the move")
    striker_position_x: float = Field(..., description="Striker X position on the board")
    striker_position_y: float = Field(..., description="Striker Y position on the board")
    striker_angle: float = Field(..., description="Striker angle in degrees")
    striker_force: float = Field(..., description="Striker force (0-100)")
    coins_pocketed: List[str] = Field(default=[], description="List of coin types pocketed: 'white', 'black', 'queen'")


# PUBLIC_INTERFACE
class TurnResponse(BaseModel):
    """Schema for turn API response."""
    id: uuid.UUID = Field(..., description="Turn record identifier")
    game_id: uuid.UUID = Field(..., description="Game identifier")
    player_id: uuid.UUID = Field(..., description="Player identifier")
    turn_number: int = Field(..., description="Sequential turn number")
    striker_position_x: Optional[float] = None
    striker_position_y: Optional[float] = None
    striker_angle: Optional[float] = None
    striker_force: Optional[float] = None
    coins_pocketed: List[str] = Field(default=[], description="Coins pocketed this turn")
    foul: bool = Field(default=False, description="Whether a foul was committed")
    foul_reason: Optional[str] = Field(None, description="Reason for foul if applicable")
    points_earned: int = Field(default=0, description="Points earned this turn")
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Game Schemas ----

# PUBLIC_INTERFACE
class GameCreate(BaseModel):
    """Schema for creating a new game."""
    mode: str = Field(default="classic", description="Game mode: 'classic', 'freestyle'")
    player_ids: List[uuid.UUID] = Field(
        ..., description="List of player IDs (2 players)", min_length=2, max_length=2
    )
    settings: Optional[GameSettingsBase] = Field(None, description="Optional game settings override")


# PUBLIC_INTERFACE
class GameResponse(BaseModel):
    """Schema for game API response."""
    id: uuid.UUID = Field(..., description="Unique game identifier")
    mode: str = Field(..., description="Game mode")
    status: str = Field(..., description="Game status: 'waiting', 'in_progress', 'completed', 'abandoned'")
    current_turn_player_id: Optional[uuid.UUID] = Field(None, description="Current turn player ID")
    winner_id: Optional[uuid.UUID] = Field(None, description="Winner player ID if game completed")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    game_players: List[GamePlayerResponse] = Field(default=[], description="Players in this game")
    settings: Optional[GameSettingsResponse] = Field(None, description="Game settings")

    model_config = {"from_attributes": True}


# PUBLIC_INTERFACE
class GameStateResponse(BaseModel):
    """Schema for full game state (used in WebSocket sync)."""
    game: GameResponse = Field(..., description="Game data")
    turns: List[TurnResponse] = Field(default=[], description="List of turns played")
    message: Optional[str] = Field(None, description="Status message")


# ---- Score Schemas ----

# PUBLIC_INTERFACE
class ScoreResponse(BaseModel):
    """Schema for score information."""
    game_id: uuid.UUID = Field(..., description="Game identifier")
    scores: List[Dict[str, Any]] = Field(
        default=[], description="List of player scores with player info"
    )


# ---- Analytics Schemas ----

# PUBLIC_INTERFACE
class AnalyticsEventCreate(BaseModel):
    """Schema for logging an analytics event."""
    game_id: Optional[uuid.UUID] = Field(None, description="Related game ID")
    player_id: Optional[uuid.UUID] = Field(None, description="Related player ID")
    event_type: str = Field(..., description="Event type identifier")
    event_data: Dict[str, Any] = Field(default={}, description="Event payload data")
    session_id: Optional[str] = Field(None, description="Client session identifier")
    device_info: Dict[str, Any] = Field(default={}, description="Device information")


# PUBLIC_INTERFACE
class AnalyticsEventResponse(BaseModel):
    """Schema for analytics event API response."""
    id: uuid.UUID = Field(..., description="Event record identifier")
    game_id: Optional[uuid.UUID] = None
    player_id: Optional[uuid.UUID] = None
    event_type: str = Field(..., description="Event type")
    event_data: Dict[str, Any] = Field(default={})
    session_id: Optional[str] = None
    device_info: Dict[str, Any] = Field(default={})
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- AI Move Schemas ----

# PUBLIC_INTERFACE
class AIMoveRequest(BaseModel):
    """Schema for requesting an AI move."""
    game_id: uuid.UUID = Field(..., description="Game identifier")
    difficulty: str = Field(default="easy", description="AI difficulty: 'easy', 'medium', 'hard'")


# PUBLIC_INTERFACE
class AIMoveResponse(BaseModel):
    """Schema for AI move result."""
    turn: TurnResponse = Field(..., description="The AI's turn data")
    message: str = Field(default="AI move completed", description="Status message")
