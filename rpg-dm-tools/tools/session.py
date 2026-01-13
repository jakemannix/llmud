"""Session management tools for RPG DM Tools."""

import os
import shutil
from typing import Dict, Any
from utils.state import (
    get_session_path,
    get_map_data,
    get_default_character,
    write_json,
    read_json,
    ensure_session_exists,
)


def create_session(session_id: str, character_name: str) -> Dict[str, Any]:
    """
    Create a new game session with a starting character.

    Call this at the beginning of a new adventure to initialize a fresh game
    state. Creates the session directory, sets up a character with default
    stats, and positions them in the starting room.

    Args:
        session_id: Unique identifier for this game session (e.g., "adventure_001")
        character_name: Name for the player's character

    Returns:
        Dictionary with:
        - session_id: The created session ID
        - character: The character name
        - starting_room: The initial room location

        Or if session already exists:
        - success: False
        - error: Error message
    """
    # Validate inputs
    if not session_id or not session_id.strip():
        return {
            "success": False,
            "error": "Session ID cannot be empty",
            "hint": "Provide a unique session identifier"
        }

    if not character_name or not character_name.strip():
        return {
            "success": False,
            "error": "Character name cannot be empty",
            "hint": "Provide a name for the character"
        }

    # Sanitize session_id (allow only alphanumeric and underscores)
    safe_session_id = "".join(c for c in session_id if c.isalnum() or c == "_")
    if safe_session_id != session_id:
        return {
            "success": False,
            "error": f"Invalid session ID: '{session_id}'",
            "hint": "Session ID can only contain letters, numbers, and underscores"
        }

    session_path = get_session_path(session_id)

    # Check if session already exists
    if session_path.exists():
        return {
            "success": False,
            "error": f"Session '{session_id}' already exists",
            "hint": "Use a different session ID or call get_session_state to resume"
        }

    # Get the starting room from the map
    map_data = get_map_data("village")
    if map_data is None:
        return {
            "success": False,
            "error": "Map data not found",
            "hint": "Ensure game_data/maps/village.json exists"
        }

    starting_room = map_data.get("starting_room", "tavern")

    # Create session directory structure
    try:
        (session_path / "characters").mkdir(parents=True, exist_ok=True)

        # Create character file
        character = get_default_character()
        character["name"] = character_name
        character_path = session_path / "characters" / f"{character_name}.json"
        write_json(character_path, character)

        # Create game state file
        game_state = {
            "current_room": starting_room,
            "current_map": "village",
            "characters": [character_name],
            "active_quests": [],
            "event_flags": {},
            "turn_count": 0
        }
        write_json(session_path / "game_state.json", game_state)

    except Exception as e:
        # Clean up on failure
        if session_path.exists():
            shutil.rmtree(session_path)
        return {
            "success": False,
            "error": f"Failed to create session: {str(e)}",
            "hint": "Check file permissions"
        }

    return {
        "session_id": session_id,
        "character": character_name,
        "starting_room": starting_room
    }


def get_session_state(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the current state of a game session.

    Use this to check the current game status including character positions,
    active quests, and event flags. Call this to resume a session or get
    an overview of the game state.

    Args:
        session_id: The session identifier to look up

    Returns:
        Dictionary with:
        - session_id: The session ID
        - current_room: Current room location
        - current_map: Active map name
        - characters: List of character names in session
        - active_quests: List of active quest IDs
        - event_flags: Dictionary of triggered events
        - turn_count: Number of turns elapsed

        Or if session doesn't exist:
        - success: False
        - error: Error message
    """
    if not ensure_session_exists(session_id):
        return {
            "success": False,
            "error": f"Session '{session_id}' does not exist",
            "hint": "Create a session first with create_session"
        }

    session_path = get_session_path(session_id)
    game_state = read_json(session_path / "game_state.json")

    if game_state is None:
        return {
            "success": False,
            "error": f"Game state file not found for session '{session_id}'",
            "hint": "Session may be corrupted, try creating a new one"
        }

    return {
        "session_id": session_id,
        "current_room": game_state.get("current_room", "unknown"),
        "current_map": game_state.get("current_map", "village"),
        "characters": game_state.get("characters", []),
        "active_quests": game_state.get("active_quests", []),
        "event_flags": game_state.get("event_flags", {}),
        "turn_count": game_state.get("turn_count", 0)
    }
