#!/usr/bin/env python3
"""
RPG DM Tools MCP Server

A FastMCP server providing tools for running a text-based roleplaying game.
Includes dice rolling, lore lookups, character management, and map navigation.

Usage:
    python rpg_server.py --port 8000

The server runs as HTTP and provides MCP tools for game masters and AI assistants.
"""

import argparse
import sys
from typing import Dict, Any

from fastmcp import FastMCP

# Import tool implementations
from tools.dice import roll_dice as _roll_dice
from tools.lore import (
    lookup_geography as _lookup_geography,
    lookup_npc as _lookup_npc,
    lookup_creature as _lookup_creature,
    lookup_scenario as _lookup_scenario,
)
from tools.session import (
    create_session as _create_session,
    get_session_state as _get_session_state,
)
from tools.character import (
    read_character as _read_character,
    update_character as _update_character,
)
from tools.movement import (
    get_current_map as _get_current_map,
    move_character as _move_character,
)

# Create the FastMCP server
mcp = FastMCP(
    name="rpg-dm-tools",
    instructions="""
    RPG DM Tools provides utilities for running a text-based roleplaying game.

    Getting Started:
    1. Create a session with create_session() to start a new game
    2. Use get_current_map() to see where the character is
    3. Use move_character() to navigate between rooms
    4. Use lookup_* tools to get world lore and NPC information
    5. Use roll_dice() for combat and skill checks
    6. Use read_character() and update_character() to manage the character sheet

    Sessions are persistent - use the same session_id to continue a game.
    """,
)


# ============================================================================
# Dice Tools (Stateless)
# ============================================================================


@mcp.tool()
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
        Dictionary with notation, rolls, modifier, and total.

    Examples:
        roll_dice("2d6+3") -> {"notation": "2d6+3", "rolls": [4, 2], "modifier": 3, "total": 9}
        roll_dice("d20") -> {"notation": "d20", "rolls": [15], "modifier": 0, "total": 15}
    """
    return _roll_dice(notation)


# ============================================================================
# Lore Tools (Read-Only)
# ============================================================================


@mcp.tool()
def lookup_geography(region: str) -> Dict[str, Any]:
    """
    Look up information about a geographic region in the game world.

    Use this to get descriptions, notable features, and connections for
    locations like villages, forests, mountains, rivers, etc. Essential
    for describing environments and planning travel routes.

    Args:
        region: Name of the region (e.g., "willowdale_village", "darkwood_forest")

    Returns:
        If found: region name, description, notable_features, and connections.
        If not found: suggestions for similar region names.
    """
    return _lookup_geography(region)


@mcp.tool()
def lookup_npc(name: str) -> Dict[str, Any]:
    """
    Look up information about a non-player character (NPC).

    Use this to get details about villagers, merchants, guards, and other
    characters the players might interact with. Includes personality traits
    and what topics the NPC knows about.

    Args:
        name: Name or identifier of the NPC (e.g., "marta_innkeeper", "Marta")

    Returns:
        If found: name, role, description, personality, and knows_about topics.
        If not found: suggestions for similar NPC names.
    """
    return _lookup_npc(name)


@mcp.tool()
def lookup_creature(creature_type: str) -> Dict[str, Any]:
    """
    Look up information about a creature type for combat encounters.

    Use this to get stats, abilities, and weaknesses for monsters, beasts,
    and other creatures. Essential for running combat encounters and
    describing enemy behavior.

    Args:
        creature_type: Type of creature (e.g., "wolf", "goblin", "skeleton")

    Returns:
        If found: type, description, stats (hp/armor/attack), weaknesses, abilities.
        If not found: suggestions for similar creature types.
    """
    return _lookup_creature(creature_type)


@mcp.tool()
def lookup_scenario(scenario_id: str) -> Dict[str, Any]:
    """
    Look up a pre-written adventure scenario or quest hook.

    Use this to get quest details including the hook (how to introduce it),
    background details, and potential rewards. Great for starting adventures
    or finding side quests.

    Args:
        scenario_id: Identifier for the scenario (e.g., "missing_merchant", "wolf_attacks")

    Returns:
        If found: id, title, hook, details, and rewards.
        If not found: suggestions for similar scenario IDs.
    """
    return _lookup_scenario(scenario_id)


# ============================================================================
# Session Management Tools
# ============================================================================


@mcp.tool()
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
        On success: session_id, character name, and starting_room.
        On failure: error message and hint.
    """
    return _create_session(session_id, character_name)


@mcp.tool()
def get_session_state(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the current state of a game session.

    Use this to check the current game status including character positions,
    active quests, and event flags. Call this to resume a session or get
    an overview of the game state.

    Args:
        session_id: The session identifier to look up

    Returns:
        On success: session_id, current_room, characters, active_quests, event_flags, turn_count.
        On failure: error message if session doesn't exist.
    """
    return _get_session_state(session_id)


# ============================================================================
# Character Management Tools
# ============================================================================


@mcp.tool()
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
        Full character sheet with name, stats, inventory, gold, and notes.
        Or error if session/character doesn't exist.
    """
    return _read_character(session_id, character_name)


@mcp.tool()
def update_character(session_id: str, character_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a character sheet with new values.

    Use this to modify character stats, inventory, gold, or notes. Supports
    special syntax for common operations like adding items or adjusting numbers.

    Args:
        session_id: The game session identifier
        character_name: Name of the character to update
        updates: Dictionary of updates. Supports special syntax:
                 {"stats.hp": 15} - Set nested value
                 {"inventory+": "torch"} - Append to list
                 {"inventory-": "rope"} - Remove from list
                 {"gold": "+10"} - Increment number
                 {"gold": "-5"} - Decrement number

    Returns:
        On success: success=True and the updated character sheet.
        On failure: error message (e.g., insufficient gold, hp > max_hp).
    """
    return _update_character(session_id, character_name, updates)


# ============================================================================
# Map and Movement Tools
# ============================================================================


@mcp.tool()
def get_current_map(session_id: str) -> Dict[str, Any]:
    """
    Get the current map view with the player's position.

    Use this to see where the character is, get a description of their
    surroundings, and see available exits. Returns an SVG visualization
    of the map with the current room highlighted.

    Args:
        session_id: The game session identifier

    Returns:
        current_room, room_description, exits dictionary, and SVG map visualization.
        Or error if session doesn't exist.
    """
    return _get_current_map(session_id)


@mcp.tool()
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
        On success: new current_room, room_description, exits, and SVG map.
        On invalid direction: error with list of valid_exits.
    """
    return _move_character(session_id, direction)


# ============================================================================
# Server Entry Point
# ============================================================================


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="RPG DM Tools MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python rpg_server.py --port 8000
    python rpg_server.py --port 8001
        """,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )

    args = parser.parse_args()

    print(f"RPG DM Tools MCP Server running on http://localhost:{args.port}/mcp")
    mcp.run(transport="http", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
