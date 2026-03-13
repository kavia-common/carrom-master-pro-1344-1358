"""
API routes for the carrom backend.

Provides REST endpoints for:
- Players: CRUD operations
- Games: Create, read, update, delete games
- Moves/Turns: Submit and retrieve game turns
- Scores: Get game scores
- Settings: Get/update game settings
- Analytics: Log and retrieve analytics events
- AI: Request AI moves
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from src.api.database import get_db
from src.api.models import (
    Player, Game, GamePlayer, GameSettings, Turn, AnalyticsEvent
)
from src.api.schemas import (
    PlayerCreate, PlayerResponse,
    GameCreate, GameResponse, GameStateResponse,
    GameSettingsUpdate, GameSettingsResponse,
    GamePlayerResponse,
    TurnCreate, TurnResponse,
    ScoreResponse,
    AnalyticsEventCreate, AnalyticsEventResponse,
    AIMoveRequest, AIMoveResponse,
)
from src.api.game_logic import (
    calculate_turn_score, detect_foul, apply_foul_penalty,
    update_score, check_win_condition, get_next_turn_player,
    get_turn_number,
)
from src.api.ai_engine import generate_ai_move
from src.api.analytics import log_event, log_game_event, log_error_event

logger = logging.getLogger(__name__)

# ---- Router Definitions ----

player_router = APIRouter(prefix="/players", tags=["Players"])
game_router = APIRouter(prefix="/games", tags=["Games"])
turn_router = APIRouter(prefix="/games/{game_id}/turns", tags=["Turns"])
score_router = APIRouter(prefix="/games/{game_id}/scores", tags=["Scores"])
settings_router = APIRouter(prefix="/games/{game_id}/settings", tags=["Settings"])
analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])
ai_router = APIRouter(prefix="/ai", tags=["AI"])


# ====================
# Player Endpoints
# ====================

@player_router.get(
    "/",
    response_model=List[PlayerResponse],
    summary="List all players",
    description="Retrieve a list of all registered players (human and AI).",
)
# PUBLIC_INTERFACE
def list_players(
    player_type: Optional[str] = Query(None, description="Filter by player type: 'human' or 'ai'"),
    db: Session = Depends(get_db),
):
    """List all players, optionally filtered by type."""
    query = db.query(Player)
    if player_type:
        query = query.filter(Player.player_type == player_type)
    return query.order_by(Player.created_at.desc()).all()


@player_router.get(
    "/{player_id}",
    response_model=PlayerResponse,
    summary="Get player by ID",
    description="Retrieve a specific player by their unique identifier.",
)
# PUBLIC_INTERFACE
def get_player(player_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single player by ID."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@player_router.post(
    "/",
    response_model=PlayerResponse,
    status_code=201,
    summary="Create a new player",
    description="Register a new human or AI player.",
)
# PUBLIC_INTERFACE
def create_player(player_data: PlayerCreate, db: Session = Depends(get_db)):
    """Create a new player."""
    player = Player(
        name=player_data.name,
        player_type=player_data.player_type,
        ai_difficulty=player_data.ai_difficulty,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    logger.info("Created player: %s (type=%s)", player.name, player.player_type)
    return player


@player_router.delete(
    "/{player_id}",
    status_code=204,
    summary="Delete a player",
    description="Remove a player by their unique identifier.",
)
# PUBLIC_INTERFACE
def delete_player(player_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a player by ID."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    db.delete(player)
    db.commit()
    return None


# ====================
# Game Endpoints
# ====================

@game_router.get(
    "/",
    response_model=List[GameResponse],
    summary="List all games",
    description="Retrieve a list of all games, optionally filtered by status.",
)
# PUBLIC_INTERFACE
def list_games(
    status: Optional[str] = Query(None, description="Filter by game status"),
    db: Session = Depends(get_db),
):
    """List all games with optional status filter."""
    query = db.query(Game).options(
        joinedload(Game.game_players).joinedload(GamePlayer.player),
        joinedload(Game.settings),
    )
    if status:
        query = query.filter(Game.status == status)
    return query.order_by(Game.created_at.desc()).all()


@game_router.get(
    "/{game_id}",
    response_model=GameResponse,
    summary="Get game by ID",
    description="Retrieve a specific game with its players and settings.",
)
# PUBLIC_INTERFACE
def get_game(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single game by ID with full details."""
    game = (
        db.query(Game)
        .options(
            joinedload(Game.game_players).joinedload(GamePlayer.player),
            joinedload(Game.settings),
        )
        .filter(Game.id == game_id)
        .first()
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@game_router.post(
    "/",
    response_model=GameResponse,
    status_code=201,
    summary="Create a new game",
    description="Create a new carrom game with specified players and optional settings.",
)
# PUBLIC_INTERFACE
def create_game(game_data: GameCreate, db: Session = Depends(get_db)):
    """Create a new game, associate players, and initialize settings."""
    try:
        # Validate players exist
        players = []
        for pid in game_data.player_ids:
            player = db.query(Player).filter(Player.id == pid).first()
            if not player:
                raise HTTPException(
                    status_code=404,
                    detail=f"Player {pid} not found"
                )
            players.append(player)

        # Create game
        game = Game(
            mode=game_data.mode,
            status="in_progress",
            current_turn_player_id=game_data.player_ids[0],
        )
        db.add(game)
        db.flush()

        # Create game_players
        for idx, player in enumerate(players):
            gp = GamePlayer(
                game_id=game.id,
                player_id=player.id,
                score=0,
                turn_order=idx,
            )
            db.add(gp)

        # Create game settings
        settings_data = game_data.settings
        settings = GameSettings(
            game_id=game.id,
            sound_enabled=settings_data.sound_enabled if settings_data else True,
            physics_speed=settings_data.physics_speed if settings_data else 1.0,
            board_friction=settings_data.board_friction if settings_data else 0.98,
            striker_max_force=settings_data.striker_max_force if settings_data else 100.0,
            timer_per_turn=settings_data.timer_per_turn if settings_data else 30,
            scoring_mode=settings_data.scoring_mode if settings_data else "standard",
        )
        db.add(settings)

        # Log analytics event
        log_game_event(db, game.id, "game_created", {
            "mode": game.mode,
            "player_count": len(players),
        })

        db.commit()

        # Reload with relationships
        game = (
            db.query(Game)
            .options(
                joinedload(Game.game_players).joinedload(GamePlayer.player),
                joinedload(Game.settings),
            )
            .filter(Game.id == game.id)
            .first()
        )

        logger.info("Created game %s with %d players", game.id, len(players))
        return game

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to create game: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create game: {str(e)}")


@game_router.patch(
    "/{game_id}/status",
    response_model=GameResponse,
    summary="Update game status",
    description="Update the status of a game (e.g., abandon or complete).",
)
# PUBLIC_INTERFACE
def update_game_status(
    game_id: uuid.UUID,
    status: str = Query(..., description="New status: 'in_progress', 'completed', 'abandoned'"),
    db: Session = Depends(get_db),
):
    """Update game status."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    valid_statuses = {"waiting", "in_progress", "completed", "abandoned"}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    game.status = status
    if status in ("completed", "abandoned"):
        game.ended_at = datetime.now(timezone.utc)

    log_game_event(db, game.id, f"game_{status}", {"previous_status": game.status})
    db.commit()

    game = (
        db.query(Game)
        .options(
            joinedload(Game.game_players).joinedload(GamePlayer.player),
            joinedload(Game.settings),
        )
        .filter(Game.id == game_id)
        .first()
    )
    return game


@game_router.delete(
    "/{game_id}",
    status_code=204,
    summary="Delete a game",
    description="Delete a game and all its associated data.",
)
# PUBLIC_INTERFACE
def delete_game(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a game by ID."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    db.delete(game)
    db.commit()
    return None


# ====================
# Turn/Move Endpoints
# ====================

@turn_router.get(
    "/",
    response_model=List[TurnResponse],
    summary="List turns for a game",
    description="Retrieve all turns/moves for a specific game in order.",
)
# PUBLIC_INTERFACE
def list_turns(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """List all turns for a game."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    turns = (
        db.query(Turn)
        .filter(Turn.game_id == game_id)
        .order_by(Turn.turn_number)
        .all()
    )
    return turns


