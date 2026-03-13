"""
Carrom game logic module.

Handles turn management, scoring rules, foul detection,
win condition checking, and related game state operations.
"""
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.api.models import Game, GamePlayer, Turn

logger = logging.getLogger(__name__)

# Scoring constants
POINTS_WHITE = 1
POINTS_BLACK = 1
POINTS_QUEEN = 3
FOUL_PENALTY = -1
WIN_SCORE_THRESHOLD = 25  # Standard carrom winning score


# PUBLIC_INTERFACE
def calculate_turn_score(coins_pocketed: List[str]) -> int:
    """
    Calculate the score for a single turn based on coins pocketed.

    Args:
        coins_pocketed: List of coin type strings ('white', 'black', 'queen').

    Returns:
        Total points earned this turn.
    """
    score = 0
    for coin in coins_pocketed:
        coin_lower = coin.lower().strip()
        if coin_lower == "white":
            score += POINTS_WHITE
        elif coin_lower == "black":
            score += POINTS_BLACK
        elif coin_lower == "queen":
            score += POINTS_QUEEN
    return score


# PUBLIC_INTERFACE
def detect_foul(
    striker_force: float,
    striker_max_force: float,
    coins_pocketed: List[str],
    striker_pocketed: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Detect if a foul was committed during a turn.

    Foul conditions:
    - Striker was pocketed
    - Striker force exceeds maximum allowed force
    - No coins were pocketed (not a foul but ends turn without extra turn)

    Args:
        striker_force: Force applied to the striker.
        striker_max_force: Maximum allowed force from settings.
        coins_pocketed: List of coins pocketed this turn.
        striker_pocketed: Whether the striker itself was pocketed.

    Returns:
        Tuple of (is_foul, foul_reason).
    """
    if striker_pocketed:
        return True, "Striker was pocketed"

    if striker_force > striker_max_force:
        return True, f"Striker force ({striker_force:.1f}) exceeds maximum ({striker_max_force:.1f})"

    return False, None


# PUBLIC_INTERFACE
def apply_foul_penalty(db: Session, game_player: GamePlayer) -> int:
    """
    Apply foul penalty to a player's score.

    Args:
        db: Database session.
        game_player: The GamePlayer record to penalize.

    Returns:
        The new score after penalty.
    """
    game_player.score = max(0, game_player.score + FOUL_PENALTY)
    db.flush()
    logger.info(
        "Foul penalty applied to player %s, new score: %d",
        game_player.player_id, game_player.score
    )
    return game_player.score


# PUBLIC_INTERFACE
def update_score(db: Session, game_player: GamePlayer, points: int) -> int:
    """
    Update a player's score after a turn.

    Args:
        db: Database session.
        game_player: The GamePlayer record to update.
        points: Points to add (can be negative for penalties).

    Returns:
        The new score.
    """
    game_player.score = max(0, game_player.score + points)
    db.flush()
    return game_player.score


# PUBLIC_INTERFACE
def check_win_condition(
    db: Session,
    game: Game,
    scoring_mode: str = "standard",
) -> Optional[GamePlayer]:
    """
    Check if any player has met the win condition.

    Win conditions:
    - Standard mode: First player to reach WIN_SCORE_THRESHOLD points.
    - Freestyle mode: All coins pocketed; player with highest score wins.

    Args:
        db: Database session.
        game: The Game record to check.
        scoring_mode: The scoring mode ('standard' or 'freestyle').

    Returns:
        The winning GamePlayer if win condition met, else None.
    """
    game_players = (
        db.query(GamePlayer)
        .filter(GamePlayer.game_id == game.id)
        .order_by(GamePlayer.score.desc())
        .all()
    )

    if not game_players:
        return None

    if scoring_mode == "standard":
        # First player to reach threshold wins
        for gp in game_players:
            if gp.score >= WIN_SCORE_THRESHOLD:
                return gp

    # For freestyle or if no standard winner, check if all coins are pocketed
    total_turns = db.query(Turn).filter(Turn.game_id == game.id).count()
    if total_turns > 0:
        # Count total coins pocketed across all turns
        turns = db.query(Turn).filter(Turn.game_id == game.id).all()
        total_pocketed = sum(len(t.coins_pocketed or []) for t in turns)
        # Standard carrom: 9 white + 9 black + 1 queen = 19 coins
        if total_pocketed >= 19:
            return game_players[0]  # Highest scorer wins

    return None


# PUBLIC_INTERFACE
def get_next_turn_player(
    db: Session,
    game: Game,
    current_player_id,
    earned_extra_turn: bool = False,
) -> Optional[GamePlayer]:
    """
    Determine which player takes the next turn.

    If the current player pocketed a coin (earned extra turn), they go again.
    Otherwise, turn passes to the next player in turn order.

    Args:
        db: Database session.
        game: The Game record.
        current_player_id: UUID of the current player.
        earned_extra_turn: Whether the current player earned an extra turn.

    Returns:
        The GamePlayer who should take the next turn.
    """
    game_players = (
        db.query(GamePlayer)
        .filter(GamePlayer.game_id == game.id)
        .order_by(GamePlayer.turn_order)
        .all()
    )

    if not game_players:
        return None

    # If player pocketed a coin and no foul, they get another turn
    if earned_extra_turn:
        for gp in game_players:
            if str(gp.player_id) == str(current_player_id):
                return gp

    # Find current player's turn order and advance to next
    current_order = 0
    for gp in game_players:
        if str(gp.player_id) == str(current_player_id):
            current_order = gp.turn_order
            break

    # Get next player (wrap around)
    next_order = (current_order + 1) % len(game_players)
    for gp in game_players:
        if gp.turn_order == next_order:
            return gp

    # Fallback: return first player
    return game_players[0]


# PUBLIC_INTERFACE
def get_turn_number(db: Session, game_id) -> int:
    """
    Get the next turn number for a game.

    Args:
        db: Database session.
        game_id: The game's UUID.

    Returns:
        The next sequential turn number.
    """
    max_turn = (
        db.query(Turn.turn_number)
        .filter(Turn.game_id == game_id)
        .order_by(Turn.turn_number.desc())
        .first()
    )
    return (max_turn[0] + 1) if max_turn else 1
