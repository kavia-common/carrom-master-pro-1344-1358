"""
WebSocket connection manager for real-time game state synchronization.

Manages WebSocket connections grouped by game ID, enabling
live broadcasting of game state updates to all connected clients.
"""
import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time game updates.

    Connections are organized by game_id, allowing targeted
    broadcasting of game state changes to relevant clients.
    """

    def __init__(self):
        """Initialize the connection manager with empty connection pools."""
        # Map of game_id -> set of WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = {}

    # PUBLIC_INTERFACE
    async def connect(self, websocket: WebSocket, game_id: str):
        """
        Accept a WebSocket connection and register it for a game.

        Args:
            websocket: The WebSocket connection to register.
            game_id: The game ID to associate with this connection.
        """
        await websocket.accept()
        if game_id not in self._connections:
            self._connections[game_id] = []
        self._connections[game_id].append(websocket)
        logger.info("WebSocket connected for game %s (total: %d)",
                     game_id, len(self._connections[game_id]))

    # PUBLIC_INTERFACE
    def disconnect(self, websocket: WebSocket, game_id: str):
        """
        Remove a WebSocket connection from a game's connection pool.

        Args:
            websocket: The WebSocket connection to remove.
            game_id: The game ID to disassociate from.
        """
        if game_id in self._connections:
            if websocket in self._connections[game_id]:
                self._connections[game_id].remove(websocket)
            if not self._connections[game_id]:
                del self._connections[game_id]
        logger.info("WebSocket disconnected from game %s", game_id)

    # PUBLIC_INTERFACE
    async def broadcast_to_game(self, game_id: str, message: dict):
        """
        Broadcast a JSON message to all clients connected to a specific game.

        Args:
            game_id: The game ID to broadcast to.
            message: Dictionary to be sent as JSON to all connected clients.
        """
        if game_id not in self._connections:
            return

        disconnected = []
        for connection in self._connections[game_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("Failed to send to WebSocket: %s", str(e))
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, game_id)

    # PUBLIC_INTERFACE
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Send a JSON message to a specific WebSocket client.

        Args:
            websocket: The target WebSocket connection.
            message: Dictionary to send as JSON.
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("Failed to send personal message: %s", str(e))

    # PUBLIC_INTERFACE
    def get_connection_count(self, game_id: str) -> int:
        """
        Get the number of active connections for a game.

        Args:
            game_id: The game ID to check.

        Returns:
            Number of active WebSocket connections.
        """
        return len(self._connections.get(game_id, []))

    # PUBLIC_INTERFACE
    def get_total_connections(self) -> int:
        """
        Get the total number of active WebSocket connections across all games.

        Returns:
            Total active connection count.
        """
        return sum(len(conns) for conns in self._connections.values())


# Singleton instance
manager = ConnectionManager()
