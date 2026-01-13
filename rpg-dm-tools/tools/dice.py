"""Dice rolling tool for RPG DM Tools."""

import random
import re
from typing import Dict, Any


def roll_dice(notation: str) -> Dict[str, Any]:
    """
    Roll dice using standard dice notation.

    Parses notation like "2d6+3", "1d20", "4d6-1", "d20", "3d6" and simulates
    the dice rolls. Use this when you need random outcomes for combat, skill
    checks, or any situation requiring chance.

    Args:
        notation: Dice notation string (e.g., "2d6+3", "d20", "1d20-2")
                  Format: [count]d<sides>[+/-modifier]

    Returns:
        Dictionary with:
        - notation: The original notation string
        - rolls: List of individual die results
        - modifier: The +/- modifier (0 if none)
        - total: Sum of all rolls plus modifier

    Examples:
        roll_dice("2d6+3") -> {"notation": "2d6+3", "rolls": [4, 2], "modifier": 3, "total": 9}
        roll_dice("d20") -> {"notation": "d20", "rolls": [15], "modifier": 0, "total": 15}
    """
    # Normalize input
    notation = notation.strip().lower()

    # Regex pattern to parse dice notation
    # Matches: optional count, 'd', sides, optional modifier
    pattern = r'^(\d*)d(\d+)([+-]\d+)?$'
    match = re.match(pattern, notation)

    if not match:
        return {
            "success": False,
            "error": f"Invalid dice notation: '{notation}'",
            "hint": "Use format like '2d6+3', '1d20', 'd20', or '4d6-1'"
        }

    # Extract components
    count_str, sides_str, modifier_str = match.groups()

    # Parse count (default to 1 if not specified)
    count = int(count_str) if count_str else 1

    # Parse sides
    sides = int(sides_str)

    # Parse modifier (default to 0 if not specified)
    modifier = int(modifier_str) if modifier_str else 0

    # Validate inputs
    if count < 1 or count > 100:
        return {
            "success": False,
            "error": f"Invalid dice count: {count}",
            "hint": "Dice count must be between 1 and 100"
        }

    if sides < 2 or sides > 1000:
        return {
            "success": False,
            "error": f"Invalid dice sides: {sides}",
            "hint": "Dice sides must be between 2 and 1000"
        }

    # Roll the dice
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    return {
        "notation": notation,
        "rolls": rolls,
        "modifier": modifier,
        "total": total
    }
