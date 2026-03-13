"""
Simple heuristic AI engine for carrom gameplay.

Provides AI move generation based on difficulty levels:
- easy: Random moves with low precision
- medium: Semi-targeted moves with moderate precision
- hard: Targeted moves with high precision and strategy
"""
import random
import math
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Board dimensions (normalized coordinates)
BOARD_MIN = 0.0
BOARD_MAX = 100.0
BOARD_CENTER = 50.0

# Pocket positions (four corners)
POCKETS = [
    (5.0, 5.0),
    (95.0, 5.0),
    (5.0, 95.0),
    (95.0, 95.0),
]

# Striker baseline Y position (player side)
STRIKER_Y = 85.0
STRIKER_MIN_X = 25.0
STRIKER_MAX_X = 75.0


# PUBLIC_INTERFACE
def generate_ai_move(difficulty: str = "easy") -> dict:
    """
    Generate an AI move based on difficulty level.

    Uses heuristic rules to determine striker position, angle, and force.
    Higher difficulty levels produce more accurate and strategic shots.

    Args:
        difficulty: AI difficulty level ('easy', 'medium', 'hard').

    Returns:
        Dictionary with keys: striker_position_x, striker_position_y,
        striker_angle, striker_force, coins_pocketed (simulated result).
    """
    if difficulty == "hard":
        return _generate_hard_move()
    elif difficulty == "medium":
        return _generate_medium_move()
    else:
        return _generate_easy_move()


def _generate_easy_move() -> dict:
    """Generate a random/low-skill AI move."""
    # Random position along the baseline
    pos_x = random.uniform(STRIKER_MIN_X, STRIKER_MAX_X)
    pos_y = STRIKER_Y

    # Random angle with wide spread (less accurate)
    angle = random.uniform(-60.0, 60.0)

    # Low to medium force
    force = random.uniform(20.0, 60.0)

    # Easy AI rarely pockets coins
    coins_pocketed = _simulate_pocket_result(accuracy=0.15)

    logger.info("AI (easy) move: pos=(%.1f, %.1f), angle=%.1f, force=%.1f",
                pos_x, pos_y, angle, force)

    return {
        "striker_position_x": round(pos_x, 2),
        "striker_position_y": round(pos_y, 2),
        "striker_angle": round(angle, 2),
        "striker_force": round(force, 2),
        "coins_pocketed": coins_pocketed,
    }


def _generate_medium_move() -> dict:
    """Generate a semi-targeted AI move with moderate accuracy."""
    # Aim towards center area where coins likely are
    target_pocket = random.choice(POCKETS)

    # Calculate angle towards a random pocket from center area
    aim_x = BOARD_CENTER + random.uniform(-15.0, 15.0)
    angle = _calculate_angle(aim_x, STRIKER_Y, target_pocket[0], target_pocket[1])

    # Add some noise for medium difficulty
    angle += random.uniform(-15.0, 15.0)

    pos_x = _clamp(aim_x + random.uniform(-10.0, 10.0), STRIKER_MIN_X, STRIKER_MAX_X)
    pos_y = STRIKER_Y

    force = random.uniform(35.0, 75.0)

    coins_pocketed = _simulate_pocket_result(accuracy=0.35)

    logger.info("AI (medium) move: pos=(%.1f, %.1f), angle=%.1f, force=%.1f",
                pos_x, pos_y, angle, force)

    return {
        "striker_position_x": round(pos_x, 2),
        "striker_position_y": round(pos_y, 2),
        "striker_angle": round(angle, 2),
        "striker_force": round(force, 2),
        "coins_pocketed": coins_pocketed,
    }


def _generate_hard_move() -> dict:
    """Generate a strategic AI move with high accuracy."""
    # Pick the nearest pocket and aim precisely
    target_pocket = random.choice(POCKETS)

    # Position striker optimally
    optimal_x = BOARD_CENTER + random.uniform(-5.0, 5.0)
    pos_x = _clamp(optimal_x, STRIKER_MIN_X, STRIKER_MAX_X)
    pos_y = STRIKER_Y

    # Calculate precise angle with minimal noise
    angle = _calculate_angle(pos_x, pos_y, target_pocket[0], target_pocket[1])
    angle += random.uniform(-5.0, 5.0)

    # Optimal force
    force = random.uniform(45.0, 85.0)

    coins_pocketed = _simulate_pocket_result(accuracy=0.55)

    logger.info("AI (hard) move: pos=(%.1f, %.1f), angle=%.1f, force=%.1f",
                pos_x, pos_y, angle, force)

    return {
        "striker_position_x": round(pos_x, 2),
        "striker_position_y": round(pos_y, 2),
        "striker_angle": round(angle, 2),
        "striker_force": round(force, 2),
        "coins_pocketed": coins_pocketed,
    }


def _calculate_angle(from_x: float, from_y: float, to_x: float, to_y: float) -> float:
    """Calculate angle in degrees from one point to another."""
    dx = to_x - from_x
    dy = to_y - from_y
    angle_rad = math.atan2(dy, dx)
    return math.degrees(angle_rad)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def _simulate_pocket_result(accuracy: float) -> List[str]:
    """
    Simulate which coins get pocketed based on AI accuracy.

    Args:
        accuracy: Probability (0-1) of pocketing a coin.

    Returns:
        List of coin type strings that were pocketed.
    """
    pocketed = []
    coin_types = ["white", "black"]

    # Determine how many coins could be pocketed (usually 0-2)
    for coin_type in coin_types:
        if random.random() < accuracy:
            pocketed.append(coin_type)

    # Queen has lower probability
    if random.random() < (accuracy * 0.3):
        pocketed.append("queen")

    return pocketed
