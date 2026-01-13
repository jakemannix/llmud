"""File I/O helpers and path management for RPG DM Tools."""

import json
import os
from pathlib import Path
from typing import Any, Optional


def get_game_data_path() -> Path:
    """Get the path to the game_data directory."""
    return Path(__file__).parent.parent / "game_data"


def read_json(path: Path) -> Optional[dict]:
    """
    Read and parse a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        Parsed JSON data as a dictionary, or None if file doesn't exist
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    """
    Write data to a JSON file, creating parent directories if needed.

    Args:
        path: Path to the JSON file
        data: Dictionary to write as JSON
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_world_data(filename: str) -> Optional[dict]:
    """
    Read data from the world/ directory (read-only lore).

    Args:
        filename: Name of the JSON file (e.g., "geography.json")

    Returns:
        Parsed JSON data or None if file doesn't exist
    """
    path = get_game_data_path() / "world" / filename
    return read_json(path)


def get_map_data(map_name: str) -> Optional[dict]:
    """
    Read map data from the maps/ directory.

    Args:
        map_name: Name of the map (e.g., "village")

    Returns:
        Parsed map data or None if map doesn't exist
    """
    path = get_game_data_path() / "maps" / f"{map_name}.json"
    return read_json(path)


def get_session_path(session_id: str) -> Path:
    """
    Get the path to a session directory.

    Args:
        session_id: The session identifier

    Returns:
        Path to the session directory
    """
    return get_game_data_path() / "sessions" / session_id


def ensure_session_exists(session_id: str) -> bool:
    """
    Check if a session exists.

    Args:
        session_id: The session identifier

    Returns:
        True if session exists, False otherwise
    """
    return get_session_path(session_id).exists()


def get_default_character() -> dict:
    """
    Get the default character template.

    Returns:
        Default character sheet as a dictionary
    """
    return {
        "name": "Hero",
        "stats": {
            "hp": 20,
            "max_hp": 20,
            "strength": 10,
            "dexterity": 10,
            "wisdom": 10
        },
        "inventory": ["torch", "rope", "dagger"],
        "gold": 15,
        "notes": []
    }


def get_character_path(session_id: str, character_name: str) -> Path:
    """
    Get the path to a character's JSON file.

    Args:
        session_id: The session identifier
        character_name: The character's name

    Returns:
        Path to the character file
    """
    return get_session_path(session_id) / "characters" / f"{character_name}.json"


def get_game_state_path(session_id: str) -> Path:
    """
    Get the path to a session's game state file.

    Args:
        session_id: The session identifier

    Returns:
        Path to the game state file
    """
    return get_session_path(session_id) / "game_state.json"


def read_character(session_id: str, character_name: str) -> Optional[dict]:
    """
    Read a character's data from a session.

    Args:
        session_id: The session identifier
        character_name: The character's name

    Returns:
        Character data or None if not found
    """
    return read_json(get_character_path(session_id, character_name))


def write_character(session_id: str, character_name: str, data: dict) -> None:
    """
    Write a character's data to a session.

    Args:
        session_id: The session identifier
        character_name: The character's name
        data: Character data to write
    """
    write_json(get_character_path(session_id, character_name), data)


def read_game_state(session_id: str) -> Optional[dict]:
    """
    Read the game state for a session.

    Args:
        session_id: The session identifier

    Returns:
        Game state data or None if not found
    """
    return read_json(get_game_state_path(session_id))


def write_game_state(session_id: str, data: dict) -> None:
    """
    Write the game state for a session.

    Args:
        session_id: The session identifier
        data: Game state data to write
    """
    write_json(get_game_state_path(session_id), data)
