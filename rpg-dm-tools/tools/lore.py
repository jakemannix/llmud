"""Lore lookup tools for RPG DM Tools (read-only access to world data)."""

from typing import Dict, Any
from utils.state import get_world_data
from utils.fuzzy import find_similar


def lookup_geography(region: str) -> Dict[str, Any]:
    """
    Look up information about a geographic region in the game world.

    Use this to get descriptions, notable features, and connections for
    locations like villages, forests, mountains, rivers, etc. Essential
    for describing environments and planning travel routes.

    Args:
        region: Name of the region to look up (e.g., "willowdale_village", "darkwood_forest")

    Returns:
        Dictionary with:
        - found: True if region exists
        - region: The region name
        - description: Text description of the area
        - notable_features: List of interesting features
        - connections: List of connected regions

        Or if not found:
        - found: False
        - query: The search term used
        - suggestions: List of similar region names
    """
    data = get_world_data("geography.json")
    if data is None:
        return {
            "success": False,
            "error": "Geography data file not found",
            "hint": "Ensure game_data/world/geography.json exists"
        }

    # Normalize region name for lookup
    region_key = region.lower().replace(" ", "_")

    if region_key in data:
        region_data = data[region_key]
        return {
            "found": True,
            "region": region_key,
            "description": region_data.get("description", ""),
            "notable_features": region_data.get("notable_features", []),
            "connections": region_data.get("connections", [])
        }

    # Not found - provide suggestions
    suggestions = find_similar(region_key, list(data.keys()))
    return {
        "found": False,
        "query": region,
        "suggestions": suggestions
    }


def lookup_npc(name: str) -> Dict[str, Any]:
    """
    Look up information about a non-player character (NPC).

    Use this to get details about villagers, merchants, guards, and other
    characters the players might interact with. Includes personality traits
    and what topics the NPC knows about.

    Args:
        name: Name or identifier of the NPC (e.g., "marta_innkeeper", "elder_morris")

    Returns:
        Dictionary with:
        - found: True if NPC exists
        - name: The NPC's display name
        - role: Their occupation or role
        - description: Physical description
        - personality: Personality traits
        - knows_about: List of topics they can discuss

        Or if not found:
        - found: False
        - query: The search term used
        - suggestions: List of similar NPC names
    """
    data = get_world_data("npcs.json")
    if data is None:
        return {
            "success": False,
            "error": "NPC data file not found",
            "hint": "Ensure game_data/world/npcs.json exists"
        }

    # Normalize name for lookup
    name_key = name.lower().replace(" ", "_")

    # Try direct lookup first
    if name_key in data:
        npc = data[name_key]
        return {
            "found": True,
            "name": npc.get("name", name_key),
            "role": npc.get("role", ""),
            "description": npc.get("description", ""),
            "personality": npc.get("personality", ""),
            "knows_about": npc.get("knows_about", [])
        }

    # Try matching by NPC's display name
    for key, npc in data.items():
        if npc.get("name", "").lower() == name.lower():
            return {
                "found": True,
                "name": npc.get("name", key),
                "role": npc.get("role", ""),
                "description": npc.get("description", ""),
                "personality": npc.get("personality", ""),
                "knows_about": npc.get("knows_about", [])
            }

    # Not found - provide suggestions
    all_names = list(data.keys()) + [npc.get("name", "") for npc in data.values()]
    suggestions = find_similar(name, all_names)
    return {
        "found": False,
        "query": name,
        "suggestions": suggestions
    }


def lookup_creature(creature_type: str) -> Dict[str, Any]:
    """
    Look up information about a creature type for combat encounters.

    Use this to get stats, abilities, and weaknesses for monsters, beasts,
    and other creatures. Essential for running combat encounters and
    describing enemy behavior.

    Args:
        creature_type: Type of creature (e.g., "wolf", "goblin", "skeleton")

    Returns:
        Dictionary with:
        - found: True if creature exists
        - type: The creature type name
        - description: Text description
        - stats: Combat statistics (hp, armor, attack)
        - weaknesses: List of vulnerabilities
        - abilities: List of special abilities

        Or if not found:
        - found: False
        - query: The search term used
        - suggestions: List of similar creature types
    """
    data = get_world_data("creatures.json")
    if data is None:
        return {
            "success": False,
            "error": "Creatures data file not found",
            "hint": "Ensure game_data/world/creatures.json exists"
        }

    # Normalize creature type for lookup
    type_key = creature_type.lower().replace(" ", "_")

    if type_key in data:
        creature = data[type_key]
        return {
            "found": True,
            "type": creature.get("type", type_key),
            "description": creature.get("description", ""),
            "stats": creature.get("stats", {}),
            "weaknesses": creature.get("weaknesses", []),
            "abilities": creature.get("abilities", [])
        }

    # Not found - provide suggestions
    suggestions = find_similar(type_key, list(data.keys()))
    return {
        "found": False,
        "query": creature_type,
        "suggestions": suggestions
    }


def lookup_scenario(scenario_id: str) -> Dict[str, Any]:
    """
    Look up a pre-written adventure scenario or quest hook.

    Use this to get quest details including the hook (how to introduce it),
    background details, and potential rewards. Great for starting adventures
    or finding side quests.

    Args:
        scenario_id: Identifier for the scenario (e.g., "missing_merchant", "wolf_attacks")

    Returns:
        Dictionary with:
        - found: True if scenario exists
        - id: The scenario identifier
        - title: Display title
        - hook: How to introduce the scenario to players
        - details: Background information for the GM
        - rewards: List of potential rewards

        Or if not found:
        - found: False
        - query: The search term used
        - suggestions: List of similar scenario IDs
    """
    data = get_world_data("scenarios.json")
    if data is None:
        return {
            "success": False,
            "error": "Scenarios data file not found",
            "hint": "Ensure game_data/world/scenarios.json exists"
        }

    # Normalize scenario ID for lookup
    id_key = scenario_id.lower().replace(" ", "_")

    if id_key in data:
        scenario = data[id_key]
        return {
            "found": True,
            "id": scenario.get("id", id_key),
            "title": scenario.get("title", ""),
            "hook": scenario.get("hook", ""),
            "details": scenario.get("details", ""),
            "rewards": scenario.get("rewards", [])
        }

    # Not found - provide suggestions
    suggestions = find_similar(id_key, list(data.keys()))
    return {
        "found": False,
        "query": scenario_id,
        "suggestions": suggestions
    }
