"""
Carrom Master Pro - FastAPI Backend Application

Main entry point for the carrom game backend server.
Provides REST API endpoints for game management, player actions,
scoring, settings, analytics, and AI moves.
Includes WebSocket endpoint for real-time game state synchronization.

API Documentation available at /docs (Swagger UI) and /redoc (ReDoc).
WebSocket endpoint: ws://<host>/ws/{game_id} for live game state updates.
"""
import logging
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from src.api.database import get_db, engine, Base
from src.api.models import Game, GamePlayer, Turn
from src.api.websocket_manager import manager
from src.api.routes import (
    player_router,
    game_router,
    turn_router,
    score_router,
    settings_router,
    analytics_router,
    ai_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# OpenAPI tags metadata for documentation grouping
openapi_tags = [
    {
        "name": "Health",
        "description": "Health check and server status endpoints.",
    },
    {
        "name": "Players",
        "description": "Player registration and management.",
    },
    {
        "name": "Games",
        "description": "Game creation, status management, and state retrieval.",
    },
    {
        "name": "Turns",
        "description": "Submit and retrieve game moves/turns.",
    },
    {
        "name": "Scores",
        "description": "Score tracking and retrieval.",
    },
    {
        "name": "Settings",
        "description": "Game settings configuration.",
    },
    {
        "name": "Analytics",
        "description": "Analytics event logging and retrieval.",
    },
    {
        "name": "AI",
        "description": "AI move generation for computer-controlled players.",
    },
    {
        "name": "WebSocket",
        "description": "Real-time game state synchronization via WebSocket. "
                       "Connect to ws://<host>/ws/{game_id} to receive live updates.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    logger.info("Carrom Backend starting up...")
    # Tables already exist in the database; we don't create them here
    # to avoid conflicts with the managed database schema.
    yield
    logger.info("Carrom Backend shutting down...")


app = FastAPI(
    title="Carrom Master Pro API",
    description=(
        "Backend API for the Carrom Master Pro game. "
        "Provides game logic, turn management, scoring, AI opponents, "
        "and real-time game state synchronization via WebSocket.\n\n"
        "## WebSocket Usage\n"
        "Connect to `ws://<host>/ws/{game_id}` to receive real-time game state updates.\n"
        "Send JSON messages with `type` field to interact:\n"
        "- `{\"type\": \"get_state\"}` - Request current game state\n"
        "- `{\"type\": \"ping\"}` - Keep-alive ping\n"
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(player_router)
app.include_router(game_router)
app.include_router(turn_router)
app.include_router(score_router)
app.include_router(settings_router)
app.include_router(analytics_router)
app.include_router(ai_router)


# ====================
# Health & Info Endpoints
# ====================

@app.get(
    "/",
    tags=["Health"],
    summary="Health Check",
    description="Returns server health status and basic info.",
)
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint returning server status."""
    return {
        "status": "healthy",
        "service": "carrom-backend",
        "version": "1.0.0",
        "websocket_info": "Connect to /ws/{game_id} for real-time game updates",
    }


@app.get(
    "/ws-docs",
    tags=["WebSocket"],
    summary="WebSocket Usage Documentation",
    description="Returns documentation on how to use the WebSocket endpoint for real-time game sync.",
)
# PUBLIC_INTERFACE
def websocket_docs():
    """Provide WebSocket usage documentation."""
    return {
        "endpoint": "/ws/{game_id}",
        "protocol": "WebSocket",
        "description": "Real-time game state synchronization",
        "usage": {
            "connect": "ws://<host>/ws/<game_id>",
            "messages": {
                "get_state": {
                    "send": {"type": "get_state"},
                    "receive": "Full game state JSON including game data and turns",
                },
                "ping": {
                    "send": {"type": "ping"},
                    "receive": {"type": "pong"},
                },
            },
            "broadcasts": (
                "Server broadcasts game state updates to all connected clients "
                "when turns are played or game state changes. "
                "Broadcast messages have type 'game_update'."
            ),
        },
    }


# ====================
# WebSocket Endpoint
# ====================

@app.websocket("/ws/{game_id}")
async def websocket_game_endpoint(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint for real-time game state synchronization.

    Connects a client to a specific game's live update channel.
    Clients receive broadcasts whenever the game state changes.

    Supported incoming message types:
    - get_state: Returns the current full game state
    - ping: Returns a pong message for keep-alive

    Args:
        websocket: The WebSocket connection.
        game_id: The game UUID to subscribe to.

    WebSocket Protocol:
        - operation_id: ws_game_sync
        - tags: WebSocket
    """
    await manager.connect(websocket, game_id)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(websocket, {
            "type": "connected",
            "game_id": game_id,
            "message": "Connected to game updates",
        })

        while True:
            # Wait for client messages
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type", "")

                if msg_type == "get_state":
                    # Retrieve and send current game state
                    game_state = _get_game_state_dict(game_id)
                    await manager.send_personal_message(websocket, {
                        "type": "game_state",
                        "data": game_state,
                    })

                elif msg_type == "ping":
                    await manager.send_personal_message(websocket, {
                        "type": "pong",
                    })

                else:
                    await manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

            except json.JSONDecodeError:
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Invalid JSON message",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)
        logger.info("Client disconnected from game %s", game_id)
    except Exception as e:
        manager.disconnect(websocket, game_id)
        logger.error("WebSocket error for game %s: %s", game_id, str(e))


def _get_game_state_dict(game_id: str) -> dict:
    """
    Helper to retrieve game state as a serializable dictionary.

    Args:
        game_id: The game UUID string.

    Returns:
        Dictionary with game data, players, settings, and turns.
    """
    db = next(get_db())
    try:
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
            return {"error": "Game not found"}

        turns = (
            db.query(Turn)
            .filter(Turn.game_id == game_id)
            .order_by(Turn.turn_number)
            .all()
        )

        # Serialize game state
        game_players_data = []
        for gp in game.game_players:
            game_players_data.append({
                "id": str(gp.id),
                "game_id": str(gp.game_id),
                "player_id": str(gp.player_id),
                "score": gp.score,
                "turn_order": gp.turn_order,
                "player": {
                    "id": str(gp.player.id),
                    "name": gp.player.name,
                    "player_type": gp.player.type if hasattr(gp.player, 'type') else gp.player.player_type,
                    "ai_difficulty": gp.player.ai_difficulty,
                } if gp.player else None,
            })

        settings_data = None
        if game.settings:
            settings_data = {
                "id": str(game.settings.id),
                "game_id": str(game.settings.game_id),
                "sound_enabled": game.settings.sound_enabled,
                "physics_speed": game.settings.physics_speed,
                "board_friction": game.settings.board_friction,
                "striker_max_force": game.settings.striker_max_force,
                "timer_per_turn": game.settings.timer_per_turn,
                "scoring_mode": game.settings.scoring_mode,
            }

        turns_data = []
        for t in turns:
            turns_data.append({
                "id": str(t.id),
                "game_id": str(t.game_id),
                "player_id": str(t.player_id),
                "turn_number": t.turn_number,
                "striker_position_x": t.striker_position_x,
                "striker_position_y": t.striker_position_y,
                "striker_angle": t.striker_angle,
                "striker_force": t.striker_force,
                "coins_pocketed": t.coins_pocketed or [],
                "foul": t.foul,
                "foul_reason": t.foul_reason,
                "points_earned": t.points_earned,
            })

        return {
            "game": {
                "id": str(game.id),
                "mode": game.mode,
                "status": game.status,
                "current_turn_player_id": str(game.current_turn_player_id) if game.current_turn_player_id else None,
                "winner_id": str(game.winner_id) if game.winner_id else None,
                "game_players": game_players_data,
                "settings": settings_data,
            },
            "turns": turns_data,
        }

    except Exception as e:
        logger.error("Failed to get game state: %s", str(e))
        return {"error": str(e)}
    finally:
        db.close()
