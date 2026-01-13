"""Map and movement tools for RPG DM Tools."""

from typing import Dict, Any
from utils.state import (
    ensure_session_exists,
    get_session_path,
    get_map_data,
    read_json,
    write_json,
)
from utils.svg import render_map_svg


def get_current_map(session_id: str) -> Dict[str, Any]:
    """
    Get the current map view with the player's position.

    Use this to see where the character is, get a description of their
    surroundings, and see available exits. Returns an SVG visualization
    of the map with the current room highlighted.

    Args:
        session_id: The game session identifier

    Returns:
        Dictionary with:
        - current_room: The room ID where the character is
        - room_description: Text description of the room
        - exits: Dictionary of direction -> room_id
        - svg: SVG string visualization of the map

        Or if session not found:
        - success: False
        - error: Error message
    """
    if not ensure_session_exists(session_id):
        return {
            "success": False,
            "error": f"Session '{session_id}' does not exist",
            "hint": "Create a session first with create_session"
        }

    # Load game state
    session_path = get_session_path(session_id)
    game_state = read_json(session_path / "game_state.json")

    if game_state is None:
        return {
            "success": False,
            "error": "Game state file not found",
            "hint": "Session may be corrupted"
        }

    current_room = game_state.get("current_room", "tavern")
    current_map_name = game_state.get("current_map", "village")

    # Load map data
    map_data = get_map_data(current_map_name)
    if map_data is None:
        return {
            "success": False,
            "error": f"Map '{current_map_name}' not found",
            "hint": "Check game_data/maps/ directory"
        }

    rooms = map_data.get("rooms", {})
    if current_room not in rooms:
        return {
            "success": False,
            "error": f"Room '{current_room}' not found in map",
            "hint": "Game state may be corrupted"
        }

    room = rooms[current_room]

    # Render SVG map
    svg = render_map_svg(rooms, current_room)

    return {
        "current_room": current_room,
        "room_description": room.get("description", ""),
        "exits": room.get("exits", {}),
        "svg": svg
    }


def move_character(session_id: str, direction: str) -> Dict[str, Any]:
    """
    Move the character in a direction to an adjacent room.

    Use this when the player wants to move. Validates that the direction
    is a valid exit from the current room. After a successful move, returns
    the new room information and updated map.

    Args:
        session_id: The game session identifier
        direction: Direction to move (e.g., "north", "south", "up", "down")

    Returns:
        On success - same format as get_current_map with new position:
        - current_room: The new room ID
        - room_description: Description of the new room
        - exits: Available exits from the new room
        - svg: Updated SVG map

        On invalid direction:
        - success: False
        - error: Error message
        - valid_exits: List of valid directions
    """
    if not ensure_session_exists(session_id):
        return {
            "success": False,
            "error": f"Session '{session_id}' does not exist",
            "hint": "Create a session first with create_session"
        }

    # Load game state
    session_path = get_session_path(session_id)
    game_state = read_json(session_path / "game_state.json")

    if game_state is None:
        return {
            "success": False,
            "error": "Game state file not found",
            "hint": "Session may be corrupted"
        }

    current_room = game_state.get("current_room", "tavern")
    current_map_name = game_state.get("current_map", "village")

    # Load map data
    map_data = get_map_data(current_map_name)
    if map_data is None:
        return {
            "success": False,
            "error": f"Map '{current_map_name}' not found",
            "hint": "Check game_data/maps/ directory"
        }

    rooms = map_data.get("rooms", {})
    if current_room not in rooms:
        return {
            "success": False,
            "error": f"Current room '{current_room}' not found in map",
            "hint": "Game state may be corrupted"
        }

    room = rooms[current_room]
    exits = room.get("exits", {})

    # Normalize direction
    direction = direction.lower().strip()

    # Check if direction is valid
    if direction not in exits:
        return {
            "success": False,
            "error": f"No exit to the {direction}",
            "valid_exits": list(exits.keys())
        }

    # Get the target room
    target_room = exits[direction]

    if target_room not in rooms:
        return {
            "success": False,
            "error": f"Target room '{target_room}' not found in map",
            "hint": "Map may be corrupted"
        }

    # Update game state
    game_state["current_room"] = target_room
    game_state["turn_count"] = game_state.get("turn_count", 0) + 1

    try:
        write_json(session_path / "game_state.json", game_state)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save game state: {str(e)}",
            "hint": "Check file permissions"
        }

    # Get new room data
    new_room = rooms[target_room]

    # Render updated SVG map
    svg = render_map_svg(rooms, target_room)

    return {
        "current_room": target_room,
        "room_description": new_room.get("description", ""),
        "exits": new_room.get("exits", {}),
        "svg": svg
    }
