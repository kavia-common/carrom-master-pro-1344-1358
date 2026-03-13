"""
Analytics logging module for the carrom backend.

Provides functions for logging game events, player actions,
errors, and performance metrics to the analytics_events table.
"""
import logging
import uuid
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.api.models import AnalyticsEvent

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def log_event(
    db: Session,
    event_type: str,
    game_id: Optional[uuid.UUID] = None,
    player_id: Optional[uuid.UUID] = None,
    event_data: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    device_info: Optional[Dict[str, Any]] = None,
) -> AnalyticsEvent:
    """
    Log an analytics event to the database.

    Args:
        db: Database session.
        event_type: Type/category of the event (e.g., 'game_started', 'turn_played').
        game_id: Optional associated game ID.
        player_id: Optional associated player ID.
        event_data: Optional dictionary of event-specific data.
        session_id: Optional client session identifier.
        device_info: Optional device information dictionary.

    Returns:
        The created AnalyticsEvent record.
    """
    event = AnalyticsEvent(
        event_type=event_type,
        game_id=game_id,
        player_id=player_id,
        event_data=event_data or {},
        session_id=session_id,
        device_info=device_info or {},
    )
    db.add(event)
    db.flush()

    logger.info(
        "Analytics event logged: type=%s, game=%s, player=%s",
        event_type, game_id, player_id
    )
    return event


# PUBLIC_INTERFACE
def log_game_event(db: Session, game_id: uuid.UUID, event_type: str, data: Optional[Dict[str, Any]] = None) -> AnalyticsEvent:
    """
    Convenience function to log a game-related event.

    Args:
        db: Database session.
        game_id: The game's UUID.
        event_type: Event type string.
        data: Optional event data.

    Returns:
        The created AnalyticsEvent record.
    """
    return log_event(db, event_type=event_type, game_id=game_id, event_data=data)


# PUBLIC_INTERFACE
def log_error_event(
    db: Session,
    error_message: str,
    error_type: str = "error",
    game_id: Optional[uuid.UUID] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> AnalyticsEvent:
    """
    Log an error or crash event for monitoring.

    Args:
        db: Database session.
        error_message: Description of the error.
        error_type: Error category (default: 'error').
        game_id: Optional associated game ID.
        extra_data: Additional error context.

    Returns:
        The created AnalyticsEvent record.
    """
    event_data = {"error_message": error_message}
    if extra_data:
        event_data.update(extra_data)

    return log_event(
        db,
        event_type=error_type,
        game_id=game_id,
        event_data=event_data,
    )
