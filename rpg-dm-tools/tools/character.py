"""Character sheet management tools for RPG DM Tools."""

from typing import Dict, Any
from utils.state import (
    ensure_session_exists,
    get_session_path,
    read_json,
    write_json,
)


def read_character(session_id: str, character_name: str) -> Dict[str, Any]:
    """
    Read a character's full character sheet.

    Use this to get all information about a character including stats,
    inventory, gold, and notes. Essential for checking character status
    before combat or when players ask about their abilities.

    Args:
        session_id: The game session identifier
        character_name: Name of the character to read

    Returns:
        Dictionary with full character sheet:
        - name: Character name
        - stats: Dictionary of stats (hp, max_hp, strength, dexterity, wisdom)
        - inventory: List of items
        - gold: Current gold amount
        - notes: List of notes

        Or if not found:
        - success: False
        - error: Error message
    """
    if not ensure_session_exists(session_id):
        return {
            "success": False,
            "error": f"Session '{session_id}' does not exist",
            "hint": "Create a session first with create_session"
        }

    character_path = get_session_path(session_id) / "characters" / f"{character_name}.json"
    character = read_json(character_path)

    if character is None:
        return {
            "success": False,
            "error": f"Character '{character_name}' not found in session '{session_id}'",
            "hint": "Check the character name or create a new session"
        }

    return character


def update_character(session_id: str, character_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a character sheet with new values.

    Use this to modify character stats, inventory, gold, or notes. Supports
    special syntax for common operations like adding items or adjusting numbers.

    Args:
        session_id: The game session identifier
        character_name: Name of the character to update
        updates: Dictionary of updates to apply. Supports special syntax:
                 - {"stats.hp": 15} - Set nested value
                 - {"inventory+": "torch"} - Append to list
                 - {"inventory-": "rope"} - Remove from list
                 - {"gold": "+10"} - Increment number
                 - {"gold": "-5"} - Decrement number

    Returns:
        Dictionary with:
        - success: True if update succeeded
        - character: The updated character sheet

        Or if failed:
        - success: False
        - error: Error message
    """
    if not ensure_session_exists(session_id):
        return {
            "success": False,
            "error": f"Session '{session_id}' does not exist",
            "hint": "Create a session first with create_session"
        }

    character_path = get_session_path(session_id) / "characters" / f"{character_name}.json"
    character = read_json(character_path)

    if character is None:
        return {
            "success": False,
            "error": f"Character '{character_name}' not found in session '{session_id}'",
            "hint": "Check the character name or create a new session"
        }

    # Apply updates
    for key, value in updates.items():
        try:
            # Handle list append (key+)
            if key.endswith("+"):
                actual_key = key[:-1]
                if actual_key not in character:
                    character[actual_key] = []
                if not isinstance(character[actual_key], list):
                    return {
                        "success": False,
                        "error": f"Cannot append to '{actual_key}': not a list",
                        "hint": f"'{actual_key}' is a {type(character[actual_key]).__name__}"
                    }
                character[actual_key].append(value)
                continue

            # Handle list remove (key-)
            if key.endswith("-"):
                actual_key = key[:-1]
                if actual_key not in character:
                    return {
                        "success": False,
                        "error": f"Cannot remove from '{actual_key}': field doesn't exist",
                        "hint": "Check the field name"
                    }
                if not isinstance(character[actual_key], list):
                    return {
                        "success": False,
                        "error": f"Cannot remove from '{actual_key}': not a list",
                        "hint": f"'{actual_key}' is a {type(character[actual_key]).__name__}"
                    }
                if value in character[actual_key]:
                    character[actual_key].remove(value)
                else:
                    return {
                        "success": False,
                        "error": f"Item '{value}' not found in '{actual_key}'",
                        "hint": f"Current items: {character[actual_key]}"
                    }
                continue

            # Handle nested keys (key.subkey)
            if "." in key:
                parts = key.split(".")
                target = character
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                final_key = parts[-1]

                # Handle increment/decrement for nested keys
                if isinstance(value, str) and value.startswith(("+", "-")):
                    try:
                        delta = int(value)
                        current = target.get(final_key, 0)
                        new_value = current + delta

                        # Validate hp constraints
                        if final_key == "hp" and "max_hp" in target:
                            if new_value > target["max_hp"]:
                                new_value = target["max_hp"]

                        target[final_key] = new_value
                    except ValueError:
                        return {
                            "success": False,
                            "error": f"Invalid increment value: '{value}'",
                            "hint": "Use format like '+10' or '-5'"
                        }
                else:
                    target[final_key] = value
                continue

            # Handle increment/decrement for top-level numeric fields
            if isinstance(value, str) and value.startswith(("+", "-")):
                try:
                    delta = int(value)
                    current = character.get(key, 0)
                    new_value = current + delta

                    # Validate gold can't go negative
                    if key == "gold" and new_value < 0:
                        return {
                            "success": False,
                            "error": f"Insufficient gold: have {current}, need {abs(delta)}",
                            "hint": "Check gold amount before spending"
                        }

                    character[key] = new_value
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid increment value: '{value}'",
                        "hint": "Use format like '+10' or '-5'"
                    }
                continue

            # Simple key=value assignment
            character[key] = value

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to apply update '{key}': {str(e)}",
                "hint": "Check the update format"
            }

    # Validate hp doesn't exceed max_hp
    if "stats" in character and isinstance(character["stats"], dict):
        stats = character["stats"]
        if "hp" in stats and "max_hp" in stats:
            if stats["hp"] > stats["max_hp"]:
                stats["hp"] = stats["max_hp"]

    # Save updated character
    try:
        write_json(character_path, character)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save character: {str(e)}",
            "hint": "Check file permissions"
        }

    return {
        "success": True,
        "character": character
    }