@turn_router.post(
    "/",
    response_model=TurnResponse,
    status_code=201,
    summary="Submit a move",
    description="Submit a new turn/move for a game. Processes scoring, fouls, and win conditions.",
)
# PUBLIC_INTERFACE
def create_turn(
    game_id: uuid.UUID,
    turn_data: TurnCreate,
    db: Session = Depends(get_db),
):
    """
    Submit a move/turn for a game.

    Processes the move through game logic:
    1. Validates game state and player turn
    2. Detects fouls
    3. Calculates and applies score
    4. Checks win conditions
    5. Advances turn to next player
    """
    try:
        # Validate game exists and is in progress
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.status != "in_progress":
            raise HTTPException(status_code=400, detail="Game is not in progress")

        # Validate it's this player's turn
        if game.current_turn_player_id and str(game.current_turn_player_id) != str(turn_data.player_id):
            raise HTTPException(
                status_code=400,
                detail="It is not this player's turn"
            )

        # Get game player record
        game_player = (
            db.query(GamePlayer)
            .filter(
                GamePlayer.game_id == game_id,
                GamePlayer.player_id == turn_data.player_id,
            )
            .first()
        )
        if not game_player:
            raise HTTPException(status_code=404, detail="Player not found in this game")

        # Get game settings for foul detection
        game_settings = db.query(GameSettings).filter(GameSettings.game_id == game_id).first()
        max_force = game_settings.striker_max_force if game_settings else 100.0
        scoring_mode = game_settings.scoring_mode if game_settings else "standard"

        # Detect fouls
        is_foul, foul_reason = detect_foul(
            striker_force=turn_data.striker_force,
            striker_max_force=max_force,
            coins_pocketed=turn_data.coins_pocketed,
        )

        # Calculate score
        points_earned = 0
        if is_foul:
            apply_foul_penalty(db, game_player)
        else:
            points_earned = calculate_turn_score(turn_data.coins_pocketed)
            if points_earned > 0:
                update_score(db, game_player, points_earned)

        # Create turn record
        turn_number = get_turn_number(db, game_id)
        turn = Turn(
            game_id=game_id,
            player_id=turn_data.player_id,
            turn_number=turn_number,
            striker_position_x=turn_data.striker_position_x,
            striker_position_y=turn_data.striker_position_y,
            striker_angle=turn_data.striker_angle,
            striker_force=turn_data.striker_force,
            coins_pocketed=turn_data.coins_pocketed,
            foul=is_foul,
            foul_reason=foul_reason,
            points_earned=points_earned,
        )
        db.add(turn)
        db.flush()

        # Check win condition
        winner = check_win_condition(db, game, scoring_mode)
        if winner:
            game.status = "completed"
            game.winner_id = winner.player_id
            game.ended_at = datetime.now(timezone.utc)
            log_game_event(db, game.id, "game_completed", {
                "winner_id": str(winner.player_id),
                "final_score": winner.score,
            })
        else:
            # Determine next turn player
            earned_extra_turn = (points_earned > 0 and not is_foul)
            next_player = get_next_turn_player(
                db, game, turn_data.player_id, earned_extra_turn
            )
            if next_player:
                game.current_turn_player_id = next_player.player_id

        # Log analytics
        log_game_event(db, game.id, "turn_played", {
            "player_id": str(turn_data.player_id),
            "turn_number": turn_number,
            "points_earned": points_earned,
            "foul": is_foul,
            "coins_pocketed": turn_data.coins_pocketed,
        })

        db.commit()
        db.refresh(turn)

        logger.info(
            "Turn %d in game %s by player %s: points=%d, foul=%s",
            turn_number, game_id, turn_data.player_id, points_earned, is_foul
        )
        return turn

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to create turn: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process move: {str(e)}")


# ====================
# Score Endpoints
# ====================

@score_router.get(
    "/",
    response_model=ScoreResponse,
    summary="Get game scores",
    description="Retrieve current scores for all players in a game.",
)
# PUBLIC_INTERFACE
def get_scores(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get scores for all players in a game."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    game_players = (
        db.query(GamePlayer)
        .options(joinedload(GamePlayer.player))
        .filter(GamePlayer.game_id == game_id)
        .order_by(GamePlayer.turn_order)
        .all()
    )

    scores = []
    for gp in game_players:
        scores.append({
            "player_id": str(gp.player_id),
            "player_name": gp.player.name if gp.player else "Unknown",
            "score": gp.score,
            "turn_order": gp.turn_order,
        })

    return ScoreResponse(game_id=game_id, scores=scores)


# ====================
# Settings Endpoints
# ====================

@settings_router.get(
    "/",
    response_model=GameSettingsResponse,
    summary="Get game settings",
    description="Retrieve the settings for a specific game.",
)
# PUBLIC_INTERFACE
def get_settings(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get settings for a game."""
    settings = db.query(GameSettings).filter(GameSettings.game_id == game_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found for this game")
    return settings


@settings_router.patch(
    "/",
    response_model=GameSettingsResponse,
    summary="Update game settings",
    description="Update one or more settings for a specific game.",
)
# PUBLIC_INTERFACE
def update_settings(
    game_id: uuid.UUID,
    settings_data: GameSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update game settings (partial update)."""
    settings = db.query(GameSettings).filter(GameSettings.game_id == game_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found for this game")

    update_dict = settings_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    logger.info("Updated settings for game %s: %s", game_id, update_dict)
    return settings


# ====================
# Analytics Endpoints
# ====================

@analytics_router.post(
    "/events",
    response_model=AnalyticsEventResponse,
    status_code=201,
    summary="Log an analytics event",
    description="Log a new analytics/tracking event.",
)
# PUBLIC_INTERFACE
def create_analytics_event(
    event_data: AnalyticsEventCreate,
    db: Session = Depends(get_db),
):
    """Log a new analytics event."""
    try:
        event = log_event(
            db,
            event_type=event_data.event_type,
            game_id=event_data.game_id,
            player_id=event_data.player_id,
            event_data=event_data.event_data,
            session_id=event_data.session_id,
            device_info=event_data.device_info,
        )
        db.commit()
        db.refresh(event)
        return event
    except Exception as e:
        db.rollback()
        logger.error("Failed to log analytics event: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")


@analytics_router.get(
    "/events",
    response_model=List[AnalyticsEventResponse],
    summary="List analytics events",
    description="Retrieve analytics events with optional filters.",
)
# PUBLIC_INTERFACE
def list_analytics_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    game_id: Optional[uuid.UUID] = Query(None, description="Filter by game ID"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    db: Session = Depends(get_db),
):
    """List analytics events with optional filtering."""
    query = db.query(AnalyticsEvent)
    if event_type:
        query = query.filter(AnalyticsEvent.event_type == event_type)
    if game_id:
        query = query.filter(AnalyticsEvent.game_id == game_id)
    return query.order_by(AnalyticsEvent.created_at.desc()).limit(limit).all()


# ====================
# AI Endpoints
# ====================

@ai_router.post(
    "/move",
    response_model=AIMoveResponse,
    summary="Request an AI move",
    description="Generate and execute an AI move for the current game. The AI uses heuristic strategies based on difficulty.",
)
# PUBLIC_INTERFACE
def request_ai_move(
    move_request: AIMoveRequest,
    db: Session = Depends(get_db),
):
    """
    Generate an AI move and submit it as a turn.

    The AI generates a move based on difficulty, then processes
    it through the same game logic as a human move.
    """
    try:
        game = db.query(Game).filter(Game.id == move_request.game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.status != "in_progress":
            raise HTTPException(status_code=400, detail="Game is not in progress")

        # Verify current turn player is AI
        current_player = (
            db.query(Player)
            .filter(Player.id == game.current_turn_player_id)
            .first()
        )
        if not current_player:
            raise HTTPException(status_code=400, detail="No current turn player")

        # Generate AI move
        ai_move = generate_ai_move(move_request.difficulty)

        # Create turn data and process through game logic
        turn_data = TurnCreate(
            player_id=current_player.id,
            striker_position_x=ai_move["striker_position_x"],
            striker_position_y=ai_move["striker_position_y"],
            striker_angle=ai_move["striker_angle"],
            striker_force=ai_move["striker_force"],
            coins_pocketed=ai_move["coins_pocketed"],
        )

        # Use the existing turn creation logic
        turn_response = create_turn(move_request.game_id, turn_data, db)

        log_game_event(db, move_request.game_id, "ai_move", {
            "difficulty": move_request.difficulty,
            "player_id": str(current_player.id),
        })

        return AIMoveResponse(
            turn=turn_response,
            message=f"AI ({move_request.difficulty}) move completed",
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("AI move failed: %s", str(e))
        raise HTTPException(status_code=500, detail=f"AI move failed: {str(e)}")


# ====================
# Game State Endpoint
# ====================

@game_router.get(
    "/{game_id}/state",
    response_model=GameStateResponse,
    summary="Get full game state",
    description="Retrieve the complete game state including all turns. Used for initial state sync.",
)
# PUBLIC_INTERFACE
def get_game_state(game_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get the full game state including game data and all turns."""
    game = (
        db.query(Game)
        .options(
            joinedload(Game.game_players).joinedload(GamePlayer.player),
            joinedload(Game.settings),
        )
        .filter(Game.id == game_id)
        .first()
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    turns = (
        db.query(Turn)
        .filter(Turn.game_id == game_id)
        .order_by(Turn.turn_number)
        .all()
    )

    return GameStateResponse(
        game=game,
        turns=turns,
        message="Game state retrieved successfully",
    )
